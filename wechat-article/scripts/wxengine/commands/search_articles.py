#!/usr/bin/env python3
"""搜狗微信搜索：按关键词搜公众号文章，输出结构化 JSON。

选题模块（wewrite-topic 2.1b 高频需求参考）的数据源：近一周垂类文章列表。
搜狗结果不带阅读量，同题密度只能用于观察内容需求频率。

时间过滤在客户端做——搜狗服务端 tsn 参数需要登录态（未登录 302 回首页），
故多扫几页后按解析出的发布时间过滤。

移植自 zjp1997720/wechat-article-search（MIT，Node.js 版），逻辑对齐其
scripts/search_wechat.js + 本地 -t 补丁。

Usage:
    wewrite search-articles "AI编程"                # 默认 10 条
    wewrite search-articles "AI编程" -n 15 -t 2     # 近一周，15 条
    wewrite search-articles "AI编程" -n 5 -r        # 解析 mp.weixin.qq.com 直链
"""

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

TIMEOUT = (10, 30)
CST = timezone(timedelta(hours=8))

# 固定 UA 池，每次请求随机选一个，避免固定指纹
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/123.0.0.0 Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
]

# tsn 时间过滤 → 天数
TSN_DAYS = {1: 1, 2: 7, 3: 30, 4: 365}


def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weixin.sogou.com/",
    }


def _bootstrap_session() -> requests.Session:
    """建会话并预热 cookie（SNUID/SUV），提高搜索请求通过率。"""
    session = requests.Session()
    try:
        session.get(
            "https://v.sogou.com/v?ie=utf8&query=&p=40030600",
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        print(f"[warn] cookie bootstrap failed: {e}", file=sys.stderr)
    return session


def _parse_item(li) -> dict | None:
    """解析一条搜索结果：标题/链接/摘要/发布时间/来源账号。"""
    title_link = li.select_one("h3 a")
    if title_link is None:
        return None
    title = title_link.get_text(strip=True)
    url = title_link.get("href", "")
    if url.startswith("/"):
        url = f"https://weixin.sogou.com{url}"

    summary_el = li.select_one("p.txt-info")
    summary = summary_el.get_text(strip=True) if summary_el else ""

    dt = ""
    source = ""
    box = li.select_one(".s-p")
    if box is not None:
        # 发布时间藏在 .s2 的 script 里，10 位 unix 时间戳
        script = box.select_one(".s2 script")
        if script is not None:
            m = re.search(r"(\d{10})", script.get_text())
            if m:
                dt = datetime.fromtimestamp(int(m.group(1)), tz=CST).strftime("%Y-%m-%d %H:%M:%S")
        source_el = box.select_one(".all-time-y2") or box.select_one("a.account")
        if source_el is not None:
            source = source_el.get_text(strip=True)

    return {"title": title, "url": url, "summary": summary, "datetime": dt, "source": source}


def _parse_search_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    news_list = soup.select_one("ul.news-list")
    if news_list is None:
        return []
    items = []
    for li in news_list.find_all("li", recursive=False):
        item = _parse_item(li)
        if item:
            items.append(item)
    return items


def _extract_redirect_url(html: str) -> str | None:
    """从搜狗中转页 HTML 提取真实跳转地址（url += 拼接 / meta refresh / JS 跳转）。"""
    parts = re.findall(r"url\s*\+=\s*'([^']*)'", html) + re.findall(r'url\s*\+=\s*"([^"]*)"', html)
    if parts:
        joined = "".join(parts)
        if "mp.weixin.qq.com" in joined:
            return joined
    m = re.search(r"<meta[^>]*http-equiv=[\"']refresh[\"'][^>]*content=[\"']\d+;\s*url=([^\"']+)[\"']", html, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(?:window\.)?location(?:\.href)?\s*=\s*[\"']([^\"']+)[\"']", html, re.I)
    if m:
        return m.group(1)
    return None


def _resolve_real_url(session: requests.Session, url: str, retries: int = 3) -> tuple[str, bool]:
    """搜狗中转链接 → mp.weixin.qq.com 直链。反爬下会失败，失败保留原链接。"""
    if "weixin.sogou.com" not in url:
        return url, True
    for attempt in range(retries):
        try:
            resp = session.get(url, headers=_headers(), timeout=(5, 10), allow_redirects=False)
            if 300 <= resp.status_code < 400:
                location = resp.headers.get("location", "")
                if "mp.weixin.qq.com" in location:
                    return location, True
                return url, False
            if resp.status_code == 200:
                real = _extract_redirect_url(resp.text)
                if real and "mp.weixin.qq.com" in real and "antispider" not in real:
                    return real, True
                return url, False
        except requests.RequestException:
            pass
        if attempt < retries - 1:
            time.sleep(1)
    return url, False


def search_articles(query: str, num: int = 10, tsn: int = 0, resolve_url: bool = False) -> list[dict]:
    num = min(num, 50)
    cutoff = None
    if tsn in TSN_DAYS:
        cutoff = datetime.now(CST) - timedelta(days=TSN_DAYS[tsn])

    session = _bootstrap_session()
    articles: list[dict] = []
    # 无时间过滤按需翻页；有时间过滤固定扫 5 页再筛
    max_pages = 5 if cutoff else max(1, -(-num // 10))

    for page in range(1, max_pages + 1):
        if len(articles) >= num:
            break
        url = (
            "https://weixin.sogou.com/weixin?"
            f"query={requests.utils.quote(query)}&s_from=input&_sug_=n&type=2&page={page}&ie=utf8"
        )
        try:
            resp = session.get(url, headers=_headers(), timeout=TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[warn] page {page} failed: {e}", file=sys.stderr)
            break
        parsed = _parse_search_page(resp.text)
        if not parsed:
            break
        if cutoff:
            parsed = [
                a for a in parsed
                if a["datetime"] and datetime.strptime(a["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST) >= cutoff
            ]
        articles.extend(parsed[: num - len(articles)])
        if page < max_pages:
            time.sleep(0.5 + random.random())

    if resolve_url and articles:
        print(f"解析 {len(articles)} 条真实链接（反爬下可能失败）…", file=sys.stderr)
        for i, article in enumerate(articles):
            real, ok = _resolve_real_url(session, article["url"])
            article["url"] = real
            article["url_resolved"] = ok
            if i < len(articles) - 1:
                time.sleep(0.5 + random.random())

    return articles


def main():
    parser = argparse.ArgumentParser(description="搜狗微信搜索：按关键词搜公众号文章")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("-n", "--num", type=int, default=10, help="返回数量（默认 10，最大 50）")
    parser.add_argument(
        "-t", "--time", type=int, default=0, choices=[1, 2, 3, 4],
        help="时间过滤：1=一天内 2=一周内 3=一月内 4=一年内（客户端过滤，最多扫 5 页）",
    )
    parser.add_argument("-r", "--resolve-url", action="store_true", help="解析 mp.weixin.qq.com 直链（逐条额外请求）")
    parser.add_argument("-o", "--output", help="结果另存为 JSON 文件")
    args = parser.parse_args()

    articles = search_articles(args.query, args.num, args.time, args.resolve_url)
    output = {
        "timestamp": datetime.now(CST).isoformat(),
        "query": args.query,
        "tsn": args.time,
        "total": len(articles),
        "articles": articles,
    }
    if not articles:
        output["error"] = "无结果：可能被反爬限流，换关键词或稍后再试；SKILL.md 应降级跳过本步。"

    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"结果已保存到: {args.output}", file=sys.stderr)
    print(text)


if __name__ == "__main__":
    main()
