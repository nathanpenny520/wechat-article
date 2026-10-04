#!/usr/bin/env python3
"""给已排版的正文加「秀米那种背景」——纸纹底与花边框。

## 为什么必须绕一圈

微信把 `background-image` 指向**外链**的整条属性删掉，但保留指向
**自己图床（`mmbiz.qpic.cn`）** 的那些，连同 `background-repeat` /
`background-size` / `background-position` 一起（2026-10-04 探针实测，
见 `references/20-wechat-html-constraints.md` 第 3 节）。

所以要做出花纹底 / 纸纹 / 花边，链路必然是三步：
**本地画图 → 传进微信图床换链接 → 写进 `background-image`**。
这个脚本把后两步接起来。

## 为什么装饰只加在「外层容器」上

正文内部的标题、卡片、编号由模版的 `h2-deco` / 各类组件渲染，
其中 `h2-deco` 会把 `<h2>` 包进一个 `display:flex` 的行里。事后往
`<h2` 前面插一条花边，插进去的是 flex 行内部，会把版式搞坏。
外层容器（`format` 产物的第一个 `<section>`）是稳定锚点，所以装饰
一律作用在这一层：纸纹做底、花边做框。**不猜结构，只包一层。**

## 用法

    python3 wxdeco.py article.html -o article-deco.html --skin full
    python3 wxdeco.py article.html -o preview.html --skin full --no-upload   # data: URI，本地看效果
    python3 wxdeco.py article.html -o article-deco.html --skin paper --accent "#2E7BF6"
    python3 wxdeco.py article.html -o out.html --skin full --json

`--no-upload` 把底图内联成 `data:` URI：不发网络请求、不消耗图床额度，
用来在本地截图核对观感。要进草稿箱时必须去掉它——微信不认 `data:` 背景。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_deco  # noqa: E402
import wxenv  # noqa: E402

#: 换链缓存。底图只取决于「皮肤 + 主色」，同一套配色在多篇文章间可以复用同一条
#: 图床链接——重复上传既慢又白占图床额度。
CACHE_NAME = "deco-cache.json"

#: 正文宽度下，花边框的内边距与圆角。竖向外边距留给外层容器自己的 padding。
FRAME_PAD = "12px 10px"
FRAME_RADIUS = "20px"

_HEX = re.compile(r"#([0-9A-Fa-f]{6})")
_TAG_OPEN = re.compile(r"<section\b[^>]*>", re.I)


# ------------------------------------------------------------------ HTML 拆分


def split_document(html: str) -> tuple[str, str, str]:
    """切成 (前, 正文, 后)。aws 产物是裸片段，wx 产物是整页文档，两者都要吃。"""
    m = re.search(r"(<body\b[^>]*>)(.*?)(</body>)", html, re.S | re.I)
    if m:
        start = m.start(2)
        end = m.end(2)
        return html[:start], html[start:end], html[end:]
    return "", html, ""


def _style_attr(html: str, tag: re.Match) -> tuple[int, int]:
    """在开标签里定位 style 属性值的区间；没有就返回 (-1, -1)。"""
    seg = tag.group(0)
    m = re.search(r"""style\s*=\s*("([^"]*)"|'([^']*)')""", seg, re.I)
    if not m:
        return -1, -1
    if m.group(2) is not None:
        return tag.start() + m.start(2), tag.start() + m.end(2)
    return tag.start() + m.start(3), tag.start() + m.end(3)


def add_style(html: str, extra: str, *, tag: str = "section") -> str:
    """给第一个匹配的标签的 style 追加声明；没有 style 就补一个。"""
    m = re.search(rf"<{tag}\b[^>]*>", html, re.I)
    if not m:
        raise SystemExit(f"[ERROR] 找不到 <{tag}>，无法挂装饰（产物结构不符合预期）")
    a, b = _style_attr(html, m)
    if a < 0:
        return html[:m.end() - 1] + f' style="{extra}"' + html[m.end() - 1:]
    body = html[a:b]
    sep = "" if not body.strip() or body.rstrip().endswith(";") else "; "
    return html[:a] + body + sep + extra + html[b:]


def wrap_fragment(fragment: str, wrapper_style: str) -> str:
    return f'<section style="{wrapper_style}">{fragment}</section>'


def band_section(url: str, height_css: int) -> str:
    """一条花边带：图片按容器宽度拉伸、不重复，所以横向不会有平铺接缝。"""
    return (
        f'<section style="height:{height_css}px; background-image:url({url}); '
        f'background-repeat:no-repeat; background-size:100% {height_css}px; '
        f'background-position:center center;"></section>'
    )


# ------------------------------------------------------------------ 主色探测


def detect_accent(html: str) -> tuple[tuple[int, int, int], str]:
    """从产物里认出模版主色。

    装饰色必须跟主题一致，否则「好看的底」会变成「第二套配色」。产物里已经有
    模版渲进去的全部色值，直接取其中出现最多、且是**彩色**的那个即可——
    灰、近黑、近白都被排除，它们在产物里出现得最多但都不是主色。

    返回 (rgb, 来源说明)。
    """
    counts: dict[str, int] = {}
    for m in _HEX.finditer(html):
        key = m.group(1).upper()
        counts[key] = counts.get(key, 0) + 1
    best, best_score = None, -1.0
    for key, n in counts.items():
        r, g, b = make_deco.parse_hex(key)
        mx, mn = max(r, g, b), min(r, g, b)
        sat = 0.0 if mx == 0 else (mx - mn) / mx
        val = mx / 255
        # 判「中性色」只看饱和度：近白（#F7EEEE，sat 0.04）与近黑（#111111，sat 0）
        # 都会被它滤掉。**不能再用亮度加一条 `val > 0.95`** —— 那会把 #2E7BF6 这种
        # 又亮又饱和的正蓝也丢掉（max 通道 246/255 = 0.965），主色一丢就退回兜底红，
        # 装饰与主题当场脱节。
        if sat < 0.15 or val < 0.15:
            continue
        # 频次优先；同频次取更饱和的那个（更像「主色」而不是「强调色的浅底」）
        score = n + sat
        if score > best_score:
            best, best_score = key, score
    if best is None:
        return make_deco.parse_hex("#C0392B"), "兜底（产物里没找到彩色）"
    return make_deco.parse_hex(best), f"产物中最常见的彩色 #{best}（出现 {counts[best]} 次）"


# ------------------------------------------------------------------ 换链


class Uploader:
    """底图 → 微信图床链接，带缓存。只在真的要上传时才去取 token。"""

    def __init__(self, cache_path: Path, use_upload: bool) -> None:
        self.cache_path = cache_path
        self.use_upload = use_upload
        self.cache: dict[str, str] = {}
        self.hits = 0
        self.uploaded = 0
        if cache_path.is_file():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.cache = {}
        self._token: str | None = None
        self._publish = None

    def _ensure_publish(self):
        if self._publish is not None:
            return self._publish
        pub_dir = wxenv.SKILL_ROOT / "scripts" / "aws" / "aws-wechat-article-publish" / "scripts"
        sys.path.insert(0, str(pub_dir))
        import publish as P  # noqa: WPS433

        self._publish = P
        return P

    def _get_token(self) -> str:
        if self._token:
            return self._token
        P = self._ensure_publish()
        cfg = P.load_repo_config()
        env = P._load_env_map()
        slot = P.wechat_slot(cfg, env, int(cfg.get("wechat_publish_slot", 1) or 1))
        missing = P.missing_wechat_slot_fields(slot)
        if missing:
            raise SystemExit(
                f"[ERROR] 微信槽位缺少 {', '.join(missing)}，无法上传装饰底图。\n"
                "         想本地先看效果就加 --no-upload（底图内联成 data: URI）。"
            )
        self._token = P.get_access_token(slot["appid"], slot["appsecret"])
        return self._token

    def url_for(self, path: Path) -> str:
        if not self.use_upload:
            # data: URI —— 本地截图能渲染，但不能进草稿箱（微信不认）。
            return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:20]
        if digest in self.cache:
            self.hits += 1
            return self.cache[digest]
        P = self._ensure_publish()
        url = P.upload_content_image(self._get_token(), str(path))
        if not str(url).startswith("http"):
            raise SystemExit(f"[ERROR] 底图上传失败: {url}")
        self.cache[digest] = url
        self.uploaded += 1
        self.flush()
        return url

    def flush(self) -> None:
        if not self.use_upload:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


# ------------------------------------------------------------------ 主流程


def decorate(html: str, skin: str, accent_hex: str, urls: dict[str, str]) -> str:
    head, fragment, tail = split_document(html)
    if not fragment.strip():
        raise SystemExit("[ERROR] 正文是空的，没有可装饰的内容")

    paper = make_deco._mix(make_deco.parse_hex(accent_hex), (255, 255, 255), 0.972)
    soft = make_deco._mix(make_deco.parse_hex(accent_hex), (255, 255, 255), 0.66)
    inner = fragment

    if skin in ("frame", "full"):
        top = band_section(urls["band"], make_deco.BAND_CSS_H)
        bottom = band_section(urls["band_flip"], make_deco.BAND_CSS_H)
        inner = top + inner + bottom

    if skin in ("paper", "full"):
        bg = (f'background-image:url({urls["tile"]}); background-repeat:repeat; '
              f'background-size:{make_deco.TILE_CSS}px {make_deco.TILE_CSS}px; '
              f'background-color:{make_deco.to_hex(paper)};')
        if skin == "full":
            # 纸纹与花边同在一层：外层既是框也是纸，正文里不再嵌一层背景。
            wrapper = (f'border:1px solid {make_deco.to_hex(soft)}; '
                       f'border-radius:{FRAME_RADIUS}; padding:{FRAME_PAD}; {bg}')
            inner = wrap_fragment(inner, wrapper)
        else:
            inner = add_style(inner, bg)
    elif skin == "frame":
        wrapper = (f'border:1px solid {make_deco.to_hex(soft)}; '
                   f'border-radius:{FRAME_RADIUS}; padding:{FRAME_PAD};')
        inner = wrap_fragment(inner, wrapper)

    return head + inner + tail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wxdeco",
        description="给已排版正文加纸纹底 / 花边框（底图上传到微信图床再写进 background-image）",
    )
    ap.add_argument("input", help="排版产物 HTML")
    ap.add_argument("-o", "--output", required=True, help="输出 HTML")
    ap.add_argument("--skin", choices=sorted(make_deco.SKINS), default="full",
                    help="装饰皮肤，默认 full（纸纹 + 花边框）")
    ap.add_argument("--accent", help="主色；不给则从产物里自动认模版主色")
    ap.add_argument("--no-upload", action="store_true",
                    help="不发上传请求，底图内联成 data: URI（仅用于本地预览）")
    ap.add_argument("--assets-dir", help="底图落盘目录，默认状态目录下 deco/<指纹>/")
    ap.add_argument("--cache", help=f"换链缓存路径，默认状态目录下 {CACHE_NAME}")
    ap.add_argument("--no-check", action="store_true", help="跳过产物微信兼容门禁")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = ap.parse_args(argv)

    src = Path(args.input)
    if not src.is_file():
        print(f"[ERROR] 文件不存在: {src}", file=sys.stderr)
        return 2
    html = src.read_text(encoding="utf-8")

    if args.accent:
        accent = make_deco.parse_hex(args.accent)
        accent_note = f"命令行指定 {make_deco.to_hex(accent)}"
    else:
        accent, accent_note = detect_accent(html)
    accent_hex = make_deco.to_hex(accent)

    fingerprint = hashlib.sha256(f"{args.skin}|{accent_hex}|{make_deco.SCALE}".encode()).hexdigest()[:12]
    assets_dir = Path(args.assets_dir) if args.assets_dir else (
        wxenv.state_home() / "deco" / fingerprint)
    made = make_deco.build(args.skin, accent_hex, assets_dir)

    cache_path = Path(args.cache) if args.cache else (wxenv.state_home() / CACHE_NAME)
    uploader = Uploader(cache_path, use_upload=not args.no_upload)
    urls = {name: uploader.url_for(path) for name, path in made.items()}
    uploader.flush()

    out_html = decorate(html, args.skin, accent_hex, urls)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(out_html, encoding="utf-8")

    gate_code = 0
    gate_note = "未检查"
    if not args.no_check:
        import wxguard  # noqa: WPS433

        findings = wxguard.gate(out_html, profile="generic")
        errors = [f for f in findings if f.get("level") == "ERROR"]
        warns = [f for f in findings if f.get("level") != "ERROR"]
        if errors:
            gate_code = 5
            gate_note = f"门禁未通过（{len(errors)} 项 ERROR）"
            for f in errors:
                print(f"[ERROR] {f['rule']}: {f['message']}\n        {f['sample']}", file=sys.stderr)
        else:
            gate_note = f"通过微信兼容门禁（{len(warns)} 项 WARN）" if warns else "通过微信兼容门禁"

    result = {
        "output": str(out),
        "skin": args.skin,
        "accent": accent_hex,
        "accent_source": accent_note,
        "assets": {k: str(v) for k, v in made.items()},
        "uploaded": uploader.uploaded,
        "cache_hits": uploader.hits,
        "inline": args.no_upload,
        "gate": gate_note,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        mode = "data: URI 内联" if args.no_upload else f"图床换链（新传 {uploader.uploaded}、命中缓存 {uploader.hits}）"
        print(f"[OK] {out}")
        print(f"     皮肤 {args.skin}　主色 {accent_hex}（{accent_note}）")
        print(f"     底图 {len(made)} 张 → {mode}")
        if args.no_upload:
            print("     ⚠ data: URI 只用于本地预览，进草稿箱前必须去掉 --no-upload")
        if gate_code:
            print(f"[WARN] {gate_note}", file=sys.stderr)
    return gate_code


if __name__ == "__main__":
    raise SystemExit(main())
