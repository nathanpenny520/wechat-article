#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二道门禁：跑微信官方校验器（verify-article-structure-spec）。

## 为什么需要它

`wxart validate` 是 14 条**正则**规则，管的是「标签/属性/内联样式/占位符」这类静态形态。
微信官方另外开源了一套**编辑器排版规范 + 校验器**（MIT）：

    仓库  https://github.com/wechatjs/verify-article-structure-spec
    规范  https://developers.weixin.qq.com/doc/subscription/guide/product/plugin_spec.html

它用 puppeteer 起真实浏览器跑**布局测量**类规则——固定宽度的居中不一致 / 溢出 / 跨屏宽度差异、
`line-height` 叠字、`height` 溢出、暗色对比度与渐变——这些正则测不出来。

## 它不阻断流水线

官方那套依赖 node + npm + 一个 Chromium。**本 skill 的运行时绝不背这个包袱**：
本脚本只做「有就跑、没有就明确跳过」，缺依赖时退出码仍是 0，并在 stderr 说明原因。
要让 CI 把缺失当失败，加 `--strict`。

## 用法

    python3 scripts/official_check.py <article.html>            # 人类可读
    python3 scripts/official_check.py <article.html> --json     # 结构化
    python3 scripts/official_check.py <article.html> --strict   # 缺依赖时退出 2

## 环境变量

    WXARTICLE_VERIFY_REPO   官方仓路径（默认 $WXARTICLE_HOME/tools/verify-article-structure-spec）
    PUPPETEER_EXECUTABLE_PATH  浏览器可执行文件；不设则自动探测系统 Chrome / Chromium

## 退出码

    0  通过，或依赖缺失而跳过（除非 --strict）
    1  官方校验器报了违规
    2  执行异常（脚本存在但跑不起来、依赖缺失且 --strict）
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_SLUG = "verify-article-structure-spec"
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)


def state_home() -> Path:
    return Path(os.environ.get("WXARTICLE_HOME", Path.home() / ".wxarticle"))


def find_repo(explicit: str | None) -> Path | None:
    cands = []
    if explicit:
        cands.append(Path(explicit))
    if os.environ.get("WXARTICLE_VERIFY_REPO"):
        cands.append(Path(os.environ["WXARTICLE_VERIFY_REPO"]))
    cands.append(state_home() / "tools" / REPO_SLUG)
    cands.append(Path.cwd() / REPO_SLUG)
    for c in cands:
        if (c / "cli" / "package.json").is_file():
            return c
    return None


def find_chrome() -> str | None:
    env = os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if env and os.access(env, os.X_OK):
        return env
    for c in CHROME_CANDIDATES:
        if os.access(c, os.X_OK):
            return c
    for name in ("google-chrome", "chromium", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def extract_body(html: str) -> str:
    """抽 <body>，去掉 <style>/<script>——与 wxart validate 同口径。

    整页输入会把预览包装的 <style> 也算进布局检测，报出假阳性 width。
    """
    m = re.search(r"<body[^>]*>(.*?)</body>", html, re.S | re.I)
    body = m.group(1) if m else html
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S | re.I)
    body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S | re.I)
    return body.strip()


HELP_SKIP = """跳过官方校验器（不阻断）。启用方式：

  1) 取官方仓（github.com 不通时用 codeload）：
       mkdir -p ~/.wxarticle/tools && cd ~/.wxarticle/tools
       curl -L -o vas.tgz https://codeload.github.com/wechatjs/{slug}/tar.gz/refs/heads/main
       mkdir -p {slug} && tar xzf vas.tgz -C {slug} --strip-components=1
  2) 装依赖（跳过 Chromium 下载，用系统浏览器）：
       cd {slug}/cli
       PUPPETEER_SKIP_DOWNLOAD=true npm install --cache /tmp/npmcache
  3) 重跑本脚本；用 PUPPETEER_EXECUTABLE_PATH 指定浏览器（不设会自动探测）
""".format(slug=REPO_SLUG)


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("article", help="排版产物 article.html")
    ap.add_argument("--json", action="store_true", help="要求官方 CLI 输出 JSON")
    ap.add_argument("--repo", help="官方仓路径")
    ap.add_argument("--strict", action="store_true", help="依赖缺失时以退出码 2 报错")
    args = ap.parse_args()

    src = Path(args.article)
    if not src.is_file():
        print("official_check: 找不到文件 %s" % src, file=sys.stderr)
        return 2

    def skip(reason: str) -> int:
        print("official_check: SKIP — %s" % reason, file=sys.stderr)
        print(HELP_SKIP, file=sys.stderr)
        return 2 if args.strict else 0

    repo = find_repo(args.repo)
    if repo is None:
        return skip("未找到官方仓（%s）" % REPO_SLUG)

    npm = shutil.which("npm")
    if npm is None:
        return skip("未找到 npm")

    cli = repo / "cli"
    if not (cli / "node_modules").is_dir():
        return skip("官方仓还没装依赖（%s/node_modules 不存在）" % cli)

    chrome = find_chrome()
    env = dict(os.environ)
    if chrome:
        env["PUPPETEER_EXECUTABLE_PATH"] = chrome

    html = extract_body(src.read_text(encoding="utf-8"))
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head>"
                 "<body><div id=\"js_content\">%s</div></body></html>" % html)
        tmp = fh.name

    cmd = [npm, "run", "check", "--silent", "--", tmp]
    if args.json:
        cmd.append("--json")
    try:
        proc = subprocess.run(cmd, cwd=str(cli), env=env, capture_output=True, text=True)
    except OSError as exc:
        return skip("启动官方校验器失败：%s" % exc)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    out = (proc.stdout or "") + (proc.stderr or "")
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)
    out = "\n".join(l for l in out.splitlines()
                    if not any(k in l for k in (
                        "Puppeteer old Headless", "In the near future",
                        "for Chrome instead", "developer.chrome.com",
                        "Consider opting", "If you encounter any bugs")))
    print(out.strip())

    if proc.returncode == 0:
        print("\nofficial_check: PASS（官方规范未报违规）", file=sys.stderr)
    elif proc.returncode == 1:
        print("\nofficial_check: FAIL（官方规范报了违规，逐条见上）", file=sys.stderr)
    else:
        print("\nofficial_check: ERROR（官方校验器退出码 %d）" % proc.returncode, file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
