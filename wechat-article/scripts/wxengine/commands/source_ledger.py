"""Manage verified sources for a WeWrite run."""

from __future__ import annotations

import argparse
import json
import sys

from ..sources import add_source, load_sources


def main(argv=None):
    ap = argparse.ArgumentParser(description="记录和查看文章事实来源")
    sub = ap.add_subparsers(dest="action", required=True)

    add = sub.add_parser("add")
    add.add_argument("--run-id")
    add.add_argument("--url", default="", help="http(s) URL; may be omitted for user_provided")
    add.add_argument("--title", required=True)
    add.add_argument("--claim", required=True)
    add.add_argument("--publisher", default="")
    add.add_argument("--published-at", default="")
    add.add_argument("--status", choices=["verified", "unverified", "user_provided"], default="verified")

    ls = sub.add_parser("list")
    ls.add_argument("--run-id")
    ls.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    try:
        if args.action == "add":
            entry = add_source(
                run_id=args.run_id,
                url=args.url,
                title=args.title,
                claim=args.claim,
                publisher=args.publisher,
                published_at=args.published_at,
                status=args.status,
            )
            print(json.dumps(entry, ensure_ascii=False, indent=2))
            return

        data = load_sources(args.run_id)
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            for item in data["sources"]:
                print(f"[{item['status']}] {item['title']} — {item['claim']} ({item['url']})")
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
