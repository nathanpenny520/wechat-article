#!/usr/bin/env python3
"""中文字体发现。Pillow 读不到字体时不会报错，只会画出方框——所以必须显式探测。

`make_cover.py` 早先直接写死 `/System/Library/Fonts/STHeiti Medium.ttc`，
在 macOS 上没问题，换到 Linux / Windows 就整张图变成豆腐块。
这里按平台列出候选，返回第一个**真的能加载**的。
"""

from __future__ import annotations

import functools
from pathlib import Path

#: (路径, ttc 内的字体索引)。字重从粗到细。
CANDIDATES: list[tuple[str, int]] = [
    # macOS
    ("/System/Library/Fonts/STHeiti Medium.ttc", 1),          # Heiti SC Medium
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
    # Linux
    ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/usr/share/fonts/truetype/arphic/uming.ttc", 0),
    # Windows
    ("C:/Windows/Fonts/msyh.ttc", 0),                          # 微软雅黑
    ("C:/Windows/Fonts/simhei.ttf", 0),                        # 黑体
    ("C:/Windows/Fonts/simsun.ttc", 0),                        # 宋体
]


@functools.lru_cache(maxsize=64)
def _probe(path: str, index: int) -> bool:
    try:
        from PIL import ImageFont

        ImageFont.truetype(path, 24, index=index)
        return True
    except Exception:  # noqa: BLE001 — 缺文件、格式不支持、索引越界都走这里
        return False


def find_cjk_font() -> tuple[str, int]:
    """返回 (字体路径, 索引)。一个都找不到时返回空串，由调用方决定怎么降级。"""
    for path, index in CANDIDATES:
        if Path(path).exists() and _probe(path, index):
            return path, index
    return "", 0


def load(px: int):
    """按像素字号加载 CJK 字体；找不到可用字体时抛出一个说人话的错误。"""
    from PIL import ImageFont

    path, index = find_cjk_font()
    if not path:
        raise SystemExit(
            "[ERROR] 找不到可用的中文字体，图上会全是方框。\n"
            "         已尝试的位置见 scripts/wxfont.py 的 CANDIDATES；\n"
            "         装一个即可，例如 Debian/Ubuntu: apt-get install fonts-noto-cjk"
        )
    return ImageFont.truetype(path, px, index=index)
