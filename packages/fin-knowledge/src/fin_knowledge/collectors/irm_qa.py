"""投资者互动问答采集: 公司对投资者提问的官方回复 → 入库(沪深两市)。

两套采集逻辑, 统一产物 schema (2026-09-09 实测定型, 修正原纯深市+全站搜索方案):
- 深市(.SZ): 巨潮互动易 per-company 干净接口。先 queryKeyboardInfo 拿 orgId(secid),
  再 company/question 按股拉列表(替代原全站搜索 keyWord=公司名 会被别股淹没漏抓)。
  字段 mainContent=问 / attachedContent=答 / attachedPubDate=答时间; 结果侧过滤已回复。
- 沪市(.SH): 上证 e 互动 sns.sseinfo.com。平台用内部 uid 寻址(非股票代码), uid 由调度层
  扫 allcompany.do 建 code→uid 缓存后传入 sse_uid。userfeeds.do type=11 拉已回复 feed,
  HTML 解析: 提问在 m_feed_txt(无id)、回复在 m_feed_detail.m_qa 内带 id 的 m_feed_txt。
  (原注释"沪市未打通"系旧结论, 2026-09-09 实测 allcompany+userfeeds 打通, 已推翻)
- 北交所(.BJ): 暂不支持(平台未接入), 返回 not_supported 属确认边界。
"""

import json
import logging
import re
import time
import urllib.parse

from ..ingest import ingest_document
from ._http import post_bytes

logger = logging.getLogger("fin_knowledge")

_FORM_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}
_SSE_HEADERS = {"Content-Type": "application/x-www-form-urlencoded", "Referer": "https://sns.sseinfo.com/"}


def _fmt_date(v) -> str:
    """毫秒/秒时间戳 → YYYY-MM-DD; 异常返回空串不猜。"""
    from datetime import datetime

    try:
        ts = float(v)
        if ts > 1e12:
            ts /= 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def _clean_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return s.strip()


# ────────────────────────── 深市: 巨潮互动易 per-company ──────────────────────────
def _sz_org_id(code: str) -> str | None:
    """queryKeyboardInfo 拿该股 secid(orgId)。"""
    r = json.loads(post_bytes(
        "https://irm.cninfo.com.cn/newircs/index/queryKeyboardInfo",
        data=urllib.parse.urlencode({"keyWord": code}).encode(),
        headers=_FORM_HEADERS, timeout=25,
    ))
    d = r.get("data") or []
    return d[0].get("secid") if d else None


def _fetch_sz_qa(code: str, page_size: int = 50) -> list[dict]:
    """深市该股已回复互动问答, 统一为 {q, a, date}。"""
    org = _sz_org_id(code)
    if not org:
        return []
    url = (
        f"https://irm.cninfo.com.cn/newircs/company/question?stockcode={code}&orgId={org}"
        f"&pageSize={page_size}&pageNum=1&keyWord=&startDay=&endDay="
    )
    r = json.loads(post_bytes(url, data=b"", headers=_FORM_HEADERS, timeout=25))
    out = []
    for x in (r.get("rows") or []):
        q = (x.get("mainContent") or "").strip()
        a = (x.get("attachedContent") or "").strip()
        if q and a:
            out.append({"q": q, "a": a, "date": _fmt_date(x.get("attachedPubDate") or x.get("pubDate"))})
    return out


# ────────────────────────── 沪市: 上证 e 互动 ──────────────────────────
def _sse_post(url: str, retries: int = 3) -> str:
    """sns.sseinfo.com 偶发读超时, 带 Referer + 重试。"""
    last = None
    for i in range(retries):
        try:
            return post_bytes(url, data=b"", headers=_SSE_HEADERS, timeout=30).decode("utf-8", "ignore")
        except Exception as e:
            last = e
            logger.warning("上证e互动重试 %d: %s", i + 1, type(e).__name__)
            time.sleep(3)
    raise last


def _norm_sse_date(s: str) -> str:
    """'2026年08月27日 15:21' → '2026-08-27'。"""
    m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _parse_sse_feed(html: str) -> list[dict]:
    """解析 userfeeds HTML: 提问=m_feed_txt(无id含公司前缀), 回复=m_qa内带id的m_feed_txt。"""
    out = []
    # 每个 feed item 以 m_feed_type(ask_ico) 开头
    items = re.split(r'<div class="m_feed_type', html)[1:]
    for it in items:
        qm = re.search(r'<div class="m_feed_txt">\s*<a[^>]*>:[^<]*</a>(.*?)</div>', it, re.S)
        if not qm:
            continue
        q = _clean_html(qm.group(1))
        tm = re.search(r'<div class="m_feed_from">\s*<span>([^<]+)</span>', it)
        date = _norm_sse_date(tm.group(1)) if tm else ""
        am = re.search(r'm_feed_detail m_qa.*?<div class="m_feed_txt"[^>]*id="m_feed_txt[^"]*">(.*?)</div>', it, re.S)
        a = _clean_html(am.group(1)) if am else ""
        if q and a:
            out.append({"q": q, "a": a, "date": date})
    return out


def _fetch_sse_qa(uid: str, page_size: int = 50) -> list[dict]:
    """沪市该股(按uid)已回复互动问答, 统一为 {q, a, date}。type=11=已回复。"""
    url = f"https://sns.sseinfo.com/ajax/userfeeds.do?typeCode=company&type=11&pageSize={page_size}&uid={uid}&page=1"
    return _parse_sse_feed(_sse_post(url))


# ────────────────────────── 主入口: 按市场分派 ──────────────────────────
def ingest_stock_qa(stock_code: str, company_name: str = "", sse_uid: str | None = None,
                    page_size: int = 50) -> dict:
    """该股互动问答合并为一篇文档入库(哈希去重, 新回复出现则成新文档)。

    沪市(.SH)需调度层传入 sse_uid(上证e互动内部id); 深市(.SZ)自动解析 orgId; 北交所暂不支持。
    合并入库而非逐条: 单条问答太短, 逐条成块检索噪声大; 合并后按块自然切分。
    """
    code = stock_code.split(".")[0]
    # 北交所(920新代码段/43/83/87/88)暂不支持; 优先后缀判断, 代码段为兜底
    if stock_code.endswith(".BJ") or code.startswith(("4", "8", "92")):
        return {"stock_code": stock_code, "status": "not_supported", "qa_count": 0}

    is_sh = stock_code.endswith(".SH") or code.startswith("6")
    if is_sh:
        if not sse_uid:
            return {"stock_code": stock_code, "status": "no_uid", "qa_count": 0}
        rows = _fetch_sse_qa(sse_uid, page_size)
        src_url = f"https://sns.sseinfo.com/company.do?uid={sse_uid}"
    else:
        rows = _fetch_sz_qa(code, page_size)
        src_url = f"https://irm.cninfo.com.cn/views/interactiveAnswer/index.html?stockcode={code}"

    if not rows:
        return {"stock_code": stock_code, "status": "not_found", "qa_count": 0}

    parts = []
    latest = ""
    for r in rows:
        latest = max(latest, r["date"] or "")
        parts.append(f"问({r['date']}): {r['q']}\n公司回复: {r['a']}")
    text = "\n\n".join(parts)
    result = ingest_document(
        doc_type="irm_qa",
        title=f"{stock_code} 互动问答(截至{latest})",
        text=text,
        stock_code=stock_code,
        source_url=src_url,
        published_at=latest,
    )
    return {"stock_code": stock_code, "qa_count": len(parts), **result}
