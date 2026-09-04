"""政府网政策原文采集: 最新政策列表 JSON + 正文容器抽取 → 入库。

来源实测 2026-09-03: www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json (现成数组
1000+ 条 TITLE/URL/DATE), 正文页 id="UCAP-CONTENT" 容器。
"""

import json
import logging
import re
import time
import urllib.request

from ..ingest import ingest_document

logger = logging.getLogger("fin_knowledge")

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_LIST_URL = "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with _opener.open(req, timeout=timeout) as resp:
        return resp.read()


def fetch_policy_list(limit: int = 50) -> list[dict]:
    raw = _get(_LIST_URL).decode("utf-8", "ignore")
    data = json.loads(raw.lstrip("﻿"))
    rows = data if isinstance(data, list) else data.get("data") or []
    return list(rows)[:limit]


def extract_policy_body(url: str) -> str:
    if url.startswith("/"):
        url = "https://www.gov.cn" + url
    html = _get(url).decode("utf-8", "ignore")
    m = re.search(r'id="UCAP-CONTENT"[^>]*>(.*?)<!--|id="UCAP-CONTENT"[^>]*>(.*)', html, re.S)
    if not m:
        return ""
    seg = m.group(1) or m.group(2) or ""
    seg = re.sub(r"<script.*?</script>|<style.*?</style>", "", seg, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", seg)
    return re.sub(r"\n{2,}", "\n", re.sub(r"[ \t　]+", " ", text)).strip()[:100000]


def ingest_latest_policies(limit: int = 30) -> dict:
    """入库最新 N 条政策原文。已入库(同标题同文)哈希去重秒过, 适合每日增量。"""
    rows = fetch_policy_list(limit=limit)
    tally = {"ingested": 0, "duplicate": 0, "empty": 0, "failed": []}
    for row in rows:
        title = (row.get("TITLE") or row.get("title") or "").strip()
        url = row.get("URL") or row.get("url") or ""
        date = str(row.get("PUBDATE") or row.get("pubdate") or "")[:10]
        if not title or not url:
            continue
        try:
            body = extract_policy_body(url)
            r = ingest_document(
                doc_type="policy",
                title=title,
                text=f"{title}\n{body}",
                source_url=url if url.startswith("http") else "https://www.gov.cn" + url,
                published_at=date,
            )
            tally[r["status"]] = tally.get(r["status"], 0) + 1
        except Exception as e:
            tally["failed"].append(f"{title[:20]}:{type(e).__name__}")
            logger.warning("政策入库失败 %s: %s", title[:30], e)
        time.sleep(1)
    return {"listed": len(rows), **tally}
