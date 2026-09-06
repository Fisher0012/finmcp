"""筹码与资金行为 tools: 融资融券/股东户数/十大流通股东/大宗交易（数据层 2.0 批次三）。

接口与字段 2026-09-04 带 token 实调确认:
margin(trade_date 三所 rzye/rzrqye) / stk_holdernumber(ann_date,end_date,holder_num) /
top10_floatholders(holder_name,hold_ratio,hold_float_ratio,hold_change,holder_type) /
block_trade(trade_date,price,vol,amount,buyer,seller)。
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from finmcp_common.errors import FinMCPError
from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager
from ..errors import handle_tool_error

logger = logging.getLogger(__name__)
_cache = CacheManager()


def _pro() -> "Any":  # tushare 无类型桩, 返回 Any
    import tushare as ts

    return ts.pro_api()


def get_margin_flow(days: int = 30) -> dict[str, Any]:
    """全市场融资融券余额日度序列(三所合计)。杠杆资金情绪指标。

    Args:
        days: 回溯自然日, 默认 30, 范围 7~120
    """
    days = max(7, min(int(days or 30), 120))
    cache_key = _cache.make_key("tushare", "margin_flow", str(days))
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="tushare", cache_hit=True)
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = _pro().margin(start_date=start, end_date=end)
        if df is None or df.empty:
            return error_response(code="DATA_NOT_FOUND", message="未取得融资融券数据", source="tushare")
        # 按日汇总三所(单位: 元 → 亿元)
        g = df.groupby("trade_date")[["rzye", "rzrqye"]].sum().sort_index()
        series = [
            {
                "trade_date": d,
                "margin_balance_yi": round(float(row["rzye"]) / 1e8, 1),
                "total_balance_yi": round(float(row["rzrqye"]) / 1e8, 1),
            }
            for d, row in g.iterrows()
        ]
        first, last = series[0], series[-1]
        data = {
            "series": series[-20:],
            "latest": last,
            "change_yi": round(last["margin_balance_yi"] - first["margin_balance_yi"], 1),
            "note": f"融资余额三所合计, 单位亿元; "
            f"区间 {first['trade_date']}~{last['trade_date']} 变化为正=杠杆资金加仓",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except FinMCPError as e:
        return handle_tool_error(e, source="tushare")
    except Exception as e:
        return handle_tool_error(e)


def get_holder_number(stock_code: str) -> dict[str, Any]:
    """个股股东户数趋势(最近8期)。户数下降=筹码集中, 上升=筹码分散。"""
    code = (stock_code or "").strip()
    if not code:
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    cache_key = _cache.make_key("tushare", "holdernum", code)
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="tushare", cache_hit=True)
    try:
        df = _pro().stk_holdernumber(ts_code=code)
        if df is None or df.empty:
            return error_response(code="DATA_NOT_FOUND", message=f"未取得 {code} 股东户数", source="tushare")
        df = df.dropna(subset=["holder_num"]).sort_values("end_date").tail(8)
        series = [{"end_date": r["end_date"], "holder_num": int(r["holder_num"])} for _, r in df.iterrows()]
        chg = None
        if len(series) >= 2 and series[-2]["holder_num"]:
            chg = round(
                (series[-1]["holder_num"] - series[-2]["holder_num"]) / series[-2]["holder_num"] * 100,
                2,
            )
        data = {
            "stock_code": code,
            "series": series,
            "latest_change_pct": chg,
            "note": "股东户数环比下降通常代表筹码集中(大资金吸筹), 上升代表筹码分散",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except FinMCPError as e:
        return handle_tool_error(e, source="tushare")
    except Exception as e:
        return handle_tool_error(e)


def get_top_float_holders(stock_code: str) -> dict[str, Any]:
    """个股最新一期十大流通股东(名称/持股比例/较上期变动)。机构进出的直接证据。"""
    code = (stock_code or "").strip()
    if not code:
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    cache_key = _cache.make_key("tushare", "topfloat", code)
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="tushare", cache_hit=True)
    try:
        df = _pro().top10_floatholders(ts_code=code)
        if df is None or df.empty:
            return error_response(code="DATA_NOT_FOUND", message=f"未取得 {code} 十大流通股东", source="tushare")
        latest_period = df["end_date"].max()
        rows = df[df["end_date"] == latest_period].sort_values("hold_ratio", ascending=False)
        holders = [
            {
                "name": r["holder_name"],
                "hold_ratio_pct": r["hold_ratio"],
                "float_ratio_pct": r["hold_float_ratio"],
                "change_shares": r["hold_change"],
                "type": r["holder_type"],
            }
            for _, r in rows.iterrows()
        ]
        data = {
            "stock_code": code,
            "period": latest_period,
            "holders": holders,
            "note": "change_shares 为较上期持股变动(股), 正=增持 负=减持 0=不变; hold_ratio 为占总股本比例(%)",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except FinMCPError as e:
        return handle_tool_error(e, source="tushare")
    except Exception as e:
        return handle_tool_error(e)


def get_block_trades(stock_code: str, days: int = 90) -> dict[str, Any]:
    """个股大宗交易明细(近N天)。频繁折价大宗=股东出货信号之一。

    Args:
        stock_code: 股票代码（如 600519.SH）
        days: 回溯自然日, 默认 90, 范围 7~365
    """
    code = (stock_code or "").strip()
    if not code:
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    days = max(7, min(int(days or 90), 365))
    cache_key = _cache.make_key("tushare", "blocktrade", code, str(days))
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="tushare", cache_hit=True)
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = _pro().block_trade(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            return ok_response(
                data={
                    "stock_code": code,
                    "days": days,
                    "trades": [],
                    "note": f"近{days}天无大宗交易记录(确认无, 非查询失败)",
                },
                source="tushare",
            )
        trades = [
            {
                "trade_date": r["trade_date"],
                "price": r["price"],
                "amount_wan": round(float(r["amount"]), 1),
                "buyer": r["buyer"],
                "seller": r["seller"],
            }
            for _, r in df.sort_values("trade_date", ascending=False).head(20).iterrows()
        ]
        data = {
            "stock_code": code,
            "days": days,
            "count": len(df),
            "total_amount_wan": round(float(df["amount"].sum()), 1),
            "trades": trades,
            "note": "amount 单位万元(tushare 口径); 判断折溢价需对照当日收盘价(get_latest_quote)",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except FinMCPError as e:
        return handle_tool_error(e, source="tushare")
    except Exception as e:
        return handle_tool_error(e)
