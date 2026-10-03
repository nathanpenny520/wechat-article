#!/usr/bin/env python3
"""把排版产物放进手机宽度（375px）的预览页，便于在浏览器里核对版式。

为什么需要它：aws 引擎的产物是一段 `<section>` 片段（可直接作为草稿 `content`），
在浏览器里直接打开没有外层容器与字号，看不出真实观感；wx 引擎的产物虽是完整文档，
但它的预览是浏览器全宽，也不是手机上的样子。

用法：
    python3 make_preview.py 产物1.html [产物2.html …] -o 预览页.html [--title "标题"]
    每个产物一张 375px 手机卡，并排对比。
"""

from __future__ import annotations

import argparse
import html as html_mod
import re
import sys
from pathlib import Path

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ margin:0; background:#eef0f3;
         font-family:-apple-system,"PingFang SC","Hiragino Sans GB",sans-serif; }}
  .bar {{ position:sticky; top:0; z-index:9; background:#111a24; color:#fff;
         padding:10px 16px; font-size:13px; display:flex; gap:14px; align-items:baseline;
         flex-wrap:wrap; }}
  .bar b {{ font-weight:600; font-size:14px; }}
  .bar span {{ color:#9fb0c2; }}
  .wrap {{ display:flex; gap:26px; padding:26px; justify-content:center;
          align-items:flex-start; flex-wrap:wrap; }}
  .pane {{ width:375px; }}
  .phone {{ width:375px; background:#fff; border-radius:14px; overflow:hidden;
           box-shadow:0 8px 28px rgba(16,24,40,.14); }}
  .screen {{ padding:20px; }}
  .cap {{ text-align:center; color:#5b6472; font-size:12px; padding:9px 0 0; }}
</style>
</head>
<body>
<div class="bar"><b>{title}</b><span>{note}</span></div>
<div class="wrap">
{panes}
</div>
</body>
</html>
"""

PANE = """  <div class="pane">
    <div class="phone"><div class="screen">
{body}
    </div></div>
    <div class="cap">{label}</div>
  </div>"""


def extract_body(text: str) -> str:
    """完整文档取 <body>；片段（aws 引擎产物）原样使用。"""
    m = re.search(r"<body[^>]*>(.*)</body>", text, re.S | re.I)
    if m:
        return m.group(1).strip()
    # 去掉可能存在的 html/head 外壳
    return re.sub(r"(?is)^.*?</head>", "", text).strip()


def build(paths: list[Path], title: str, note: str) -> str:
    panes = []
    for path in paths:
        body = extract_body(path.read_text(encoding="utf-8"))
        panes.append(PANE.format(body=body, label=html_mod.escape(path.name)))
    return PAGE.format(title=html_mod.escape(title), note=html_mod.escape(note),
                       panes="\n".join(panes))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make_preview", description="生成 375px 手机宽度预览页")
    ap.add_argument("inputs", nargs="+", help="一个或多个排版产物 HTML")
    ap.add_argument("-o", "--output", required=True, help="输出预览页路径")
    ap.add_argument("--title", default="排版预览", help="预览页标题")
    ap.add_argument("--note", default="每张 375px，按手机正文宽度呈现", help="标题栏右侧说明")
    args = ap.parse_args(argv)

    paths = [Path(p) for p in args.inputs]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print("文件不存在: " + ", ".join(str(p) for p in missing), file=sys.stderr)
        return 2

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(paths, args.title, args.note), encoding="utf-8")
    print(f"[OK] 预览页已写入: {out}（{len(paths)} 张，用浏览器打开）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
