#!/usr/bin/env python3
"""生成微信图文用的装饰底图（纸纹 / 花边带 / 角标）。

## 为什么装饰必须是「图片」

`references/20-wechat-html-constraints.md` 里记着两条实测结论，合起来决定了这件事：

1. 微信收几乎所有内联样式，**唯独把 `background-image` 指向外链的整条删掉**；
2. 换成**上传到微信图床后的 `mmbiz.qpic.cn` 链接**，`background-image` 连同
   `background-repeat` / `background-size` / `background-position` 一起完整保留。

所以花纹底、纸纹、花边这些「秀米感」的来源只有一条路：**先把图传进微信，再写进
`background-image`**。这个脚本负责前半段——把图确定性地画出来。

## 为什么用 Pillow 画而不是给 SVG

SVG 在这条链路上走不通：`background-image` 要的是一张能被图床接收的位图，
而内联 `<svg>` 虽然被微信保留，却只能当作元素塞进文档流——它没法当「底」重复平铺。
文字与几何形状用 Pillow 直接画，尺寸、颜色、平铺周期都是确定的。

## 平铺的接缝

`tile` 会被 `background-repeat:repeat` 使用，所以它**必须是四边无缝的**：
所有图案落在与画布边长成整除关系的坐标上，边缘的图案在下一块里继续。
画一个 48×48 的点阵，点在 (0,0) 与 (24,24) 各一个，平铺后就还原成 24px 的规整网格。
随手在边上加一道渐隐就会露馅成网格线。

## 用法

    python3 make_deco.py --skin paper --accent "#C0392B" -o 目录/
    python3 make_deco.py --list
    python3 make_deco.py --skin frame --accent "#1F4FD6" -o 目录/ --scale 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: 2 倍像素密度。手机上 1 CSS px = 2~3 物理像素，1 倍图在描边和斜角上会发虚。
SCALE = 2

#: CSS 尺寸（缩放前）。band 的宽度按微信正文宽度 375 减去左右各 16px 的页边距算，
#: 这样用 `background-size:100% <高>` 拉伸时几乎不产生形变。
TILE_CSS = 24
BAND_CSS_W = 343
BAND_CSS_H = 13


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """向 b 混 t（0=全 a，1=全 b）。"""
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def parse_hex(value: str) -> tuple[int, int, int]:
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"不是合法的十六进制颜色: {value!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % rgb


# ------------------------------------------------------------------ 三种底图


def make_tile(accent: tuple[int, int, int], scale: int = SCALE) -> "object":
    """无缝纸纹：极浅的底 + 规则点阵。对比度必须低到「像纸不像格子」。"""
    from PIL import Image, ImageDraw

    n = TILE_CSS * scale
    base = _mix(accent, (255, 255, 255), 0.972)      # 几乎白，只留一点色相
    dot = _mix(accent, (255, 255, 255), 0.885)       # 点比底深一点点
    im = Image.new("RGB", (n, n), base)
    d = ImageDraw.Draw(im)
    r = max(1, scale // 2)
    half = n // 2
    # 画在四个角与正中：平铺后每条接缝两侧各半个点，拼起来正好是一个整点。
    for cx, cy in ((0, 0), (half, 0), (0, half), (half, half)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dot)
    return im


def make_band(accent: tuple[int, int, int], scale: int = SCALE, flip: bool = False) -> "object":
    """花边带：一条细横线 + 居中的菱形。用 `background-size:100% <高>` 拉伸。

    两侧留空、只有中间有东西——这样即使被横向拉伸，菱形仍在正中，不会被拉变形。
    """
    from PIL import Image, ImageDraw

    w, h = BAND_CSS_W * scale, BAND_CSS_H * scale
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    line = _mix(accent, (255, 255, 255), 0.72)
    strong = _mix(accent, (255, 255, 255), 0.18)
    mid_y = h // 2

    gap = 11 * scale                                    # 菱形左右留出的空档
    x0, x1 = gap, w - gap
    for x in range(x0, x1):
        # 两端渐隐，避免色带在边缘出现硬切口
        t = min(x - x0, x1 - 1 - x) / max(1, (x1 - x0) / 2)
        d.point((x, mid_y), fill=_mix((255, 255, 255), line, min(1.0, t * 1.6 + 0.15)))

    cx, r = w // 2, 4 * scale
    d.polygon([(cx, mid_y - r), (cx + r, mid_y), (cx, mid_y + r), (cx - r, mid_y)], fill=strong)
    if flip:
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
    return im



#: 皮肤 → 需要哪几张底图。
#:
#: 这里**没有角标**。四角装饰要靠 `position:absolute` 定位，而微信把 `position`
#: 整条删掉（见 20-wechat-html-constraints.md 第 6 节）——删掉之后四张角标会
#: 依次堆在正文最前面，比没有装饰更糟。花边的四角改用 CSS `border-radius`。
SKINS = {
    "paper": ("tile",),            # 整篇纸纹底
    "frame": ("band", "band_flip"),  # 上下花边带（四角交给 border-radius）
    "full": ("tile", "band", "band_flip"),
}


def build(skin: str, accent_hex: str, out_dir: Path, scale: int = SCALE) -> dict[str, Path]:
    accent = parse_hex(accent_hex)
    wanted = SKINS[skin]
    out_dir.mkdir(parents=True, exist_ok=True)
    made: dict[str, Path] = {}

    for name in wanted:
        if name == "tile":
            im = make_tile(accent, scale)
        elif name == "band":
            im = make_band(accent, scale)
        elif name == "band_flip":
            im = make_band(accent, scale, flip=True)
        else:  # pragma: no cover — SKINS 与分支必须同步
            raise SystemExit(f"[ERROR] 未知底图: {name}")
        path = out_dir / f"{name}.png"
        im.save(path, optimize=True)
        made[name] = path
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make_deco", description="生成微信图文装饰底图")
    ap.add_argument("--skin", choices=sorted(SKINS), help="要生成哪一组")
    ap.add_argument("--accent", default="#C0392B", help="主色，用于把底图染成与主题一致")
    ap.add_argument("-o", "--output", help="输出目录")
    ap.add_argument("--scale", type=int, default=SCALE, help=f"像素密度，默认 {SCALE}")
    ap.add_argument("--list", action="store_true", help="列出可用的皮肤")
    args = ap.parse_args(argv)

    if args.list:
        for name in sorted(SKINS):
            print(f"  {name:<8} {' + '.join(SKINS[name])}")
        return 0

    if not args.skin or not args.output:
        ap.error("--skin 与 -o 都是必需的（或加 --list）")

    trace = build(args.skin, args.accent, Path(args.output), args.scale)
    for name, path in trace.items():
        print(f"[OK] {name}: {path}  {path.stat().st_size} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
