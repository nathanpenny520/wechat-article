#!/usr/bin/env python3
"""把「文章里已经核实过的数字」画成正文配图。

## 为什么是图表而不是「配图」

行业观察与产品说明这两类文章里的图不应该是装饰性插画：读者读到「AMD 花 82 亿美元」
「这个项目三万星」，帮他记住的是**图和数字**，不是一张氛围照。而且没有生图模型时，
唯一诚实且可行的做法就是**把已核实的数字画出来**。

**这个脚本不会自己编数据。** 它只渲染 spec 里给出的数字，一个都不推算。
图表有很强的视觉权威感，读者会默认它是硬事实——把没核实的数字画进图里，
比写错在正文里更严重。所以 spec 里还支持 `source`，把出处留在图上。

## 为什么不用 SVG

正文里的 `:::stat` / `:::compare` 已经能做数字排版，但它们只能做**文字**：
条形长度、时间线刻度、2×2 数字面板需要像素级控制。内联 `<svg>` 在微信里虽然能活，
但 SVG 没有自动换行，中文折行要手工算。画成 PNG 最稳。

## 四种图形

| kind | 用途 |
|---|---|
| `bar` | 横向条形，比较几个同类数字（星标数、耗时） |
| `kpi` | 2×2 数字面板，几个互不可比但都很重的数字 |
| `timeline` | 竖向时间线，按时间发生的一串事件 |
| `compare` | 左右两栏概念对照（不是数字，是两种形态） |

## spec 格式

    kind: bar
    title: 六个项目的 GitHub 星标
    subtitle: 10 月 4 日从 GitHub 官方 API 读取   # 可选
    source: 数据来源：GitHub REST API             # 可选，印在图底部
    accent: "#C0392B"                            # 可选
    items:
      - {label: laya, value: 30393, note: 非自回归决策引擎}

    # kpi:      items: [{value: 82 亿美元, label: 全股票对价}]
    # timeline: items: [{date: 9/28, text: AMD 宣布收购 World Labs, note: 可选}]
    # compare:  left: {title: 聊天模型, items: [...]}, right: {title: 决策模型, items: [...]}

## 用法

    python3 make_chart.py spec.yaml -o imgs/01-stars.png
    python3 make_chart.py spec.yaml -o out.png --accent "#2E7BF6"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wxfont  # noqa: E402

#: 微信正文宽度减去左右各 16px 页边距。配图与正文同宽，缩放到 100% 时不变形。
W_CSS = 343
SCALE = 2
W = W_CSS * SCALE

KINDS = ("bar", "kpi", "timeline", "compare")

INK = (26, 26, 26)
MUTED = (122, 122, 122)
LINE = (228, 223, 216)
PANEL = (255, 255, 255)
TRACK = (242, 239, 235)


def px(v: float) -> int:
    return int(round(v * SCALE))


def mix(a, b, t: float):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def parse_hex(value: str) -> tuple[int, int, int]:
    s = str(value).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise SystemExit(f"[ERROR] 不是合法颜色: {value!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


# ------------------------------------------------------------------ 文字工具

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.,%:/+-]*|\s+|.")


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    """CJK 友好的折行：中文逐字断，西文按词断，数字与英文单词不拆开。"""
    lines: list[str] = []
    cur = ""
    for token in _TOKEN.findall(text):
        if token.isspace():
            if cur and not cur.endswith(" "):
                cur += " "
            continue
        if draw.textlength(cur + token, font=font) <= max_w or not cur:
            cur += token
        else:
            lines.append(cur.rstrip())
            cur = token
    if cur.strip():
        lines.append(cur.rstrip())
    return lines or [""]


def new_panel(height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (W, height), PANEL)
    d = ImageDraw.Draw(im)
    # 1px 内描边：图与底纹之间需要一点边界，否则浅色图会「浮」在纸上
    d.rectangle([0, 0, W - 1, height - 1], outline=LINE, width=1)
    return im, d


def header(d: ImageDraw.ImageDraw, title: str, subtitle: str, accent) -> int:
    """画标题区，返回正文起始 y。"""
    y = px(20)
    # 左上角短色条：和正文里导语装置同一种语法
    d.rectangle([px(20), y + px(3), px(20) + px(26), y + px(7)], fill=accent)
    y += px(18)
    f_title = wxfont.load(px(19))
    f_sub = wxfont.load(px(12))
    for line in wrap(d, title, f_title, W - px(40)):
        d.text((px(20), y), line, font=f_title, fill=INK)
        y += f_title.size + px(4)
    if subtitle:
        y += px(3)
        for line in wrap(d, subtitle, f_sub, W - px(40)):
            d.text((px(20), y), line, font=f_sub, fill=MUTED)
            y += f_sub.size + px(3)
    return y + px(16)


def _num(value) -> str:
    """数字显示：整数加千分位，小数最多两位。"""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{int(f):,}" if f.is_integer() else f"{f:,.2f}".rstrip("0").rstrip(".")


def fit_font(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, floor: int = 9):
    """把字号收到放得下为止。

    长标签（`SemIf-OpenJev` 这种）会顶到旁边的条形上——不处理就是「图里有两块
    叠在一起的字」，比字号小一点难看得多。
    """
    while draw.textlength(text, font=font) > max_w and font.size > px(floor):
        font = wxfont.load(font.size - 1)
    return font


# ------------------------------------------------------------------ 四种图形


def render_bar(spec: dict, accent) -> Image.Image:
    items = list(spec.get("items") or [])
    if not items:
        raise SystemExit("[ERROR] bar 需要 items")
    values = [float(i.get("value") or 0) for i in items]
    vmax = max(values) or 1
    f_label = wxfont.load(px(13))
    f_value = wxfont.load(px(14))
    f_note = wxfont.load(px(11))

    row_pitch = px(34)
    height = px(56) + px(46) + row_pitch * len(items) + px(20)
    im, d = new_panel(height)
    y = header(d, spec.get("title", ""), spec.get("subtitle", ""), accent)

    label_w = px(96)
    bar_x = px(20) + label_w + px(10)
    value_w = px(58)
    bar_max = W - bar_x - value_w - px(20)
    soft = mix(accent, (255, 255, 255), 0.45)

    for item, value in zip(items, values):
        label = str(item.get("label", ""))
        lf = fit_font(d, label, f_label, label_w)
        d.text((px(20), y + px(2) + (f_label.size - lf.size) // 2), label, font=lf, fill=INK)
        top = y + px(2)
        d.rectangle([bar_x, top, bar_x + bar_max, top + px(14)], fill=TRACK)
        w = max(px(3), int(bar_max * value / vmax))
        d.rectangle([bar_x, top, bar_x + w, top + px(14)], fill=accent)
        text = str(item.get("display") or _num(item.get("value")))
        d.text((bar_x + bar_max + px(8), y + px(1)), text, font=f_value, fill=soft)
        if item.get("note"):
            for line in wrap(d, str(item["note"]), f_note, bar_max)[:1]:
                d.text((bar_x, y + px(19)), line, font=f_note, fill=MUTED)
        y += row_pitch
    return im


def render_kpi(spec: dict, accent) -> Image.Image:
    items = list(spec.get("items") or [])
    if not items:
        raise SystemExit("[ERROR] kpi 需要 items")
    f_value = wxfont.load(px(25))
    f_label = wxfont.load(px(12))
    cols = 2
    rows = (len(items) + cols - 1) // cols
    cell_h = px(84)
    height = px(56) + px(46) + cell_h * rows + px(14)
    im, d = new_panel(height)
    y0 = header(d, spec.get("title", ""), spec.get("subtitle", ""), accent)

    col_w = (W - px(40) - px(12)) // cols
    for i, item in enumerate(items):
        cx = px(20) + (i % cols) * (col_w + px(12))
        cy = y0 + (i // cols) * cell_h
        d.rectangle([cx, cy, cx + px(2), cy + px(28)], fill=accent)
        value = str(item.get("value", ""))
        # 长数字（「82 亿美元」这种带单位的）自动收字号，避免压出格子
        font = f_value
        while d.textlength(value, font=font) > col_w - px(16) and font.size > px(14):
            font = wxfont.load(font.size - px(2))
        d.text((cx + px(10), cy), value, font=font, fill=accent)
        yy = cy + font.size + px(8)
        for line in wrap(d, str(item.get("label", "")), f_label, col_w - px(16))[:3]:
            d.text((cx + px(10), yy), line, font=f_label, fill=MUTED)
            yy += f_label.size + px(3)
    return im


def render_timeline(spec: dict, accent) -> Image.Image:
    items = list(spec.get("items") or [])
    if not items:
        raise SystemExit("[ERROR] timeline 需要 items")
    f_date = wxfont.load(px(12))
    f_text = wxfont.load(px(14))
    f_sub = wxfont.load(px(11))

    line_x = px(84)
    text_x = line_x + px(20)
    text_w = W - text_x - px(22)

    # 折行依赖字体度量，只能先拿一个探针 draw 量一遍高度
    probe = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    heights = []
    for item in items:
        h = len(wrap(probe, str(item.get("text", "")), f_text, text_w)) * (f_text.size + px(4))
        if item.get("note"):
            h += f_sub.size + px(4)
        heights.append(max(h, px(30)) + px(16))

    height = px(56) + px(46) + sum(heights) + px(16)
    im, d = new_panel(height)
    y = header(d, spec.get("title", ""), spec.get("subtitle", ""), accent)

    d.line([line_x, y, line_x, y + sum(heights) - px(16)], fill=LINE, width=px(1))
    for item, h in zip(items, heights):
        cy = y + px(8)
        d.ellipse([line_x - px(5), cy - px(5), line_x + px(5), cy + px(5)], fill=accent)
        date = str(item.get("date", ""))
        d.text((line_x - px(14) - d.textlength(date, font=f_date), cy - px(7)),
               date, font=f_date, fill=MUTED)
        yy = cy - px(8)
        for line in wrap(d, str(item.get("text", "")), f_text, text_w):
            d.text((text_x, yy), line, font=f_text, fill=INK)
            yy += f_text.size + px(4)
        if item.get("note"):
            d.text((text_x, yy), str(item["note"]), font=f_sub, fill=MUTED)
        y += h
    return im


def render_compare(spec: dict, accent) -> Image.Image:
    left = dict(spec.get("left") or {})
    right = dict(spec.get("right") or {})
    if not left or not right:
        raise SystemExit("[ERROR] compare 需要 left 与 right")
    f_head = wxfont.load(px(14))
    f_item = wxfont.load(px(13))

    col_w = (W - px(40) - px(10)) // 2
    probe = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    rows = []
    for l, r in zip(left.get("items") or [], right.get("items") or []):
        lh = len(wrap(probe, str(l), f_item, col_w - px(20))) * (f_item.size + px(3))
        rh = len(wrap(probe, str(r), f_item, col_w - px(20))) * (f_item.size + px(3))
        rows.append(max(lh, rh) + px(12))

    height = px(56) + px(46) + px(32) + sum(rows) + px(18)
    im, d = new_panel(height)
    y = header(d, spec.get("title", ""), spec.get("subtitle", ""), accent)

    soft = mix(accent, (255, 255, 255), 0.90)
    for col, cfg, is_right in ((0, left, False), (1, right, True)):
        x = px(20) + col * (col_w + px(10))
        d.rectangle([x, y, x + col_w, y + px(28)], fill=soft if is_right else TRACK)
        d.text((x + px(10), y + px(6)), str(cfg.get("title", "")), font=f_head,
               fill=accent if is_right else MUTED)
    y += px(32)

    for idx, h in enumerate(rows):
        for col, cfg in ((0, left), (1, right)):
            items = list(cfg.get("items") or [])
            if idx >= len(items):
                continue
            x = px(20) + col * (col_w + px(10))
            yy = y
            for line in wrap(d, str(items[idx]), f_item, col_w - px(20)):
                d.text((x + px(10), yy), line, font=f_item, fill=INK)
                yy += f_item.size + px(3)
        y += h
    return im


RENDERERS = {"bar": render_bar, "kpi": render_kpi, "timeline": render_timeline,
             "compare": render_compare}


def render(spec: dict, accent_override: str | None = None) -> Image.Image:
    kind = str(spec.get("kind", "")).strip()
    if kind not in RENDERERS:
        raise SystemExit(f"[ERROR] kind 只能是 {'/'.join(KINDS)}，收到 {kind!r}")
    accent = parse_hex(accent_override or spec.get("accent") or "#C0392B")
    im = RENDERERS[kind](spec, accent)

    # 底部来源行。图表有很强的视觉权威感，出处必须留在图上，不能只写在正文里。
    if spec.get("source"):
        draw_probe = ImageDraw.Draw(Image.new("RGB", (W, 10)))
        f = wxfont.load(px(10))
        rows = wrap(draw_probe, str(spec["source"]), f, W - px(40))
        band = len(rows) * (f.size + px(2)) + px(14)
        tall = Image.new("RGB", (W, im.height + band), PANEL)
        tall.paste(im, (0, 0))
        d = ImageDraw.Draw(tall)
        d.line([px(20), im.height + px(6), W - px(20), im.height + px(6)], fill=LINE, width=1)
        yy = im.height + px(10)
        for line in rows:
            d.text((px(20), yy), line, font=f, fill=MUTED)
            yy += f.size + px(2)
        d.rectangle([0, tall.height - 1, W - 1, tall.height - 1], outline=LINE, width=1)
        im = tall
    return im


def main(argv: list[str] | None = None) -> int:
    import yaml

    ap = argparse.ArgumentParser(prog="make_chart", description="把已核实的数字画成正文配图")
    ap.add_argument("spec", nargs="?", help="spec YAML 路径")
    ap.add_argument("-o", "--output", help="输出 PNG 路径")
    ap.add_argument("--accent", help="覆盖 spec 里的主色")
    ap.add_argument("--list", action="store_true", help="列出可用的 kind")
    args = ap.parse_args(argv)

    if args.list:
        for k in KINDS:
            print(f"  {k}")
        return 0
    if not args.spec or not args.output:
        ap.error("spec 与 -o 都是必需的（或加 --list）")

    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"[ERROR] spec 不存在: {spec_path}", file=sys.stderr)
        return 2
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    im = render(spec, args.accent)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, optimize=True)
    css = f"{im.size[0] // SCALE}×{im.size[1] // SCALE}"
    print(f"[OK] {out}  {im.size[0]}x{im.size[1]}（{css} CSS px）  {out.stat().st_size} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
