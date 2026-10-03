#!/usr/bin/env python3
"""按「纯色大字」封面形态规格合成封面（本次无生图模型，用户已确认用此方案）。

规格来自 06-visual.md 的形态表，逐条落实：
  - 2.35:1，长边 ≥ 900px（官方推荐 900×383，这里用 1408×599 出图更清晰）
  - 4–7 字钩子，极粗无衬线黑体，居中
  - 字高占画面高度 35–40%
  - 标题横向占画面宽度 ≥ 45%
  - 可在下方加一行字高为主标题 1/4 的副标题
  - 视觉元素不超过 3 个
  - 在 345×147 的信息流缩略图下仍可读（脚本会同时导出一张缩略图供核对）

用法：python3 make_cover.py <主标题> <副标题> <输出路径>
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1408, 599                      # 2.35:1，长边 1408 ≥ 900
BG = (244, 241, 234)                  # 暖白纸感，对应账号「简洁清新」的封面偏好
INK = (20, 24, 31)                    # 近黑墨色
ACCENT = (37, 99, 235)                # 默认极客蓝；可用 --accent 对齐所选排版配色
FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_INDEX = 1                        # Heiti SC Medium（无衬线黑体）

# 字高目标区间（占画面高度）
TITLE_H_RATIO = 0.375                 # 落在 35–40% 中点
SUB_H_RATIO = TITLE_H_RATIO / 4       # 副标题 = 主标题的 1/4


def load_font(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, px, index=FONT_INDEX)


def text_width(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    return draw.textbbox((0, 0), text, font=font)[2]


def fit_title(draw: ImageDraw.ImageDraw, text: str, target_h: int) -> tuple:
    """让字号逼近目标字高，同时保证横向占比 ≥ 45%。"""
    size = target_h
    font = load_font(size)
    # 中文按字高≈字号估算；横向不足就把字号顶到满足 45% 为止
    while text_width(draw, text, font) < W * 0.45 and size < int(H * 0.42):
        size += 4
        font = load_font(size)
    # 横向超出安全边距就收回来
    while text_width(draw, text, font) > W * 0.92 and size > 40:
        size -= 4
        font = load_font(size)
    return font, size


def main(argv: list[str] | None = None) -> int:
    argv = [a for a in (sys.argv[1:] if argv is None else argv) if a != "--"]
    out: Path | None = None
    positional: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--accent":
            if i + 1 >= len(argv):
                print("--accent 需要一个 #RRGGBB", file=sys.stderr); return 2
            hexv = argv[i + 1].lstrip("#")
            try:
                global ACCENT
                ACCENT = tuple(int(hexv[k:k+2], 16) for k in (0, 2, 4))
            except (ValueError, IndexError):
                print("--accent 需要形如 #9B2D30 的十六进制", file=sys.stderr); return 2
            i += 2
            continue
        if argv[i] in ("-o", "--output"):
            if i + 1 >= len(argv):
                print("-o 需要一个输出路径", file=sys.stderr)
                return 2
            out = Path(argv[i + 1])
            i += 2
            continue
        positional.append(argv[i])
        i += 1
    if len(positional) < 2 or out is None:
        print(__doc__)
        return 2
    title, subtitle = positional[0], positional[1]

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # 元素①：左上角一处极简色块（唯一的装饰，扁平化）
    draw.rectangle([64, 64, 64 + 56, 64 + 10], fill=ACCENT)

    # 元素②：主标题（极粗 → 用同色描边加字重）
    title_font, title_px = fit_title(draw, title, int(H * TITLE_H_RATIO))
    tw = text_width(draw, title, title_font)
    tx = (W - tw) / 2
    ty = H * 0.30
    draw.text((tx, ty), title, font=title_font, fill=INK,
              stroke_width=max(2, title_px // 28), stroke_fill=INK)

    # 元素③：副标题，字高为主标题的 1/4
    sub_font = load_font(int(H * SUB_H_RATIO))
    sw = text_width(draw, subtitle, sub_font)
    draw.text(((W - sw) / 2, ty + title_px * 1.22), subtitle, font=sub_font, fill=(92, 100, 112))

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")

    # 自检：信息流缩略图下是否还读得出
    thumb = img.resize((345, 147), Image.LANCZOS)
    thumb_path = out.with_name(out.stem + "-thumb345.png")
    thumb.save(thumb_path, "PNG")

    print(f"主标题 {len(title)} 字，字号 {title_px}px，字高占 {title_px / H:.0%}，"
          f"横向占 {tw / W:.0%}")
    print(f"已保存 {out}（{W}x{H}）与缩略图 {thumb_path}（345x147，用于核对可读性）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
