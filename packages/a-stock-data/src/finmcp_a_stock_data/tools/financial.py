"""get_financial_indicator 和 get_financial_report_summary tools"""

from typing import Any

from finmcp_common.responses import ok_response


def get_financial_indicator(
    stock_code: str,
    indicators: list[str] | None = None,
    years: int = 5,
) -> dict[str, Any]:
    """获取个股的核心财务指标，按报告期返回。

    indicators 支持：
    - 盈利能力：roe, roa, gross_margin, net_margin
    - 成长性：revenue_yoy, net_profit_yoy
    - 偿债能力：debt_to_asset, current_ratio
    - 运营效率：asset_turnover, inventory_turnover
    - 估值：pe_ttm, pb, ps_ttm
    - 其他：eps, bvps, ocf_per_share

    indicators=None 返回全部指标。years 控制返回多少年数据（默认 5 年，最大 20 年）。
    返回数据按报告期降序排列。

    典型场景：财务分析、ROE/利润趋势分析、估值对比时调用。
    """
    # Stage 1: stub 数据
    stub_data = [
        {
            "report_period": "2025-12-31",
            "roe": 30.5,
            "roa": 22.1,
            "gross_margin": 91.5,
            "net_margin": 51.2,
            "eps": 60.8,
        },
        {
            "report_period": "2024-12-31",
            "roe": 29.8,
            "roa": 21.5,
            "gross_margin": 91.3,
            "net_margin": 50.8,
            "eps": 57.2,
        },
    ]
    return ok_response(data=stub_data, source="stub", note="Stage 1 stub 数据")


def get_financial_report_summary(
    stock_code: str,
    report_period: str | None = None,
) -> dict[str, Any]:
    """获取个股指定报告期的财报关键科目摘要。

    report_period 格式 "YYYY-MM-DD"，必须是季度末日期（03-31/06-30/09-30/12-31）。
    为 None 时返回最新一期。

    返回三大表关键科目：
    - 利润表：营收、毛利、营业利润、净利润、扣非净利润、研发费用、销售费用
    - 资产负债表：总资产、总负债、股东权益、货币资金、应收账款、存货、商誉
    - 现金流量表：经营性现金流、投资性现金流、筹资性现金流、自由现金流

    金额单位：元（人民币）。

    典型场景：财报分析、深度研究、不同公司财报对比时调用。
    """
    # Stage 1: stub 数据
    stub_data = {
        "stock_code": "600519.SH",
        "report_period": "2025-12-31",
        "revenue": 170000000000.0,
        "gross_profit": 155550000000.0,
        "operating_profit": 115000000000.0,
        "net_profit": 86200000000.0,
        "net_profit_deducted": 85000000000.0,
        "total_assets": 280000000000.0,
        "total_liabilities": 90000000000.0,
        "equity": 190000000000.0,
        "cash": 160000000000.0,
        "operating_cashflow": 90000000000.0,
        "investing_cashflow": -5000000000.0,
        "financing_cashflow": -30000000000.0,
        "free_cashflow": 85000000000.0,
    }
    return ok_response(data=stub_data, source="stub", note="Stage 1 stub 数据")
