#!/usr/bin/env python3
"""把排版产物截成手机宽度的 PNG —— 让「排版好不好看」这件事可以被看见。

## 为什么需要它

`wxart format` 产出的是 HTML，而 HTML 的正确性（标签闭合、内联样式、门禁通过）
机器能验，**观感**不能。此前核对版式的办法只有两个：把 HTML 丢进浏览器自己看，
或者发进草稿箱再看——前者要人工、后者要联网并且污染草稿箱。结果是换主题这件事
只能靠猜，跑完门禁就当作「排版好了」。

这个脚本把观感也变成确定性的产物：给定 HTML，输出一张 375px 宽（微信正文宽度）、
按内容实际高度裁好的 PNG。多份输入时额外拼一张横向对照图，几套主题谁更合适一眼可判。

## 用法

    python3 wxshot.py 产物.html -o 截图.png
    python3 wxshot.py a.html b.html -o 对比.png          # 生成对比.png + 每份单独截图
    python3 wxshot.py 产物.html -o 首屏.png --crop 0,1400
    python3 wxshot.py 产物.html -o 全篇.png --scale 2

## 依赖与降级

依赖一个 Chromium 内核浏览器（Chrome / Chromium / Edge / Brave）。找不到时**不静默
失败**：打印自己发现的候选路径和一份 `wxart preview-page` 的替代建议，返回非零退出码。
截图是给人和 Agent 看的辅助产物，不参与发布链路，所以这里不做「自动下载浏览器」这种
带网络副作用的兜底。
"""

from __future__ import annotations

import argparse
import html as html_mod
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

# 微信正文宽度。375 是 iPhone SE/8 的逻辑宽度，也是「手机上最窄的常见情形」——
# 按它排版，宽屏上只会更宽松，不会更挤。
PHONE_WIDTH = 375

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
]


def find_browser(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit if Path(explicit).exists() else None
    env = os.environ.get("WXSHOT_BROWSER")
    if env and Path(env).exists():
        return env
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    for name in ("google-chrome", "chromium", "chromium-browser",
                 "microsoft-edge", "brave-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def extract_body(text: str) -> str:
    """aws 引擎产出的是片段，wx 引擎产出的是整页文档；两者都要能喂进来。"""
    m = re.search(r"<body[^>]*>(.*)</body>", text, re.S | re.I)
    if m:
        return m.group(1)
    return text


def _page(fragment: str, width: int, extra: str = "", base_href: str = "") -> str:
    """外层容器**必须 margin:0**。

    Chrome 的 `--window-size` 只决定截图裁切范围，不决定布局视口（实测布局视口会
    停在 500px）。容器若写成 `margin:0 auto`，在 500px 视口里就被推到中间，
    截出来的 375px 只剩左半边——看起来像「正文被右边切掉了」，其实是截图裁错了。
    靠左摆放，裁切区就与容器严格重合。

    `base_href` 是原产物的所在目录：正文里的 `<img src="imgs/01.png">` 是**相对路径**，
    而这里把片段搬进了临时目录，不补 `<base>` 就会整篇图裂——带配图的稿子全中招。
    """
    base = f"<base href='{base_href}'>" if base_href else ""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"{base}<style>\n"
        "html,body{margin:0;padding:0;background:#ffffff;}\n"
        f"#wxshot-wrap{{width:{width}px;margin:0;}}\n"
        "</style></head><body>"
        f"<div id='wxshot-wrap'>{fragment}</div>{extra}</body></html>"
    )


_MEASURE_JS = """<script>window.addEventListener('load',function(){
  var wrap=document.getElementById('wxshot-wrap'), r=wrap.getBoundingClientRect(), over=[];
  document.querySelectorAll('#wxshot-wrap *').forEach(function(el){
    var b=el.getBoundingClientRect();
    if(b.right>r.right+1) over.push(Math.round(b.right)+'px '+(el.textContent||'').trim().slice(0,18));
  });
  var pre=document.createElement('pre'); pre.id='WXSHOT';
  pre.textContent='H='+Math.ceil(r.height)+'|OVER='+over.length+'|'+over.slice(0,3).join(' ~ ');
  document.body.appendChild(pre);});</script>"""


def _run(browser: str, args: list[str], timeout: int = 120) -> str:
    proc = subprocess.run([browser, "--headless=new", "--disable-gpu",
                           "--hide-scrollbars", "--no-sandbox", *args],
                          capture_output=True, text=True, timeout=timeout)
    return proc.stdout


def measure(browser: str, fragment: str, width: int, work: Path,
            base_href: str = "") -> tuple[int, int, str]:
    """返回 (内容高度, 横向溢出元素数, 溢出摘要)。"""
    probe = work / "_measure.html"
    probe.write_text(_page(fragment, width, _MEASURE_JS, base_href), encoding="utf-8")
    dom = _run(browser, [f"--window-size={width},1400", "--virtual-time-budget=6000",
                         "--dump-dom", probe.as_uri()])
    m = re.search(r"<pre id=['\"]WXSHOT['\"]>(.*?)</pre>", dom, re.S)
    if not m:
        return 0, 0, "(无法测量高度，按 3000px 截取)"
    info = html_mod.unescape(m.group(1))
    h = re.search(r"H=(\d+)", info)
    over = re.search(r"OVER=(\d+)", info)
    detail = info.split("|", 2)[2] if info.count("|") >= 2 else ""
    return (int(h.group(1)) if h else 0,
            int(over.group(1)) if over else 0,
            detail)


def shoot(browser: str, fragment: str, out: Path, width: int, height: int,
          scale: float, work: Path, base_href: str = "") -> tuple[int, int]:
    page = work / "_shot.html"
    page.write_text(_page(fragment, width, base_href=base_href), encoding="utf-8")
    args = [f"--window-size={width},{max(height, 1)}",
            "--virtual-time-budget=6000", f"--screenshot={out}", page.as_uri()]
    if scale != 1:
        args.insert(0, f"--force-device-scale-factor={scale}")
    _run(browser, args)
    if not out.exists():
        return 0, 0
    head = out.read_bytes()[:33]
    w, h = struct.unpack(">II", head[16:24])
    return w, h


_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def _label(text: str, width: int):
    """栏头标签。PIL 的默认位图字体在 2x 截图里小到看不清，优先用系统 TTF。"""
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for cand in _FONT_CANDIDATES:
        if Path(cand).exists():
            try:
                font = ImageFont.truetype(cand, 20)
                break
            except OSError:
                continue
    bar = Image.new("RGB", (width, 40), (17, 26, 36))
    d = ImageDraw.Draw(bar)
    d.text((12, 20), text[:40], fill=(255, 255, 255), font=font, anchor="lm" if font else None)
    return bar


def contact_sheet(items: list[tuple[str, Path]], out: Path, sheet_height: int) -> str | None:
    """把多份截图各取前 N 像素横向拼一张对照图。缺 Pillow 时返回原因。"""
    try:
        from PIL import Image
    except ImportError:
        return "未安装 Pillow，跳过对照图（pip install Pillow）"

    panels = []
    for _label_text, path in items:
        with Image.open(path) as im:
            im = im.convert("RGB")
            h = min(sheet_height, im.height)
            panels.append(im.crop((0, 0, im.width, h)))
    width = sum(p.width for p in panels) + 16 * (len(panels) + 1)
    height = max(p.height for p in panels) + 40 + 16 * 2
    sheet = Image.new("RGB", (width, height), (238, 240, 243))
    x = 16
    for (label, _), panel in zip(items, panels):
        sheet.paste(_label(label, panel.width), (x, 16))
        sheet.paste(panel, (x, 16 + 40 + 8))
        x += panel.width + 16
    sheet.save(out)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wxshot",
        description="排版产物 → 手机宽度 PNG（用于核对观感）",
    )
    ap.add_argument("inputs", nargs="+", help="一个或多个排版产物 HTML")
    ap.add_argument("-o", "--output", required=True, help="输出 PNG 路径")
    ap.add_argument("--width", type=int, default=PHONE_WIDTH,
                    help=f"视口宽度，默认 {PHONE_WIDTH}（微信正文宽度）")
    ap.add_argument("--scale", type=float, default=2.0,
                    help="像素密度，默认 2（视网膜清晰度）")
    ap.add_argument("--crop", default="",
                    help="只截一段，形如 0,1400（起点,终点）；默认截整篇")
    ap.add_argument("--max-height", type=int, default=12000,
                    help="单张最大高度，超过则截断，默认 12000")
    ap.add_argument("--sheet-height", type=int, default=1500,
                    help="多份输入时对照图每栏取多高，默认 1500")
    ap.add_argument("--no-sheet", action="store_true", help="多份输入时不拼对照图")
    ap.add_argument("--browser", help="指定 Chromium 内核浏览器可执行文件路径")
    args = ap.parse_args(argv)

    browser = find_browser(args.browser)
    if not browser:
        print("[ERROR] 没找到 Chromium 内核浏览器（Chrome / Chromium / Edge / Brave）。", file=sys.stderr)
        print("  已查找：", file=sys.stderr)
        for p in CHROME_CANDIDATES:
            print(f"    {p}", file=sys.stderr)
        print("  可显式指定：wxart shot … --browser /path/to/Chrome", file=sys.stderr)
        print("  或设环境变量 WXSHOT_BROWSER。", file=sys.stderr)
        print("  也可以先退回浏览器核对：wxart preview-page <html…> -o 预览.html", file=sys.stderr)
        return 3

    paths = [Path(p) for p in args.inputs]
    for p in paths:
        if not p.exists():
            print(f"[ERROR] 文件不存在: {p}", file=sys.stderr)
            return 2

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    crop = None
    if args.crop.strip():
        try:
            a, b = (int(x) for x in args.crop.split(","))
            crop = (a, b)
        except ValueError:
            print("[ERROR] --crop 需形如 0,1400", file=sys.stderr)
            return 2

    results: list[tuple[str, Path]] = []
    with tempfile.TemporaryDirectory(prefix="wxshot-") as td:
        work = Path(td)
        for i, path in enumerate(paths):
            fragment = extract_body(path.read_text(encoding="utf-8"))
            # 正文图是相对路径，必须让页面以产物目录为基准解析，否则整篇图裂
            base_href = path.resolve().parent.as_uri() + "/"
            height, over, detail = measure(browser, fragment, args.width, work, base_href)
            if height <= 0:
                height = 3000
            # 多份输入时文件名带上序号。只按 `path.stem` 命名会撞车——
            # 对比不同主题时输入往往同名（各有各目录的 article.html），
            # 后一张会静默覆盖前一张，只剩最后一张能看。
            target = out if len(paths) == 1 else out.with_name(
                f"{out.stem}-{i + 1}-{path.stem}{out.suffix or '.png'}")
            y0 = crop[0] if crop else 0
            y1 = min(crop[1] if crop else height, height + 40, args.max_height)

            # 裁剪靠「先按整篇高度截、再切」实现：Chrome 的 --screenshot 没有 offset 参数。
            tmp = work / f"full-{i}.png"
            shoot(browser, fragment, tmp, args.width, height + 40, args.scale, work, base_href)
            if crop or y1 < height:
                try:
                    from PIL import Image
                except ImportError:
                    print("[ERROR] 用了 --crop/高度截断但没装 Pillow，无法裁剪。", file=sys.stderr)
                    return 3
                with Image.open(tmp) as im:
                    im.crop((0, int(y0 * args.scale), im.width,
                             min(int(y1 * args.scale), im.height))).save(target)
            else:
                shutil.copy2(tmp, target)

            # 尺寸以**实际落盘的 PNG** 为准，不由意图反推——两者不一致时谎言会留在日志里。
            with open(target, "rb") as fh:
                w, h_px = struct.unpack(">II", fh.read(33)[16:24])
            if over:
                print(f"[OK] {target}  {w}x{h_px}  "
                      f"内容高度 {height}px  ⚠ {over} 处横向溢出: {detail}")
            else:
                print(f"[OK] {target}  {w}x{h_px}  "
                      f"内容高度 {height}px  无横向溢出")
            results.append((path.stem, target))

    if len(results) > 1 and not args.no_sheet:
        sheet = out.with_name(f"{out.stem}-sheet{out.suffix or '.png'}")
        why = contact_sheet(results, sheet, args.sheet_height)
        if why:
            print(f"[WARN] {why}")
        else:
            print(f"[OK] 对照图 {sheet}（每栏取前 {args.sheet_height}px）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
