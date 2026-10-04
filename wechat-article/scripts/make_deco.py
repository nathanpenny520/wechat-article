#!/usr/bin/env python3
"""生成微信图文用的装饰底图（纸纹 / 花边带）。

## 为什么装饰必须是「图片」

`references/20-wechat-html-constraints.md` 里记着两条实测结论，合起来决定了这件事：

1. 微信收几乎所有内联样式，**唯独把 `background-image` 指向外链的整条删掉**；
2. 换成**上传到微信图床后的 `mmbiz.qpic.cn` 链接**，`background-image` 连同
   `background-repeat` / `background-size` / `background-position` 一起完整保留。

所以花纹底、纸纹、花边这些「秀米感」的来源只有一条路：**先把图传进微信，再写进
`background-image`**。这个脚本负责前半段——把图确定性地画出来。

## 两个正交的维度

底子（texture）和花边（frame）是两件独立的事，所以拆成两个参数而不是一串皮肤名：

| 维度 | 取值 | 观感 |
|---|---|---|
| `texture` | `dot` / `grid` / `kraft` / `none` | 点阵纸 / 方格纸 / 牛皮纸 / 不铺底 |
| `frame` | `none` / `single` / `double` | 无框 / 单色花边 / 双色花边 |

`SKINS` 只是这两维的常用组合，方便一次说清；`--texture` / `--frame` 可以覆盖它。

## 平铺的接缝

铺底图会被 `background-repeat:repeat` 使用，所以它**必须是四边无缝的**：
图案落在与画布边长成整除关系的坐标上，或者用环绕绘制把越过边界的笔画补到另一侧。
牛皮纸那种随机纤维点尤其要注意——不环绕绘制，平铺后会出现「点只落在格子中间」的破绽。

## 用法

    python3 make_deco.py --skin full --accent "#C0392B" -o 目录/
    python3 make_deco.py --texture kraft --frame double --accent "#1F4FD6" -o 目录/
    python3 make_deco.py --list
"""

from __future__ import annotations

import argparse
from pathlib import Path

#: 2 倍像素密度。手机上 1 CSS px = 2~3 物理像素，1 倍图在描边和斜角上会发虚。
SCALE = 2

#: CSS 尺寸（缩放前）。花边带的宽度按微信正文宽度 375 减去左右各 16px 的页边距算，
#: 这样用 `background-size:100% <高>` 拉伸时几乎不产生形变。
TILE_CSS = 24
BAND_CSS_W = 343
BAND_CSS_H = 13

TEXTURES = ("dot", "grid", "kraft", "none")
FRAMES = ("none", "single", "double")

#: 皮肤预设：（底子，花边）。用户可用 --texture / --frame 各自覆盖。
SKINS: dict[str, tuple[str, str]] = {
    "paper": ("dot", "none"),      # 轻点阵纸
    "grid": ("grid", "none"),      # 方格纸，比 paper 明显
    "kraft": ("kraft", "none"),    # 牛皮纸质感
    "frame": ("none", "single"),   # 只加框
    "double": ("none", "double"),  # 只加双色框
    "full": ("dot", "single"),     # 默认：轻点阵 + 单色框
    "graph": ("grid", "single"),   # 方格纸 + 单色框
    "craft": ("kraft", "double"),  # 牛皮纸 + 双色框，最重的一档
}


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


# ------------------------------------------------------------------ 底子


def make_dot(accent: tuple[int, int, int], scale: int = SCALE) -> "object":
    """轻点阵纸：极浅的底 + 规则圆点。对比度必须低到「像纸不像格子」。"""
    from PIL import Image, ImageDraw

    n = TILE_CSS * scale
    base = _mix(accent, (255, 255, 255), 0.972)      # 几乎白，只留一点色相
    dot = _mix(accent, (255, 255, 255), 0.885)       # 点比底深一点点
    im = Image.new("RGB", (n, n), base)
    d = ImageDraw.Draw(im)
    r = max(1, scale // 2)
    half = n // 2
    # 画在四角与正中：平铺后每条接缝两侧各半个点，拼起来正好是一个整点。
    for cx, cy in ((0, 0), (half, 0), (0, half), (half, half)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dot)
    return im


def make_grid(accent: tuple[int, int, int], scale: int = SCALE) -> "object":
    """方格纸：主格线压在画布边缘、次格线在正中，平铺后就是主次分明的方格。

    两条线都在整除位置上，所以不会出现粗细不匀的假格线。
    """
    from PIL import Image, ImageDraw

    n = TILE_CSS * scale
    base = _mix(accent, (255, 255, 255), 0.955)       # 方格纸的底比点阵纸略深
    major = _mix(accent, (255, 255, 255), 0.80)
    minor = _mix(accent, (255, 255, 255), 0.895)
    im = Image.new("RGB", (n, n), base)
    d = ImageDraw.Draw(im)
    half = n // 2
    w = max(1, scale // 2)
    d.line([(0, 0), (n - 1, 0)], fill=major, width=w)
    d.line([(0, 0), (0, n - 1)], fill=major, width=w)
    d.line([(half, 0), (half, n - 1)], fill=minor, width=w)
    d.line([(0, half), (n - 1, half)], fill=minor, width=w)
    return im


#: 牛皮纸的本色（暖黄褐）。不随主色走——牛皮纸的识别特征是「暖」。
KRAFT_PAPER = (214, 186, 150)


def make_kraft(accent: tuple[int, int, int], scale: int = SCALE) -> "object":
    """牛皮纸：暖调底 + 细碎纤维点。

    底色以**牛皮纸本色**为主，主色只掺 8%。早先是「主色掺 55% 再往白里提」，
    遇到冷色主色（靛蓝、石青）整张底就变成灰紫——那是灰纸，不是牛皮纸。

    纤维点是随机撒的，所以必须**环绕绘制**——越过边界的点要在对侧再画一次，
    否则平铺后会出现规整的「点只出现在格子中间」的破绽。
    随机数用固定种子，保证同一主色每次生成逐字节一致（目录名按指纹去重）。
    """
    import random

    from PIL import Image, ImageDraw

    n = TILE_CSS * scale
    tinted = _mix(KRAFT_PAPER, accent, 0.08)          # 只沾一点主色的色相
    base = _mix(tinted, (255, 255, 255), 0.86)
    fleecen = _mix(_mix(KRAFT_PAPER, (140, 108, 66), 0.45), (255, 255, 255), 0.70)
    im = Image.new("RGB", (n, n), base)
    d = ImageDraw.Draw(im)
    rnd = random.Random(20261004)
    for _ in range(n * 4):
        x, y = rnd.randrange(n), rnd.randrange(n)
        for dx in (-n, 0, n):
            for dy in (-n, 0, n):
                d.point((x + dx, y + dy), fill=fleecen)
    return im


TEXTURE_BUILDERS = {"dot": make_dot, "grid": make_grid, "kraft": make_kraft}


# ------------------------------------------------------------------ 花边带


def make_band(accent: tuple[int, int, int], scale: int = SCALE, flip: bool = False) -> "object":
    """单色花边带：一条细横线 + 居中的菱形。

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


def make_band_double(accent: tuple[int, int, int], scale: int = SCALE,
                     flip: bool = False) -> "object":
    """双色花边带：上粗下细两条线，中间一排大小方块。

    比单色带更重，所以配合 `kraft` / `grid` 这类更明显的底子。两个色都由主色调出来
    （次色 = 主色向白混 0.5），不引入第二套配色。
    """
    from PIL import Image, ImageDraw

    w, h = BAND_CSS_W * scale, BAND_CSS_H * scale * 2   # 双色带比单色带高一倍
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    strong = _mix(accent, (255, 255, 255), 0.16)
    second = _mix(accent, (255, 255, 255), 0.50)

    thick = 3 * scale
    thin = max(1, scale // 2)
    top_y = thick // 2
    bot_y = h - thin - 1
    for x in range(w):
        t = min(x, w - 1 - x) / max(1, w / 2)
        fade = min(1.0, t * 2.0 + 0.10)
        d.point((x, top_y), fill=_mix((255, 255, 255), strong, fade))
        d.point((x, bot_y), fill=_mix((255, 255, 255), second, fade))

    # 中间一排方块：大方块主色、小方块次色，间隔固定 → 拉伸后仍等距
    cx = w // 2
    step = 9 * scale
    for i in range(-3, 4):
        x = cx + i * step
        if not (8 * scale < x < w - 8 * scale):
            continue
        r = 4 * scale if i == 0 else 2 * scale
        d.rectangle([x - r, h // 2 - r, x + r, h // 2 + r],
                    fill=strong if i == 0 else second)
    if flip:
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
    return im


# ------------------------------------------------------------------ 组装


def resolve(skin: str, texture: str | None, frame: str | None) -> tuple[str, str]:
    """把皮肤预设与显式覆盖合成 (texture, frame)。"""
    if skin not in SKINS:
        raise SystemExit(f"[ERROR] 未知皮肤 {skin}；可选 {'/'.join(sorted(SKINS))}")
    t, f = SKINS[skin]
    if texture:
        if texture not in TEXTURES:
            raise SystemExit(f"[ERROR] texture 只能是 {'/'.join(TEXTURES)}")
        t = texture
    if frame:
        if frame not in FRAMES:
            raise SystemExit(f"[ERROR] frame 只能是 {'/'.join(FRAMES)}")
        f = frame
    return t, f


def assets_for(texture: str, frame: str) -> list[str]:
    out: list[str] = []
    if texture != "none":
        out.append("tile")
    if frame == "single":
        out += ["band", "band_flip"]
    elif frame == "double":
        out += ["band2", "band2_flip"]
    return out


def band_height(frame: str, scale: int = SCALE) -> int:
    """花边带在 HTML 里的 CSS 高度，必须与画出来的比例一致，否则菱形会被拉扁。"""
    return BAND_CSS_H * (2 if frame == "double" else 1)


def build(texture: str, frame: str, accent_hex: str, out_dir: Path,
          scale: int = SCALE) -> dict[str, Path]:
    accent = parse_hex(accent_hex)
    out_dir.mkdir(parents=True, exist_ok=True)
    made: dict[str, Path] = {}

    for name in assets_for(texture, frame):
        if name == "tile":
            im = TEXTURE_BUILDERS[texture](accent, scale)
        elif name == "band":
            im = make_band(accent, scale)
        elif name == "band_flip":
            im = make_band(accent, scale, flip=True)
        elif name == "band2":
            im = make_band_double(accent, scale)
        elif name == "band2_flip":
            im = make_band_double(accent, scale, flip=True)
        else:  # pragma: no cover — assets_for 与分支必须同步
            raise SystemExit(f"[ERROR] 未知底图: {name}")
        path = out_dir / f"{name}.png"
        im.save(path, optimize=True)
        made[name] = path
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make_deco", description="生成微信图文装饰底图")
    ap.add_argument("--skin", choices=sorted(SKINS), default="full", help="皮肤预设")
    ap.add_argument("--texture", choices=TEXTURES, help="覆盖预设里的底子")
    ap.add_argument("--frame", choices=FRAMES, help="覆盖预设里的花边")
    ap.add_argument("--accent", default="#C0392B", help="主色，用于把底图染成与主题一致")
    ap.add_argument("-o", "--output", help="输出目录")
    ap.add_argument("--scale", type=int, default=SCALE, help=f"像素密度，默认 {SCALE}")
    ap.add_argument("--list", action="store_true", help="列出皮肤与两个维度")
    args = ap.parse_args(argv)

    if args.list:
        print("皮肤（底子 × 花边）：")
        for name, (t, f) in sorted(SKINS.items()):
            print(f"  {name:<8} {t:<6} × {f}")
        print(f"\n底子 --texture: {'/'.join(TEXTURES)}")
        print(f"花边 --frame:   {'/'.join(FRAMES)}")
        return 0

    if not args.output:
        ap.error("-o 是必需的（或加 --list）")

    texture, frame = resolve(args.skin, args.texture, args.frame)
    trace = build(texture, frame, args.accent, Path(args.output), args.scale)
    print(f"[OK] 皮肤 {args.skin} → 底子 {texture}、花边 {frame}")
    for name, path in trace.items():
        print(f"     {name}: {path}  {path.stat().st_size} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
