"""龙虎榜与个股两融明细（batch-7 T22 组1）。字段经生产实调确认(2026-09-06)。"""

from datetime import datetime, timedelta
from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager

_cache = CacheManager()


def _pro() -> "Any":  # tushare 无类型桩
    import tushare as ts

    return ts.pro_api()


def _recent_trade_date_try(pro: Any, days: int = 7) -> tuple[str, Any]:
    """从今天往前找最近有龙虎榜数据的交易日, 返回 (日期, df)。"""
    for off in range(days):
        d = (datetime.now() - timedelta(days=off)).strftime("%Y%m%d")
        df = pro.top_list(trade_date=d)
        if df is not None and not df.empty:
            return d, df
    return "", None


def get_top_list(stock_code: str | None = None) -> dict[str, Any]:
    """龙虎榜(最近交易日): 全市场上榜名单或指定个股上榜记录。

    典型场景: "今天龙虎榜有哪些""XX股上龙虎榜了吗/游资动向"。
    l_buy/l_sell=龙虎榜买入/卖出额(元), l_amount=龙虎榜成交额。
    """
    try:
        code = (stock_code or "").strip().upper()
        cache_key = _cache.make_key("tushare", "top_list", code or "all")
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source="tushare", cache_hit=True)
        d, df = _recent_trade_date_try(_pro())
        if df is None:
            return error_response(code="DATA_NOT_FOUND", message="近7日无龙虎榜数据")
        if code:
            df = df[df["ts_code"] == code]
        items = []
        for _, r in df.head(60).iterrows():
            items.append(
                {
                    "name": str(r.get("name") or ""),
                    "close": float(r["close"]) if r.get("close") == r.get("close") else None,
                    "pct_change": float(r["pct_change"]) if r.get("pct_change") == r.get("pct_change") else None,
                    "l_buy_yi": round(float(r["l_buy"]) / 1e8, 2) if r.get("l_buy") == r.get("l_buy") else None,
                    "l_sell_yi": round(float(r["l_sell"]) / 1e8, 2) if r.get("l_sell") == r.get("l_sell") else None,
                    "reason": str(r.get("reason") or "")[:30] if "reason" in df.columns else "",
                }
            )
        data = {
            "trade_date": d,
            "items": items,
            "note": "tushare 龙虎榜; l_buy/l_sell 单位亿元; 未上榜个股返回空列表(confirmed_absent)",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"龙虎榜获取失败: {e}"[:120])


def get_stock_margin_detail(stock_code: str, days: int = 30) -> dict[str, Any]:
    """个股两融明细序列: 融资余额(rzye)/融券余额(rqye)/融资买入(rzmre)等, 日度。

    典型场景: "XX股融资盘怎么样/杠杆资金在加仓吗"。全市场口径另有 get_margin_flow。
    """
    try:
        code = (stock_code or "").strip().upper()
        if not code:
            return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
        cache_key = _cache.make_key("tushare", "margin_detail", code, str(days))
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source="tushare", cache_hit=True)
        start = (datetime.now() - timedelta(days=days + 10)).strftime("%Y%m%d")
        end = datetime.now().strftime("%Y%m%d")
        df = _pro().margin_detail(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            return ok_response(
                data={"items": [], "note": f"{code} 非两融标的或区间无数据(confirmed_absent)"}, source="tushare"
            )
        df = df.sort_values("trade_date")
        items = []
        for _, r in df.iterrows():
            items.append(
                {
                    "date": str(r["trade_date"]),
                    "rzye_yi": round(float(r["rzye"]) / 1e8, 2),
                    "rqye_yi": round(float(r["rqye"]) / 1e8, 2),
                    "rzmre_yi": round(float(r["rzmre"]) / 1e8, 2),
                }
            )
        first, last = items[0], items[-1]
        data = {
            "items": items,
            "note": f"融资余额 {first['date']} {first['rzye_yi']}亿 → {last['date']} "
            f"{last['rzye_yi']}亿; 上升=杠杆资金加仓该股",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"个股两融获取失败: {e}"[:120])
