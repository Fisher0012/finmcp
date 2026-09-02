"""5 源采集器（自 workbench lib/fin_news/collector.py 迁入, 抓取逻辑逐函数保持一致）。

方案 A（SPEC F4 R6 裁定）: 以独立进程运行（`python -m fin_news`）, 与 app 生命周期解耦。
"""

import json
import logging
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .db import count_rows, save

logger = logging.getLogger("fin_news")

# 绕过进程的 HTTPS_PROXY（国内 API 走代理会失败）
_no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

COLLECT_INTERVAL = 30 * 60  # 30 分钟


# ─────────────── 各信源抓取 ───────────────


def fetch_sina(limit: int = 30) -> list[dict]:
    """新浪财经 7x24 快讯。"""
    url = f"https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size={limit}&zhibo_id=152&tag_id=0&dire=f&dpc=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(_no_proxy_opener.open(req, timeout=15).read())
    feeds = data["result"]["data"]["feed"]["list"]
    items = []
    for f in feeds:
        txt = (f.get("rich_text") or "").strip()
        if not txt:
            continue
        m = re.search(r"【(.+?)】", txt)
        title = m.group(1) if m else txt[:40]
        items.append(
            {
                "source": "新浪财经",
                "title": title,
                "content": txt[:500],
                "url": f.get("docurl") or "https://finance.sina.com.cn",
                "published_at": f.get("create_time", ""),
            }
        )
    return items


def fetch_wallstreet(limit: int = 30) -> list[dict]:
    """华尔街见闻全球快讯。"""
    url = f"https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&client=pc&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(_no_proxy_opener.open(req, timeout=15).read())
    items_raw = data.get("data", {}).get("items", [])
    items = []
    for it in items_raw:
        title = (it.get("title") or "").strip()
        content = (it.get("content_text") or "").strip()
        if not title and not content:
            continue
        items.append(
            {
                "source": "华尔街见闻",
                "title": title or content[:40],
                "content": (content or title)[:500],
                "url": it.get("uri") or "https://wallstreetcn.com",
                "published_at": it.get("display_time", ""),
            }
        )
    return items


def fetch_eastmoney(limit: int = 30) -> list[dict]:
    """东方财富 7x24 快讯（JSONP 格式）。"""
    url = f"https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_{limit}_1_.html"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://kuaixun.eastmoney.com/",
        },
    )
    raw = _no_proxy_opener.open(req, timeout=15).read().decode("utf-8")
    m = re.search(r"var ajaxResult=(.+)", raw)
    if not m:
        return []
    data = json.loads(m.group(1))
    items = []
    for it in data.get("LivesList", []):
        title = (it.get("title") or "").strip()
        digest = (it.get("digest") or "").strip()
        if not title:
            continue
        items.append(
            {
                "source": "东方财富",
                "title": title,
                "content": digest[:500] or title,
                "url": it.get("url_w") or "https://finance.eastmoney.com",
                "published_at": it.get("showtime", ""),
            }
        )
    return items


def fetch_cninfo(limit: int = 20) -> list[dict]:
    """巨潮资讯网——A 股上市公司公告。"""
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    body = f"pageNum=1&pageSize={limit}&tabName=fulltext&isHLtitle=true".encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    data = json.loads(_no_proxy_opener.open(req, timeout=15).read())
    items = []
    for ann in data.get("announcements") or []:
        title = (ann.get("announcementTitle") or "").strip()
        sec = (ann.get("secName") or "").strip()
        if not title:
            continue
        full_title = f"{sec}：{title}" if sec else title
        adj_url = ann.get("adjunctUrl") or ""
        link = f"http://static.cninfo.com.cn/{adj_url}" if adj_url else "http://www.cninfo.com.cn"
        items.append(
            {
                "source": "巨潮资讯",
                "title": full_title,
                "content": full_title,
                "url": link,
                "published_at": "",
            }
        )
    return items


def fetch_10jqka(limit: int = 30) -> list[dict]:
    """同花顺财经要闻。"""
    url = f"https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(_no_proxy_opener.open(req, timeout=15).read())
    raw_list = (data.get("data") or {}).get("list") or []
    items = []
    for it in raw_list:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        items.append(
            {
                "source": "同花顺",
                "title": title,
                "content": (it.get("digest") or title)[:500],
                "url": it.get("url") or "https://news.10jqka.com.cn",
                "published_at": it.get("ctime", ""),
            }
        )
    return items


_SOURCES = [
    ("新浪财经", fetch_sina),
    ("华尔街见闻", fetch_wallstreet),
    ("东方财富", fetch_eastmoney),
    ("巨潮资讯", fetch_cninfo),
    ("同花顺", fetch_10jqka),
]


def run_collect_once() -> dict:
    """同步执行一次采集（多源并行），返回各源结果统计。"""
    stats = {}
    with ThreadPoolExecutor(max_workers=len(_SOURCES)) as pool:
        futures = {pool.submit(fn): name for name, fn in _SOURCES}
        all_items = []
        for fut, name in futures.items():
            try:
                items = fut.result(timeout=30)
                all_items.extend(items)
                stats[name] = {"ok": True, "fetched": len(items)}
            except Exception as e:
                stats[name] = {"ok": False, "error": str(e)[:80]}
                logger.warning("源 %s 失败: %s", name, e)
    inserted = save(all_items)
    stats["_total"] = {"fetched": len(all_items), "new": inserted, "db_total": count_rows()}
    logger.info("采集完成: %s", stats["_total"])
    return stats


def run_forever() -> None:
    """常驻采集循环（独立进程入口用）: 启动立即跑一次, 之后每 COLLECT_INTERVAL 秒一次。"""
    while True:
        try:
            run_collect_once()
        except Exception:
            logger.exception("采集循环异常（继续）")
        time.sleep(COLLECT_INTERVAL)
