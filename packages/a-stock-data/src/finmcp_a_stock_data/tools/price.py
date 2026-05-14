"""get_stock_price tool"""

from typing import Any

from finmcp_common.responses import ok_response


def get_stock_price(
    stock_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily",
    adjust: str = "qfq",
) -> dict[str, Any]:
    """获取 A 股个股的历史行情。

    period: daily（日线）/ weekly（周线）/ monthly（月线）。
    adjust: qfq（前复权）/ hfq（后复权）/ none（不复权）。
    start_date / end_date 格式 YYYY-MM-DD；都为 None 时返回最近 60 个交易日。

    返回字段：date, open, high, low, close, volume, amount, pct_change, turnover_rate。

    典型场景：分析走势、计算涨跌、回测时调用。

    注意：当日数据需在收盘后获取才完整；盘中数据的 close 为最新价而非收盘价。
    """
    # Stage 1: stub 数据
    stub_data = [
        {
            "date": "2026-05-14",
            "open": 1580.0,
            "high": 1600.0,
            "low": 1575.0,
            "close": 1595.0,
            "volume": 25000.0,
            "amount": 3987500000.0,
            "pct_change": 1.27,
            "turnover_rate": 0.2,
        }
    ]
    return ok_response(data=stub_data, source="stub", note="Stage 1 stub 数据")
