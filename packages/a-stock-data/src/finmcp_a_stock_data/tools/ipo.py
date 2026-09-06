"""IPO 日历（batch-7 T19）: tushare new_share, 近期已发+未来待发新股。

字段经生产实调确认(2026-09-06): ts_code/sub_code/name/ipo_date/issue_date/amount(发行量万股)/
price/pe/limit_amount(申购上限万股)/funds(募资亿)/ballot(中签率%)。
"""

from datetime import datetime, timedelta
from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager

_cache = CacheManager()


def _pro() -> "Any":  # tushare 无类型桩, 返回 Any
    import tushare as ts

    return ts.pro_api()


def get_ipo_calendar(days_back: int = 14, days_forward: int = 30) -> dict[str, Any]:
    """IPO 日历: 近 days_back 天已上市/申购 + 未来 days_forward 天待发新股。

    典型场景: "最近有什么新股""打新日历""下周有哪些新股申购"。
    """
    try:
        start = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        end = (datetime.now() + timedelta(days=days_forward)).strftime("%Y%m%d")
        cache_key = _cache.make_key("tushare", "ipo_calendar", start, end)
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source="tushare", cache_hit=True)
        df = _pro().new_share(start_date=start, end_date=end)
        if df is None or df.empty:
            return ok_response(
                data={"items": [], "note": f"{start}~{end} 区间无新股记录(confirmed_absent)"},
                source="tushare",
            )
        items = []
        for _, r in df.iterrows():
            items.append(
                {
                    "name": str(r.get("name") or ""),
                    "sub_code": str(r.get("sub_code") or ""),
                    "ipo_date": str(r.get("ipo_date") or ""),
                    "issue_date": str(r.get("issue_date") or "") if str(r.get("issue_date")) != "nan" else "",
                    "amount_wan": float(r["amount"]) if r.get("amount") == r.get("amount") else None,
                    "price": float(r["price"]) if r.get("price") and r.get("price") == r.get("price") else None,
                    "pe": float(r["pe"]) if r.get("pe") and r.get("pe") == r.get("pe") else None,
                    "funds_yi": float(r["funds"]) if r.get("funds") == r.get("funds") else None,
                    "ballot_pct": float(r["ballot"]) if r.get("ballot") == r.get("ballot") else None,
                }
            )
        data = {"items": items, "note": f"区间 {start}~{end}; ipo_date=申购日; price/pe 为 0 表示尚未定价"}
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"IPO 日历获取失败: {e}"[:120])
