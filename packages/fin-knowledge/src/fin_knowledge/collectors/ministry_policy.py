"""部委政策采集: gov.cn 政策文件库·部门文件检索接口 → 正文/PDF附件 → 入库。

来源实测 2026-09-10: sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary_bm
(部门文件库 12781 条, 覆盖工信部/发改委/央行/证监会/财政部等全部部委发文,
字段 title/url/puborg/pcode/pubtimeStr, 翻页 p/n)。正文页与国务院政策同构
(id="UCAP-CONTENT"); 重磅规划类"印发通知"正文短、全文在 PDF 附件, 此时
下载附件 pdfplumber 抽文本合并(复用年报线依赖)。

部委官网直采不可行(工信部 jpaas JS 壳, 2026-09-09 撞墙点), 政策库是唯一
可靠统一入口; 交易所(sse/szse)不在政策库, 另行立项。
"""

import json
import logging
import re
import time
import urllib.parse

from ..ingest import ingest_document
from ._http import get_bytes
from .annual_report import _pdf_to_text

logger = logging.getLogger("fin_knowledge")

_SEARCH_URL = "https://sousuo.www.gov.cn/search-gov/data"
# 实测: 默认 UA 被 WAF 拒, Chrome 样式 UA 通过
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0"}
# 印发通知类正文短于此值且带 PDF 附件时, 视为"全文在附件", 触发 PDF 抽取
_BODY_SHORT_THRESHOLD = 1500
_PDF_MAX_BYTES = 30 * 1024 * 1024


def fetch_ministry_list(page: int = 1, page_size: int = 20) -> list[dict]:
    """拉部门文件库列表(按发布时间倒序)。返回 listVO 原始行。"""
    qs = urllib.parse.urlencode({
        "t": "zhengcelibrary_bm", "q": "", "sort": "pubtime", "sortType": "1",
        "p": str(page), "n": str(page_size),
    })
    raw = get_bytes(f"{_SEARCH_URL}?{qs}", headers=_HEADERS).decode("utf-8", "ignore")
    data = json.loads(raw)
    return (data.get("searchVO") or {}).get("listVO") or []


def _find_pdf_url(page_url: str, html: str) -> str:
    """正文页内第一个 PDF 附件链接(相对路径基于正文页目录解析); 无则空串。"""
    m = re.search(r'href="([^"]+\.pdf)"', html, re.I)
    return urllib.parse.urljoin(page_url, m.group(1)) if m else ""


def _fetch_attachment_text(pdf_url: str) -> str:
    data = get_bytes(pdf_url, headers=_HEADERS, timeout=60)
    if len(data) > _PDF_MAX_BYTES or data[:4] != b"%PDF":
        return ""
    return _pdf_to_text(data)


def ingest_latest_ministry_policies(limit: int = 40) -> dict:
    """入库最新 N 条部委政策。哈希去重秒过, 适合每日增量。

    正文 = 通知正文(UCAP 容器) + 短正文时附件 PDF 全文;
    首行注入 发文机关/文号 结构化行(利于机构统计与检索召回)。
    """
    tally = {"listed": 0, "ingested": 0, "duplicate": 0, "empty": 0,
             "pdf_used": 0, "pdf_unreadable": 0, "url_skipped": 0, "failed": []}
    page_size = min(limit, 50)
    pages = (limit + page_size - 1) // page_size
    rows: list[dict] = []
    for p in range(1, pages + 1):
        rows.extend(fetch_ministry_list(page=p, page_size=page_size))
        time.sleep(1)
    rows = rows[:limit]
    tally["listed"] = len(rows)

    # URL 预查: 已入库的政策不重复抓正文/下载附件(去重时机教训: doc_hash 去重
    # 发生在下载之后, 每日增量会反复下载同一批 PDF)。政策 URL 稳定唯一可作预查键。
    from ..db import connect
    conn = connect()
    known_urls = {r["source_url"] for r in conn.execute(
        "SELECT source_url FROM documents WHERE doc_type='policy' AND source_url IS NOT NULL")}
    conn.close()

    for row in rows:
        title = re.sub(r"</?em>", "", (row.get("title") or "")).strip()
        url = row.get("url") or ""
        puborg = (row.get("puborg") or "").strip()
        pcode = (row.get("pcode") or "").strip()
        date = (row.get("pubtimeStr") or "").replace(".", "-")[:10]
        if not title or not url:
            continue
        if url in known_urls:
            tally["url_skipped"] += 1
            continue
        try:
            html = get_bytes(url, headers=_HEADERS).decode("utf-8", "ignore")
            body = _extract_body(html)
            pdf_url = _find_pdf_url(url, html) if len(body) < _BODY_SHORT_THRESHOLD else ""
            if pdf_url:
                att = _fetch_attachment_text(pdf_url).strip()
                if len(att) > 200:
                    body = f"{body}\n\n[附件全文]\n{att}"
                    tally["pdf_used"] += 1
                else:
                    # 扫描版 PDF 等抽不出文本: 显式标注缺口, 不静默(认识论铁律)
                    body = f"{body}\n\n[附件说明] 本文附件为PDF但文本不可抽取(疑似扫描版), 附件全文未入库。"
                    tally["pdf_unreadable"] += 1
            head = f"发文机关: {puborg or '未知'}" + (f"\n文号: {pcode}" if pcode else "")
            r = ingest_document(
                doc_type="policy",
                title=title,
                text=f"{title}\n{head}\n{body}",
                source_url=url,
                published_at=date,
            )
            tally[r["status"]] = tally.get(r["status"], 0) + 1
        except Exception as e:
            tally["failed"].append(f"{title[:20]}:{type(e).__name__}")
            logger.warning("部委政策入库失败 %s: %s", title[:30], e)
        time.sleep(1)
    return tally


def _extract_body(html: str) -> str:
    """UCAP-CONTENT 容器抽正文(与 policy.extract_policy_body 同构, 免二次请求)。"""
    m = re.search(r'id="UCAP-CONTENT"[^>]*>(.*?)<!--|id="UCAP-CONTENT"[^>]*>(.*)', html, re.S)
    if not m:
        return ""
    seg = m.group(1) or m.group(2) or ""
    seg = re.sub(r"<script.*?</script>|<style.*?</style>", "", seg, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", seg)
    return re.sub(r"\n{2,}", "\n", re.sub(r"[ \t　]+", " ", text)).strip()[:100000]
