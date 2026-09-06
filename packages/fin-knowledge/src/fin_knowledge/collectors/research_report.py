"""券商研报采集: 东财研报列表 + 详情页投资要点正文 → 入库。

来源实测 2026-09-03/04: reportapi.eastmoney.com 列表(JSON, 缺参报500 故全参数拼接);
详情页 zw-content 容器嵌套 div, 用标签栈平衡抽取(non-greedy 正则会被截断)。
PDF 原文被 EdgeOne 反爬, 不抓——摘要正文已覆盖主要价值(Donnie 批准口径)。
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta

from ..ingest import ingest_document
from ._http import get_bytes

logger = logging.getLogger("fin_knowledge")

_HEADERS = {"Referer": "https://data.eastmoney.com/"}


def _get(url: str, timeout: int = 30) -> bytes:
    return get_bytes(url, headers=_HEADERS, timeout=timeout)


def fetch_report_list(stock_code: str, days: int = 180, page_size: int = 20) -> list[dict]:
    """东财个股研报列表。stock_code 完整格式(600519.SH), 接口用纯数字代码。"""
    code = stock_code.split(".")[0]
    end = datetime.now().strftime("%Y-%m-%d")
    begin = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (
        "https://reportapi.eastmoney.com/report/list?"
        f"industryCode=*&pageSize={page_size}&pageNo=1&qType=0&code={code}"
        f"&industry=*&beginTime={begin}&endTime={end}"
    )
    data = json.loads(_get(url))
    return list(data.get("data") or [])


def extract_report_body(info_code: str) -> str:
    """详情页正文: 定位 zw-content 容器, 标签栈平衡截取, 去标签清洗。"""
    html = _get(f"https://data.eastmoney.com/report/zw_stock.jshtml?infocode={info_code}").decode("utf-8", "ignore")
    pos = html.find("zw-content")
    if pos < 0:
        return ""
    start = html.rfind("<div", 0, pos)
    depth, end = 0, None
    for m in re.finditer(r"<div\b|</div>", html[start : start + 200000]):
        depth += 1 if m.group(0) != "</div>" else -1
        if depth == 0:
            end = start + m.end()
            break
    if end is None:
        return ""
    seg = re.sub(r"<script.*?</script>", "", html[start:end], flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", seg)
    text = re.sub(r"\n{2,}", "\n", re.sub(r"[ \t　]+", " ", text)).strip()
    # 去页面装饰行(域名/查看PDF等), 保留正文
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 1]
    lines = [ln for ln in lines if ln not in ("www.eastmoney.com", "查看PDF原文")]
    return "\n".join(lines)


def ingest_stock_reports(stock_code: str, days: int = 180, limit: int = 10) -> dict:
    """抓取并入库该股近 N 天研报正文。逐篇容错, 失败列入 failed 不静默。"""
    reports = fetch_report_list(stock_code, days=days)[:limit]
    tally = {"ingested": 0, "duplicate": 0, "empty": 0, "failed": []}
    for rep in reports:
        info_code = rep.get("infoCode")
        title = rep.get("title") or ""
        try:
            body = extract_report_body(info_code)
            org = rep.get("orgSName") or ""
            rating = rep.get("emRatingName") or ""
            header = f"{title}\n机构: {org} 评级: {rating}\n"
            r = ingest_document(
                doc_type="research_report",
                title=f"{org}: {title}",
                text=header + body,
                stock_code=stock_code,
                source_url=f"https://data.eastmoney.com/report/zw_stock.jshtml?infocode={info_code}",
                published_at=(rep.get("publishDate") or "")[:10],
            )
            tally[r["status"]] = tally.get(r["status"], 0) + 1
        except Exception as e:
            tally["failed"].append(f"{info_code}:{type(e).__name__}")
            logger.warning("研报入库失败 %s %s: %s", stock_code, title[:30], e)
        time.sleep(1)
    return {"stock_code": stock_code, "listed": len(reports), **tally}
