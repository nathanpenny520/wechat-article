#!/usr/bin/env python3
"""把微信公众号官方文档镜像到本地，供离线检索。

## 为什么要镜像

写作与发布涉及大量「官方怎么规定的」细节：接口路径、字段上限、错误码、频率限制。
这些以前靠探针一条条试出来（见 `references/20-wechat-html-constraints.md`），
试出来的结论散在文档里、且只覆盖试过的那些。把官方文档拉一份到本地，
agent 就能在离线状态下先查规定、再决定要不要探。

## 为什么不把镜像提交进仓库

文档内容版权归腾讯所有。把它复制进本仓库分发是不合适的，所以镜像落在**状态目录**
（`$WXARTICLE_HOME/wechat-docs/`），不进版本库；仓库里只放这个抓取脚本，
谁需要谁自己拉一份。仓库内另有 `references/22-wechat-api-reference.md`——
那是**我们自己写的**、只覆盖本流水线真正依赖的规定摘要。

## 站点结构

`developers.weixin.qq.com` 是 Vue 单页应用，但服务端渲染出了完整链接与正文，
所以按普通 BFS 抓即可。正文容器是 `div.content.custom`（页面的导航树在同一层之外，
不能拿「文本最多的 div」当判据——那样会把左侧 170 多项导航一起抓进来）。

## 用法

    python3 wechat_docs.py fetch [--limit N] [--delay 0.3] [--force]
    python3 wechat_docs.py list
    python3 wechat_docs.py search "draft/update"
    python3 wechat_docs.py show subscription/api/draftbox/draftmanage/api_draft_update
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wxenv  # noqa: E402

BASE = "https://developers.weixin.qq.com"
SEEDS = [
    "/doc/subscription/guide/",
    "/doc/subscription/api/",
]
#: 只抓公众号（原订阅号）这一支。同一站点还有小程序 / 支付 / 企业微信等，
#: 与本流水线无关，跟着爬会平白多出几千页。
SCOPE = "/doc/subscription/"
UA = "Mozilla/5.0 (compatible; wechat-article-skill/1.0; +local-docs-mirror)"
MAX_PAGES_DEFAULT = 400


def docs_root() -> Path:
    return wxenv.state_home() / "wechat-docs"


def _get(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    # 站点是 UTF-8；不显式指定时 urllib 会按 latin-1 处理，中文全成乱码。
    return raw.decode("utf-8", "replace")


# ------------------------------------------------------------------ 正文抽取


def _cell_text(cell) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).replace("|", "\\|")


def html_to_markdown(html: str, url: str) -> str:
    """把正文容器转成 Markdown。只覆盖文档站真正用到的几种块。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("div.content.custom") or soup.select_one("div.page-inner")
    if node is None:
        return ""
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else url

    out: list[str] = [
        f"<!-- 来源: {url} -->",
        "<!-- 版权归腾讯所有；本文件为本地检索用的离线副本，以线上原文为准 -->",
        "",
    ]
    # 页面 `<title>` 与正文 h1 往往重复（前者还带站点后缀），所以标题以正文 h1 为准；
    # 正文没有 h1（少见）时才用 `<title>` 兜一个。
    has_h1 = node.find("h1") is not None
    if not has_h1:
        out += [f"# {title}", ""]

    def emit_text(el, prefix: str = "") -> None:
        text = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if text:
            out.append(prefix + text)
            out.append("")

    for el in node.find_all(["h1", "h2", "h3", "h4", "p", "pre", "table", "ul", "ol", "blockquote"]):
        # 表格与列表会包含 p，避免重复输出内层
        if el.find_parent(["table", "ul", "ol", "blockquote"]) is not None and el.name == "p":
            continue
        name = el.name
        if name in ("h1", "h2", "h3", "h4"):
            emit_text(el, "#" * {"h1": 1, "h2": 2, "h3": 3, "h4": 4}[name] + " ")
        elif name == "pre":
            code = el.get_text("\n", strip=False).rstrip()
            out += ["```", code, "```", ""]
        elif name == "blockquote":
            emit_text(el, "> ")
        elif name == "table":
            rows = el.find_all("tr")
            if not rows:
                continue
            for i, tr in enumerate(rows):
                cells = [_cell_text(c) for c in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                out.append("| " + " | ".join(cells) + " |")
                if i == 0:
                    out.append("|" + "---|" * len(cells))
            out.append("")
        elif name in ("ul", "ol"):
            for i, li in enumerate(el.find_all("li", recursive=False), 1):
                text = re.sub(r"\s+", " ", li.get_text(" ", strip=True))
                if text:
                    out.append(f"{i}. {text}" if name == "ol" else f"- {text}")
            out.append("")

    # 相邻空行折叠
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def page_to_path(url: str) -> Path:
    """URL → 镜像里的相对路径。目录页存成 index.md。"""
    rel = url[len(BASE):].lstrip("/")
    rel = re.sub(r"\.html?$", "", rel)
    rel = re.sub(r"[^A-Za-z0-9/._-]", "_", rel)
    if rel.endswith("/") or not rel.split("/")[-1]:
        rel += "index"
    return Path(rel + ".md")


def _links(html: str, current: str) -> list[str]:
    """抽出同一支下的所有文档链接，转成绝对 URL 并去重。"""
    found = set()
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith("http"):
            if not href.startswith(BASE):
                continue
            path = href[len(BASE):]
        else:
            path = href
        path = path.split("#")[0].split("?")[0]
        if not path.startswith(SCOPE):
            continue
        if not re.search(r"(/|\.html?)$", path):
            continue
        found.add(BASE + path)
    return sorted(found)


# ------------------------------------------------------------------ 抓取


def cmd_fetch(args: argparse.Namespace) -> int:
    root = docs_root()
    root.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    queue: list[str] = [BASE + s for s in SEEDS]
    saved = skipped = failed = 0
    started = time.time()

    while queue and saved + skipped < args.limit:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        dest = root / page_to_path(url)

        if dest.is_file() and not args.force and dest.stat().st_size > 200:
            skipped += 1
            # 已抓过的页面仍然要解析它的链接，否则断点续抓会漏掉后面的页
            try:
                html = _get(url)
            except Exception:  # noqa: BLE001
                continue
        else:
            try:
                html = _get(url)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
                failed += 1
                print(f"[WARN] 抓取失败 {url}: {e}", file=sys.stderr)
                continue
            md = html_to_markdown(html, url)
            if len(md) < 120:
                # 目录页或空页：只当作链接来源，不落盘
                pass
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(md, encoding="utf-8")
                saved += 1

        for link in _links(html, url):
            if link not in seen:
                queue.append(link)
        if not dest.is_file() or args.force:
            time.sleep(args.delay)

    write_index(root)
    print(f"[OK] 镜像目录: {root}")
    print(f"     新抓 {saved} 页、跳过已存在 {skipped} 页、失败 {failed} 页"
          f"、用时 {time.time() - started:.0f}s")
    print(f"     入口索引: {root / 'INDEX.md'}")
    print("     版权归腾讯所有，仅作本地检索，以线上原文为准。")
    return 0 if saved or skipped else 1


def write_index(root: Path) -> None:
    files = sorted(p for p in root.rglob("*.md") if p.name != "INDEX.md")
    lines = [
        "# 微信公众号官方文档 · 本地镜像索引",
        "",
        "> 来源 <https://developers.weixin.qq.com/doc/subscription/>　"
        f"页面数 **{len(files)}**",
        ">",
        "> 内容版权归腾讯所有；本目录为本地检索用副本，**不进版本库**，以线上原文为准。",
        "> 每个文件首行标注了原始 URL。重新抓取：`wxart docs fetch`。",
        "",
    ]
    for path in files:
        rel = path.relative_to(root).with_suffix("")
        lines.append(f"- [{rel}]({rel}.md)")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ 检索


def _iter_files() -> list[Path]:
    root = docs_root()
    if not root.is_dir():
        raise SystemExit(
            f"[ERROR] 还没有本地镜像（{root}）。先跑 `wxart docs fetch`。\n"
            "         只想知道关键规定的话，仓库里 references/22-wechat-api-reference.md 有摘要。"
        )
    return sorted(p for p in root.rglob("*.md") if p.name != "INDEX.md")


def cmd_list(args: argparse.Namespace) -> int:
    files = _iter_files()
    for path in files:
        rel = path.relative_to(docs_root()).with_suffix("")
        if args.filter and args.filter not in str(rel):
            continue
        print(rel)
    print(f"\n共 {len(files)} 页")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    files = _iter_files()
    pattern = re.compile(args.keyword, re.I)
    hits = 0
    for path in files:
        body = path.read_text(encoding="utf-8")
        matches = list(pattern.finditer(body))
        if not matches:
            continue
        hits += 1
        rel = path.relative_to(docs_root()).with_suffix("")
        print(f"\n■ {rel}　（{len(matches)} 处）")
        if args.quiet:
            continue
        for m in matches[: args.max_per_file]:
            line_no = body.count("\n", 0, m.start()) + 1
            line = body.splitlines()[line_no - 1].strip()
            print(f"   {line_no}: {line[:160]}")
    print(f"\n命中 {hits} 页 / 共 {len(files)} 页")
    return 0 if hits else 1


def cmd_show(args: argparse.Namespace) -> int:
    root = docs_root().resolve()
    raw = args.path.removesuffix(".md")
    # 镜像里的路径带着 `doc/` 前缀（它来自 URL 路径），但用户更可能只写 `subscription/…`，
    # 所以两种都试一下，别让人为了一个前缀去翻 list。
    for cand in (raw, f"doc/{raw}"):
        target = (root / f"{cand}.md").resolve()
        if not str(target).startswith(str(root)):
            raise SystemExit("[ERROR] 路径越界")
        if target.is_file():
            print(target.read_text(encoding="utf-8"))
            return 0
    raise SystemExit(f"[ERROR] 没有这一页: {args.path}（用 `wxart docs list` 看有哪些）")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wechat_docs",
        description="微信公众号官方文档本地镜像（抓取 / 检索 / 查看）",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", help="抓取/续抓官方文档到状态目录")
    p.add_argument("--limit", type=int, default=MAX_PAGES_DEFAULT,
                   help=f"本次最多抓多少页，默认 {MAX_PAGES_DEFAULT}")
    p.add_argument("--delay", type=float, default=0.3, help="每页间隔秒数，默认 0.3")
    p.add_argument("--force", action="store_true", help="忽略已存在的副本，全部重抓")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("list", help="列出镜像里的页面")
    p.add_argument("filter", nargs="?", help="只列路径含该字符串的页")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("search", help="在镜像里按正则检索")
    p.add_argument("keyword")
    p.add_argument("--max-per-file", type=int, default=5)
    p.add_argument("--quiet", action="store_true", help="只列命中文件，不列行")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("show", help="打印某一页")
    p.add_argument("path")
    p.set_defaults(func=cmd_show)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
