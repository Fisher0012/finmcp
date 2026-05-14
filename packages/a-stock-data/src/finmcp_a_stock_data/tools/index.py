"""get_index_price tool"""

from typing import Any

from finmcp_common.responses import ok_response


def get_index_price(
    index_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily",
) -> dict[str, Any]:
    """获取主要 A 股指数的历史行情。

    支持常见指数：
    - 000001.SH (上证指数)
    - 399001.SZ (深证成指)
    - 399006.SZ (创业板指)
    - 000300.SH (沪深300)
    - 000905.SH (中证500)
    - 000852.SH (中证1000)
    等约 30 个主流指数。

    index_code 必须带交易所后缀（如 000001.SH），因为 000001 同时是上证指数和平安银行。
    period: daily / weekly / monthly。
    start_date / end_date 格式 YYYY-MM-DD；都为 None 时返回最近 60 个交易日。

    典型场景：分析大盘走势、计算个股相对收益时调用。
    """
    # Stage 1: stub 数据
    stub_data = [
        {
            "date": "2026-05-14",
            "open": 3150.0,
            "high": 3180.0,
            "low": 3145.0,
            "close": 3175.0,
            "volume": 350000000.0,
            "amount": 450000000000.0,
            "pct_change": 0.85,
        }
    ]
    return ok_response(data=stub_data, source="stub", note="Stage 1 stub 数据")
