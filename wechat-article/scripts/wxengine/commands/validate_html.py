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
    ("iframe_tag", re.compile(r"<iframe[\s>]", re.I), "WARN",
     "<iframe> 仅白名单来源（腾讯视频等）可用，其余会被过滤"),
    ("external_link", re.compile(r'<a[^>]+href\s*=\s*["\']https?://(?!mp\.weixin\.qq\.com)', re.I), "WARN",
     "外部链接在未认证公众号会被过滤（converter 正常应已转脚注）"),
]


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
