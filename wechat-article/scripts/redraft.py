#!/usr/bin/env python3
"""原地更新草稿箱里的一条草稿 —— 重排版式而不产生新草稿。

## 为什么需要它

`wxart publish` 只会 `draft/add`，也就是**新建**一条草稿。于是「换个模版再排一遍看看」
这件事的成本是草稿箱里多一条近乎重复的稿子，试三套模版就是三条，选完还得手工删。
真实流程里更常见的是：稿子已经进草稿箱了，只想把版式换掉、标题正文一个字不动。

微信有 `draft/update`：按 `media_id` 替换某条草稿的内容，**不新建**。这个脚本把它接出来。

## 用法

    python3 redraft.py <media_id> <文章目录> [--index 0] [--dry-run]

文章目录与 `publish.py full` 一致：

    文章目录/
    ├── article.yaml    标题/作者/摘要等元信息
    ├── article.html    排版后的正文 HTML
    ├── cover.png       封面图
    └── imgs/           正文内图片（可选）

`--dry-run` 只打印将要提交的字段与长度，不发请求——用于确认「改的确实是这条、
只改了版式」。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 复用 aws 发布链路的凭证/上传/裁剪实现。这些函数是纯标准库写的，import 无副作用。
_SCRIPTS = Path(__file__).resolve().parent
_PUB = _SCRIPTS / "aws" / "aws-wechat-article-publish" / "scripts"
if str(_PUB) not in sys.path:
    sys.path.insert(0, str(_PUB))

_COVER_NAMES = ["cover.jpg", "cover.png", "cover.jpeg", "cover.webp"]


def _load_article_dir(article_dir: Path) -> dict:
    import yaml

    meta_path = article_dir / "article.yaml"
    if not meta_path.is_file():
        raise SystemExit(f"[ERROR] 未找到 {meta_path}")
    content_path = article_dir / "article.html"
    if not content_path.is_file():
        raise SystemExit(f"[ERROR] 未找到 {content_path}")

    with open(meta_path, encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    import publish as P

    cover = None
    for name in _COVER_NAMES:
        if (article_dir / name).is_file():
            cover = article_dir / name
            break
    if cover is None:
        imgs = article_dir / "imgs"
        if imgs.is_dir():
            for name in _COVER_NAMES:
                if (imgs / name).is_file():
                    cover = imgs / name
                    break
    if cover is None:
        raise SystemExit(
            f"[ERROR] 未找到封面图（{'/'.join(_COVER_NAMES)}）；放在 {article_dir}/ 或 imgs/ 下"
        )

    return {"meta": meta, "content": content_path.read_text(encoding="utf-8"),
            "cover": cover, "article_dir": article_dir, "P": P}


def _build_payload(bundle: dict, token: str, index: int) -> dict:
    P = bundle["P"]
    meta, content, article_dir = bundle["meta"], bundle["content"], bundle["article_dir"]

    thumb = P.upload_thumb(token, str(bundle["cover"]))
    if thumb.get("errcode"):
        raise SystemExit(f"[ERROR] 封面上传失败: {thumb}")
    print(f"[OK] 封面图上传成功: media_id={thumb['media_id']}", file=sys.stderr)

    # 正文内图：与 full 一致，只上传 HTML 真正引用到的文件，并把路径换成微信图床 URL。
    P._info(f"封面 {bundle['cover'].name}")
    imgs_dir = article_dir / "imgs"
    if imgs_dir.is_dir():
        for fname in P._content_image_refs_flat(content):
            img_file = imgs_dir / fname
            if not img_file.is_file():
                raise SystemExit(f"[ERROR] 正文引用了不存在的图片: imgs/{fname}")
            url = P.upload_content_image(token, str(img_file))
            content = content.replace(f"imgs/{img_file.name}", url)
            content = content.replace(img_file.name, url)
            print(f"[OK] 正文图 {img_file.name} → {url}", file=sys.stderr)

    cfg = P.load_repo_config()
    author = (meta.get("author") or "").strip() or str(cfg.get("default_author") or "").strip()

    article = {
        "title": meta.get("title", ""),
        "author": author,
        "digest": meta.get("digest", ""),
        "content": content,
        "thumb_media_id": thumb["media_id"],
        "content_source_url": meta.get("content_source_url", ""),
        "need_open_comment": meta.get("need_open_comment", 0),
        "only_fans_can_comment": meta.get("only_fans_can_comment", 0),
    }
    article.update(P._cover_crops(str(bundle["cover"]), meta))
    return {"index": index, "articles": article}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="redraft",
        description="原地更新草稿箱里的一条草稿（按 media_id，不新建）",
    )
    ap.add_argument("media_id", help="要更新的草稿 media_id（wxart getdraft list 可取）")
    ap.add_argument("article_dir", help="文章目录（article.yaml + article.html + cover.*）")
    ap.add_argument("--index", type=int, default=0,
                    help="多图文时更新第几篇，默认 0")
    ap.add_argument("--dry-run", action="store_true", help="只打印将提交的内容，不发请求")
    args = ap.parse_args(argv)

    article_dir = Path(args.article_dir)
    bundle = _load_article_dir(article_dir)
    P = bundle["P"]

    if args.dry_run:
        print(json.dumps({
            "media_id": args.media_id,
            "index": args.index,
            "title": bundle["meta"].get("title", ""),
            "content_bytes": len(bundle["content"].encode("utf-8")),
            "cover": str(bundle["cover"]),
        }, ensure_ascii=False, indent=2))
        return 0

    cfg = P.load_repo_config()
    env = P._load_env_map()
    slot_index = int(cfg.get("wechat_publish_slot", 1) or 1)
    slot = P.wechat_slot(cfg, env, slot_index)
    missing = P.missing_wechat_slot_fields(slot)
    if missing:
        raise SystemExit(f"[ERROR] 微信槽位 {slot_index} 缺少: {', '.join(missing)}")
    token = P.get_access_token(slot["appid"], slot["appsecret"])

    payload = {"media_id": args.media_id.strip(), **_build_payload(bundle, token, args.index)}

    url = f"{P.API_BASE}{P.API_PATH}/draft/update?access_token={token}"
    resp = P._api_post_json(url, payload)
    if resp.get("errcode") not in (None, 0):
        raise SystemExit(f"[ERROR] draft/update 失败: {resp}")
    print("[OK] 已原地更新草稿", file=sys.stderr)

    # 回读一次，确认「改的是这条、标题没动」。只信写成功不够——写错条目也是 0。
    got = P._api_post_json(
        f"{P.API_BASE}{P.API_PATH}/draft/get?access_token={token}",
        {"media_id": args.media_id.strip()},
    )
    items = got.get("news_item") or []
    if not items:
        print("[WARN] 更新成功但回读不到内容，请到草稿箱肉眼确认", file=sys.stderr)
        return 0
    ni = items[min(args.index, len(items) - 1)]
    print(f"[OK] 回读确认: 《{ni.get('title')}》 正文 {len(ni.get('content') or '')} 字节",
          file=sys.stderr)
    if ni.get("title") != bundle["meta"].get("title"):
        print(f"[WARN] 回读标题与 article.yaml 不一致: {ni.get('title')!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
