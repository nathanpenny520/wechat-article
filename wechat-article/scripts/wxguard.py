#!/usr/bin/env python3
"""wxguard —— 两个排版引擎之间的安全栅栏。

整合保留了上游两套排版实现，它们的 `:::` 容器语法**部分同名但语义不同**：

| 容器 | wx 引擎 | aws 引擎 |
|---|---|---|
| `steps` | `:::steps`，每行一步，**自动编号、无参数** | `:::steps[标题]`，每行 `步骤名 | 说明` **两列** |
| `highlight` | `:::highlight`，首行当标题的琥珀色盒 | **已废弃**，会退化成普通文本（只打 WARN） |
| `label` / `section-title` | `:::label`、`:::label pill` | `:::section-title[01]` |

同一个名字在两个引擎里渲染成完全不同的结构，**而且不会报错**。这份模块把静默的语义漂移
变成显式报错，并提供跨两个引擎都能用的产物门禁（`gate`）。

用法：
    python3 scripts/wxguard.py containers <article.md> [--engine wx|aws] [--json]
    python3 scripts/wxguard.py gate <article.html> [--profile wx|generic] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wxenv  # noqa: E402

# ---------------------------------------------------------------- 容器登记表

#: 每个引擎真正认识（且语义正确）的容器名
ENGINE_CONTAINERS: dict[str, set[str]] = {
    "wx": {
        "dialogue", "timeline", "callout", "quote", "pullquote",
        "label", "steps", "highlight", "summary",
    },
    "aws": {
        "section-title", "lead", "quote-card", "stat", "steps",
        "compare", "layers", "checklist", "closing", "aside",
    },
}

#: 同名但语法/语义不同的容器 → 需要靠内容特征判定实际写法
AMBIGUOUS: dict[str, dict[str, str]] = {
    "steps": {
        "wx": ":::steps，每行一步，自动编号、不带方括号参数",
        "aws": ":::steps[标题]，每行「步骤名 | 说明」两列",
    },
}

#: 已废弃的容器名：写了不报错但会退化成普通文本。
#: **废弃是分引擎的**——`:::highlight` 在 wx 引擎里是内置容器，只有在 aws 引擎下才会退化。
DEPRECATED: dict[str, dict[str, str]] = {
    "highlight": {
        "aws": "aws 引擎已删除内置 :::highlight，会渲染成普通文本；wx 引擎仍支持它",
    },
    "note": {
        "wx": "已废弃容器；改用 :::callout info",
        "aws": "已废弃容器；改用 :::callout info 或自建组件",
    },
}

_BLOCK_OPEN = re.compile(r"^:::([A-Za-z0-9_-]+)\s*(?:\[(.*)\])?\s*$")
_BLOCK_CLOSE = re.compile(r"^:::\s*$")


def parse_blocks(markdown: str) -> list[dict]:
    """扫描 `:::` 块，返回 [{name, arg, line, body_lines, closed}]。"""
    blocks: list[dict] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        m = _BLOCK_OPEN.match(lines[i].strip())
        if not m:
            i += 1
            continue
        name, arg = m.group(1), (m.group(2) or "")
        body: list[str] = []
        j = i + 1
        closed = False
        while j < len(lines):
            if _BLOCK_CLOSE.match(lines[j].strip()):
                closed = True
                break
            body.append(lines[j])
            j += 1
        blocks.append(
            {"name": name, "arg": arg, "line": i + 1, "body_lines": body, "closed": closed}
        )
        i = j + 1 if closed else len(lines)
    return blocks


def _steps_style(block: dict) -> str:
    """判定 `:::steps` 的实际写法：aws（带标题或两列）还是 wx（纯逐行）。"""
    if block["arg"].strip():
        return "aws"
    for line in block["body_lines"]:
        if "|" in line:
            return "aws"
    return "wx"


def detect_style(block: dict) -> str:
    if block["name"] in AMBIGUOUS:
        return _steps_style(block) if block["name"] == "steps" else "wx"
    return "wx" if block["name"] in ENGINE_CONTAINERS["wx"] else "aws"


def check_containers(markdown: str, engine: str) -> dict:
    """检查 Markdown 里的 `:::` 用法是否与目标引擎相容。"""
    if engine not in ENGINE_CONTAINERS:
        raise ValueError(f"未知引擎: {engine}")
    own = ENGINE_CONTAINERS[engine]
    other = "aws" if engine == "wx" else "wx"

    blocks = parse_blocks(markdown)
    foreign: list[dict] = []
    ambiguous: list[dict] = []
    unknown: list[dict] = []
    deprecated: list[dict] = []
    unclosed: list[dict] = []

    for b in blocks:
        name = b["name"]
        if not b["closed"]:
            unclosed.append({"name": name, "line": b["line"]})
            continue
        if name in own:
            if name in AMBIGUOUS and _steps_style(b) == other:
                ambiguous.append(
                    {
                        "name": name,
                        "line": b["line"],
                        "expected": AMBIGUOUS[name][engine],
                        "found": AMBIGUOUS[name][other],
                    }
                )
            # 本引擎认识它，但本引擎把它标成废弃（如 aws 下的 highlight）
            hint = DEPRECATED.get(name, {}).get(engine)
            if hint:
                deprecated.append({"name": name, "line": b["line"], "hint": hint})
            continue
        if name in ENGINE_CONTAINERS[other]:
            # 属于另一个引擎：这是阻塞项，用 belongs_to 的提示说明，不再重复报废弃
            foreign.append(
                {"name": name, "line": b["line"], "belongs_to": other,
                 "hint": f"该容器只有 {other} 引擎认识；{engine} 引擎会把它当普通文本输出"}
            )
            continue
        unknown.append({"name": name, "line": b["line"]})
        hint = DEPRECATED.get(name, {}).get(engine)
        if hint:
            deprecated.append({"name": name, "line": b["line"], "hint": hint})

    blocking = bool(foreign or ambiguous or unclosed)
    return {
        "engine": engine,
        "block_count": len(blocks),
        "foreign": foreign,
        "ambiguous": ambiguous,
        "deprecated": deprecated,
        "unknown": unknown,
        "unclosed": unclosed,
        "ok": not blocking,
    }


def format_container_report(report: dict) -> str:
    engine = report["engine"]
    if report["ok"] and not report["deprecated"] and not report["unknown"]:
        return f"✓ {engine} 引擎：{report['block_count']} 个 ::: 块全部相容"
    lines = [f"::: 容器检查（目标引擎 {engine}，共 {report['block_count']} 块）", "-" * 48]
    for key, label in (
        ("foreign", "属于另一个引擎，本引擎会渲染成普通文本"),
        ("ambiguous", "同名但语法不同，会渲染成完全不同的结构"),
        ("unclosed", "缺少结尾的 :::"),
        ("deprecated", "已废弃"),
        ("unknown", "未知容器名（会按普通文本输出）"),
    ):
        for item in report.get(key, []):
            lines.append(f"[ERROR] 第 {item['line']} 行 :::{item['name']} —— {label}")
            for detail in ("hint", "expected", "found"):
                if item.get(detail):
                    lines.append(f"        {detail}: {item[detail]}")
    if report["ok"]:
        lines.append("结论：无阻塞问题")
    else:
        lines.append(f"结论：换引擎或改写这些块，或用 --engine {_suggest(report)}")
    return "\n".join(lines)


def _suggest(report: dict) -> str:
    if report["foreign"]:
        return report["foreign"][0].get("belongs_to", "aws")
    if report["ambiguous"]:
        return "aws" if report["engine"] == "wx" else "wx"
    return "aws"


# ---------------------------------------------------------------- 产物门禁

#: 与引擎无关的硬约束（微信会过滤或改写）
UNIVERSAL_RULES = {
    "style_tag", "script_tag", "link_tag", "position_unsupported", "float_css",
    "media_query", "keyframes", "import_css", "display_grid", "css_var",
    "external_font",
}

#: 只对 wx 引擎产物成立（aws 引擎会为微信专有嵌入类型输出 class，也会用 div 做分隔）
WX_ONLY_ERRORS = {"div_tag", "class_attr", "id_attr"}


def _load_rules() -> list[tuple]:
    """复用 vendored 引擎的规则表，避免两处规则漂移。"""
    wxenv.sys_path_prelude()
    from wxengine.commands.validate_html import RULES  # noqa: WPS433

    return list(RULES)


def gate(html: str, profile: str = "wx") -> list[dict]:
    """对 HTML 产物做微信兼容门禁。

    profile=wx      全部 ERROR 规则（含 div/class/id）——wx 引擎产物应恒过
    profile=generic div/class/id 降级为 WARN——aws 引擎产物按这个口径判
    """
    if profile not in ("wx", "generic"):
        raise ValueError("profile 只能是 wx 或 generic")
    rules = _load_rules()

    body = html
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    if m:
        body = m.group(1)

    findings: list[dict] = []
    for name, rx, level, message in rules:
        if profile == "generic" and name in WX_ONLY_ERRORS:
            level = "WARN"
        hits = rx.findall(body)
        if not hits:
            continue
        hit = rx.search(body)
        start = max(0, hit.start() - 20)
        findings.append(
            {
                "rule": name,
                "level": level,
                "count": len(hits),
                "message": message,
                "sample": body[start:hit.end() + 30].replace("\n", " ")[:80],
            }
        )

    img_count = len(re.findall(r"<img[\s>]", body, re.I))
    if img_count > 10:
        findings.append(
            {
                "rule": "too_many_images",
                "level": "WARN",
                "count": img_count,
                "message": f"正文 {img_count} 张图，超过微信上限 10 张",
                "sample": "",
            }
        )
    return findings


def format_gate_report(findings: list[dict], source: str, profile: str) -> str:
    errors = [f for f in findings if f["level"] == "ERROR"]
    warns = [f for f in findings if f["level"] != "ERROR"]
    if not findings:
        return f"✓ {source}：通过微信兼容门禁（profile={profile}）"
    lines = [f"微信兼容门禁 profile={profile}: {source}", "-" * 48]
    for f in findings:
        lines.append(f"[{f['level']:5s}] {f['rule']} ×{f['count']}: {f['message']}")
        if f["sample"]:
            lines.append(f"        …{f['sample']}…")
    lines.append(f"共 {len(errors)} 个 ERROR，{len(warns)} 个 WARN")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wxguard", description="排版引擎容器检查与产物微信兼容门禁")
    sub = ap.add_subparsers(dest="command")

    p_c = sub.add_parser("containers", help="检查 Markdown 的 ::: 用法是否与目标引擎相容")
    p_c.add_argument("input")
    p_c.add_argument("--engine", choices=("wx", "aws"), default="wx")
    p_c.add_argument("--json", action="store_true")

    p_g = sub.add_parser("gate", help="校验 HTML 产物的微信兼容性")
    p_g.add_argument("input")
    p_g.add_argument("--profile", choices=("wx", "generic"), default="wx")
    p_g.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    if not args.command:
        ap.print_help()
        return 0

    if args.command == "containers":
        text = Path(args.input).read_text(encoding="utf-8")
        report = check_containers(text, args.engine)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_container_report(report))
        return 0 if report["ok"] else 1

    html = Path(args.input).read_text(encoding="utf-8")
    findings = gate(html, args.profile)
    errors = [f for f in findings if f["level"] == "ERROR"]
    if args.json:
        print(json.dumps(
            {"profile": args.profile, "findings": findings, "errors": len(errors)},
            ensure_ascii=False, indent=2,
        ))
    else:
        print(format_gate_report(findings, args.input, args.profile))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
