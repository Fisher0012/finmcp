"""深交所互动易问答采集: 公司管理层对投资者提问的官方回复 → 入库。

来源实测 2026-09-03: irm.cninfo.com.cn/newircs/index/search (POST 表单, JSON 返回,
mainContent 提问 + attachedContent 回复)。业绩说明会文本的深市替代入口
(上证路演中心登录墙, 暂缓——SPEC §3B 裁定)。

【覆盖边界, 显式标注】仅深市(00/30 开头)。沪市对应平台上证 e 互动
(sns.sseinfo.com) 的公司 uid 映射 2026-09-04 两次探测未打通(feeds.do 的 uid
非股票代码, 搜索接口 404), 沪市股返回 not_found 属确认边界而非数据缺失。
"""

import json
import logging
import time
import urllib.parse
import urllib.request

from ..ingest import ingest_document

logger = logging.getLogger("fin_knowledge")

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _fmt_date(v) -> str:
    """接口日期为 unix 时间戳(秒或毫秒), 转 YYYY-MM-DD; 异常返回空串不猜。"""
    from datetime import datetime

    try:
        ts = float(v)
        if ts > 1e12:
            ts /= 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def fetch_qa(stock_code: str, company_name: str, page_size: int = 50) -> list[dict]:
    """互动易该股最新已回复问答。

    参数实测(2026-09-04): searchTypes="11,"=已回复问答; stockCodes/secid 均无法锁定
    个股(返回杂股), 只能 keyWord=公司名 全文检索 + 结果侧按 stockCode 过滤。
    """
    code = stock_code.split(".")[0]
    payload = urllib.parse.urlencode(
        {"pageNo": 1, "pageSize": page_size, "searchTypes": "11,", "keyWord": company_name}
    ).encode()
    req = urllib.request.Request(
        "https://irm.cninfo.com.cn/newircs/index/search",
        data=payload,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with _opener.open(req, timeout=30) as resp:
        data = json.loads(resp.read())
    rows = data.get("results") or []
    return [r for r in rows if r.get("stockCode") == code and r.get("attachedContent")]


def ingest_stock_qa(stock_code: str, company_name: str, page_size: int = 50) -> dict:
    """该股互动易已回复问答合并为一篇文档入库（按抓取批次哈希去重, 新回复出现则成新文档）。

    合并入库而非逐条: 单条问答太短(几十字), 逐条成块检索噪声大; 合并后按块自然切分。
    """
    rows = fetch_qa(stock_code, company_name, page_size=page_size)
    if not rows:
        return {"stock_code": stock_code, "status": "not_found", "qa_count": 0}
    parts = []
    latest = ""
    for r in rows:
        q = (r.get("mainContent") or "").strip()
        a = (r.get("attachedContent") or "").strip()
        d = _fmt_date(r.get("attachedPubDate") or r.get("pubDate"))
        latest = max(latest, d)
        if q and a:
            parts.append(f"问({d}): {q}\n公司回复: {a}")
    text = "\n\n".join(parts)
    result = ingest_document(
        doc_type="irm_qa",
        title=f"{stock_code} 互动易问答(截至{latest})",
        text=text,
        stock_code=stock_code,
        source_url=f"https://irm.cninfo.com.cn/views/interactiveAnswer/index.html?stockcode={stock_code.split('.')[0]}",
        published_at=latest,
    )
    return {"stock_code": stock_code, "qa_count": len(parts), **result}
