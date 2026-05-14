"""get_latest_quote tool"""

from typing import Any

from finmcp_common.responses import ok_response


def get_latest_quote(stock_code: str) -> dict[str, Any]:
    """获取 A 股个股的当前快照（盘中实时，收盘后为收盘数据）。

    返回字段：current_price, change, pct_change, open, high, low,
    prev_close, volume, amount, market_cap_yi, pe_ttm, pb。

    stock_code 支持 "600519"（自动识别）或 "600519.SH" 格式。

    典型场景：用户问"XX 现在多少钱"、"今天涨了多少"时调用。

    注意：缓存 TTL 60 秒，频繁调用同一代码会返回缓存值。
    """
    # Stage 1: stub 数据
    stub_data = {
        "stock_code": "600519.SH",
        "name": "贵州茅台",
        "current_price": 1595.0,
        "change": 20.0,
        "pct_change": 1.27,
        "open": 1580.0,
        "high": 1600.0,
        "low": 1575.0,
        "prev_close": 1575.0,
        "volume": 25000.0,
        "amount": 3987500000.0,
        "market_cap_yi": 20035.8,
        "pe_ttm": 26.5,
        "pb": 8.2,
    }
    return ok_response(data=stub_data, source="stub", note="Stage 1 stub 数据")
