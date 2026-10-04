#!/usr/bin/env python3
"""微信公众号 HTML 产物合规校验。

规则依据是微信编辑器/草稿箱对 HTML 的平台行为（会过滤的标签与属性、
不支持的 CSS 特性——参见 wewrite-publish skill 的 wechat-constraints.md），
全部为本项目独立实现。

用法：
    wewrite validate article.html            # 文本报告
    wewrite validate article.html --json     # JSON（agent 用）

退出码：1 = 存在 ERROR（会被平台过滤/改写的写法），0 = 通过（WARN 不阻断）。
converter 自产的 HTML 应恒过 ERROR 级；本工具主要护住两类场景：
人工改过的 HTML、外部来源的 HTML。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# (规则名, 正则, 级别, 说明)。ERROR = 微信会过滤该写法或导致样式失效。
RULES = [
    ("style_tag", re.compile(r"<style[\s>]", re.I), "ERROR",
     "<style> 标签会被微信过滤，样式必须内联到元素"),
    ("script_tag", re.compile(r"<script[\s>]", re.I), "ERROR",
     "<script> 标签会被微信过滤"),
    ("link_tag", re.compile(r"<link[\s>]", re.I), "ERROR",
     "外部 <link>（CSS/字体）会被微信过滤"),
    ("div_tag", re.compile(r"</?div[\s>]", re.I), "ERROR",
     "<div> 会被微信编辑器改写，应使用 <section>"),
    ("class_attr", re.compile(r"<[^>]+\sclass\s*=", re.I), "ERROR",
     "class 属性会被剥离，样式必须内联"),
    ("id_attr", re.compile(r"<[^>]+\sid\s*=", re.I), "ERROR",
     "id 属性会被剥离"),
    ("position_unsupported", re.compile(r"position\s*:\s*(fixed|absolute|sticky)", re.I), "ERROR",
     "position: fixed/absolute/sticky 在微信正文不生效"),
    ("float_css", re.compile(r"float\s*:\s*(left|right)", re.I), "ERROR",
     "float 布局在微信正文不可靠，应使用 flex"),
    ("media_query", re.compile(r"@media", re.I), "ERROR",
     "@media 媒体查询不被支持（暗黑模式用 data-darkmode-* 属性）"),
    ("keyframes", re.compile(r"@keyframes|animation\s*:", re.I), "ERROR",
     "CSS 动画不被支持"),
    ("import_css", re.compile(r"@import", re.I), "ERROR",
     "@import 不被支持"),
    ("display_grid", re.compile(r"display\s*:\s*grid", re.I), "ERROR",
     "display:grid 不被支持，应使用 flex"),
    ("css_var", re.compile(r"var\s*\(\s*--", re.I), "ERROR",
     "CSS 变量 var(--x) 不被支持，颜色需写实际值"),
    ("external_font", re.compile(r"url\s*\(['\"]?https?://[^)]*\.(?:woff2?|ttf|otf|eot)", re.I), "ERROR",
     "外部字体文件不会被加载"),
    ("quoted_url", re.compile(r"url\s*\(\s*['\"]", re.I), "ERROR",
     "url() 里带引号会让整个元素被拆掉（背景图连同 <section> 一起消失），引号必须去掉"),
    ("iframe_tag", re.compile(r"<iframe[\s>]", re.I), "WARN",
     "<iframe> 仅白名单来源（腾讯视频等）可用，其余会被过滤"),
    ("external_link", re.compile(r'<a[^>]+href\s*=\s*["\']https?://(?!mp\.weixin\.qq\.com)', re.I), "WARN",
     "外部链接在未认证公众号会被过滤（converter 正常应已转脚注）"),
]

# nodeleaf 容器检查用：自闭合/空元素，不参与层级计数
_VOID_TAGS = {"img", "br", "hr", "mpvoice", "mpvideo", "source", "input", "wbr", "area"}
# 出现在 nodeleaf 顶层即违规的块级标签
_BLOCK_TAGS = {"section", "p", "div", "table", "thead", "tbody", "tr", "td", "th",
               "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
               "blockquote", "pre", "figure"}

_ATTR_RE = r'((?:"[^"]*"|\'[^\']*\'|[^>])*?)'


def _extract_nodeleaf(inner_html: str) -> list[str]:
    """取出每个 `<section nodeleaf>` 的内层 HTML（按 section 配平切分）。

    微信会把裸属性规范化成 `nodeleaf="nodeleaf"`，所以只匹配属性名本身。
    """
    out = []
    for m in re.finditer(r"<section\b[^>]*\bnodeleaf\b[^>]*>", inner_html, re.I):
        depth = 1
        rest = inner_html[m.end():]
        closed = False
        for t in re.finditer(r"<(/?)section\b[^>]*>", rest, re.I):
            if t.group(1):
                depth -= 1
                if depth == 0:
                    out.append(rest[:t.start()])
                    closed = True
                    break
            else:
                depth += 1
        if not closed:  # 未闭合：按到文末处理，避免漏报
            out.append(rest)
    return out


def _top_level_tags(fragment: str) -> list[str]:
    """片段里处于最外层的元素名（用于判断 nodeleaf 装了几个东西）。"""
    tags: list[str] = []
    depth = 0
    for m in re.finditer(r"<(/?)([a-zA-Z][\w:-]*)" + _ATTR_RE + r"(/?)>", fragment):
        closing, name, _attrs, self_close = m.groups()
        name = name.lower()
        if name in _VOID_TAGS:
            if depth == 0:
                tags.append(name)
            continue
        if closing:
            depth = max(0, depth - 1)
        else:
            if depth == 0:
                tags.append(name)
            if not self_close:
                depth += 1
    return tags


def validate_html(html: str) -> list[dict]:
    """返回问题列表 [{rule, level, message, count, sample}]，无问题返回 []。

    传入完整 HTML 页面（如 preview 产物）时只校验 <body> 内容——
    预览包装的 <head>/<style> 不参与公众号粘贴/发布。
    """
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    if m:
        html = m.group(1)
    issues = []
    for name, rx, level, msg in RULES:
        hits = rx.findall(html)
        if hits:
            m = rx.search(html)
            start = max(0, m.start() - 20)
            issues.append({
                "rule": name,
                "level": level,
                "message": msg,
                "count": len(hits),
                "sample": html[start:m.end() + 30].replace("\n", " ")[:80],
            })

    # 结构性检查：nodeleaf 容器。官方规范（编辑器插件开发规范 2.3）：
    # 该容器只允许包裹单个图片 / 视频 / 官方组件；2026-10-04 真机实测，
    # 里面放 <p> 时回读保留、手机上整段消失。
    for frag in _extract_nodeleaf(html):
        top = _top_level_tags(frag)
        blocks = [t for t in top if t in _BLOCK_TAGS]
        if blocks:
            issues.append({
                "rule": "nodeleaf_content", "level": "ERROR",
                "message": "nodeleaf 容器内出现块级元素（%s）：官方只允许单个图片/视频/官方组件，"
                           "客户端会把这部分内容整段丢弃" % "、".join(sorted(set(blocks))),
                "count": len(blocks),
                "sample": "<section nodeleaf>…" + frag.strip()[:60].replace("\n", " ") + "…",
            })
        elif len(top) > 1:
            issues.append({
                "rule": "nodeleaf_content", "level": "ERROR",
                "message": "nodeleaf 容器内有 %d 个顶层子元素：官方只允许一个（图片/视频/官方组件）" % len(top),
                "count": len(top),
                "sample": "<section nodeleaf>…" + frag.strip()[:60].replace("\n", " ") + "…",
            })
        elif not top:
            issues.append({
                "rule": "nodeleaf_empty", "level": "WARN",
                "message": "nodeleaf 容器是空的：该容器只用于承载单个图片/视频/官方组件",
                "count": 1, "sample": "",
            })

    # 结构性检查：图片数量（平台上限 10 张，publish 预检也会拦，这里提前提醒）
    img_count = len(re.findall(r"<img[\s>]", html, re.I))
    if img_count > 10:
        issues.append({
            "rule": "too_many_images", "level": "WARN",
            "message": f"图片 {img_count} 张，超过微信正文上限 10 张（发布时会移除末尾多余）",
            "count": img_count, "sample": "",
        })
    return issues


def format_text(issues: list[dict], source: str) -> str:
    if not issues:
        return f"✓ {source}: 通过微信兼容性校验"
    lines = [f"微信兼容性校验: {source}", "-" * 40]
    for i in issues:
        lines.append(f"[{i['level']:5s}] {i['rule']} ×{i['count']}: {i['message']}")
        if i["sample"]:
            lines.append(f"        …{i['sample']}…")
    errors = sum(1 for i in issues if i["level"] == "ERROR")
    warns = len(issues) - errors
    lines.append(f"共 {errors} 个 ERROR，{warns} 个 WARN")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="wewrite validate",
                                 description="校验 HTML 是否会被微信编辑器/草稿箱过滤或改写")
    ap.add_argument("input", help="HTML 文件路径")
    ap.add_argument("--json", action="store_true", help="JSON 输出（agent 用）")
    args = ap.parse_args(argv)

    html = Path(args.input).read_text(encoding="utf-8")
    issues = validate_html(html)

    if args.json:
        print(json.dumps({"issues": issues,
                          "errors": sum(1 for i in issues if i["level"] == "ERROR"),
                          "warnings": sum(1 for i in issues if i["level"] == "WARN")},
                         ensure_ascii=False, indent=2))
    else:
        print(format_text(issues, args.input))

    sys.exit(1 if any(i["level"] == "ERROR" for i in issues) else 0)


if __name__ == "__main__":
    main()
