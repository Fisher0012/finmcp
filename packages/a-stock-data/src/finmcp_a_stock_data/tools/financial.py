"""get_financial_indicator 和 get_financial_report_summary tools"""

from typing import Any

from finmcp_common.errors import FinMCPError, InvalidParamError
from finmcp_common.responses import error_response, ok_response
from finmcp_common.stock_code import normalize_stock_code

from ..cache import CacheManager
from ..data_sources.base import StockDataSource
from ..errors import handle_tool_error
from ..utils import get_data_source

_cache = CacheManager()
_source = None


def _get_source() -> StockDataSource:
    global _source
    if _source is None:
        _source = get_data_source()
    return _source


# 合法的 indicator 名称
VALID_INDICATORS = {
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "revenue_yoy",
    "net_profit_yoy",
    "debt_to_asset",
    "current_ratio",
    "asset_turnover",
    "inventory_turnover",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "eps",
    "bvps",
    "ocf_per_share",
}


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
    try:
        code = normalize_stock_code(stock_code)
    except ValueError as e:
        return handle_tool_error(InvalidParamError(str(e)))

    # 校验 indicators
    if indicators:
        invalid = [i for i in indicators if i not in VALID_INDICATORS]
        if invalid:
            return error_response(
                code="INVALID_PARAM",
                message=f"不支持的指标: {invalid}",
                hint=f"支持的指标: {sorted(VALID_INDICATORS)}",
            )

    years = min(max(1, years), 20)

    try:
        source = _get_source()
        ind_key = ",".join(sorted(indicators)) if indicators else "all"
        cache_key = _cache.make_key(
            source.name,
            "fina_indicator",
            code,
            ind_key,
            str(years),
        )
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source=source.name, cache_hit=True)

        results = source.get_financial_indicator(code, indicators, years)
        _cache.set(cache_key, results, ttl_category="financial")
        return ok_response(data=results, source=source.name)

    except FinMCPError as e:
        return handle_tool_error(e, source=_get_source().name if _source else "unknown")
    except Exception as e:
        return handle_tool_error(e)


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
    try:
        code = normalize_stock_code(stock_code)
    except ValueError as e:
        return handle_tool_error(InvalidParamError(str(e)))

    # 校验 report_period 格式
    ts_period = None
    if report_period:
        valid_endings = ("03-31", "06-30", "09-30", "12-31")
        if report_period[5:] not in valid_endings:
            return error_response(
                code="INVALID_PARAM",
                message=f"report_period 必须是季度末日期，收到: {report_period}",
                hint="有效值示例：2024-12-31, 2024-09-30, 2024-06-30, 2024-03-31",
            )
        ts_period = report_period.replace("-", "")

    try:
        source = _get_source()
        cache_key = _cache.make_key(
            source.name,
            "fina_report",
            code,
            ts_period or "latest",
        )
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source=source.name, cache_hit=True)

        result = source.get_financial_report(code, ts_period)
        _cache.set(cache_key, result, ttl_category="financial")
        return ok_response(data=result, source=source.name)

    except FinMCPError as e:
        return handle_tool_error(e, source=_get_source().name if _source else "unknown")
    except Exception as e:
        return handle_tool_error(e)


def get_earnings_express(
    stock_code: str,
    period: str | None = None,
) -> dict[str, Any]:
    """业绩快报(正式财报披露前的快速业绩数据, 比业绩预告的区间更精确)。

    period 形如 2026-06-30(可选, 不传返回近年各期)。
    典型场景：问最新业绩/业绩是否超预期、正式财报未出时调用。

    (2026-09-10 补真实现: a63e85f 假部署事故根治——数据源层 f1b6a1d 已有,
    工具封套层从未落仓, 消费侧 workbench 曾长期 import 失败。)
    """
    try:
        code = normalize_stock_code(stock_code)
    except ValueError as e:
        return handle_tool_error(InvalidParamError(str(e)))
    try:
        source = _get_source()
        impl = getattr(source, "get_earnings_express", None)
        if impl is None:
            return error_response(
                code="UNSUPPORTED_SOURCE",
                message=f"数据源 {source.name} 不支持业绩快报",
                hint="需要 tushare 数据源",
            )
        cache_key = _cache.make_key(source.name, "express", code, str(period or "all"))
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source=source.name, cache_hit=True)
        results = impl(code, period)
        _cache.set(cache_key, results, ttl_category="financial")
        return ok_response(data=results, source=source.name)
    except FinMCPError as e:
        return handle_tool_error(e, source=_get_source().name if _source else "unknown")
    except Exception as e:
        return handle_tool_error(e)


def get_disclosure_date(
    stock_code: str,
) -> dict[str, Any]:
    """财报披露计划(各报告期的预约披露日/实际披露日)。

    典型场景：问何时出财报/做财报前瞻排期时调用。

    (2026-09-10 补真实现, 同 get_earnings_express 事故根治。)
    """
    try:
        code = normalize_stock_code(stock_code)
    except ValueError as e:
        return handle_tool_error(InvalidParamError(str(e)))
    try:
        source = _get_source()
        impl = getattr(source, "get_disclosure_date", None)
        if impl is None:
            return error_response(
                code="UNSUPPORTED_SOURCE",
                message=f"数据源 {source.name} 不支持披露计划",
                hint="需要 tushare 数据源",
            )
        cache_key = _cache.make_key(source.name, "disclosure", code)
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source=source.name, cache_hit=True)
        results = impl(code)
        _cache.set(cache_key, results, ttl_category="financial")
        return ok_response(data=results, source=source.name)
    except FinMCPError as e:
        return handle_tool_error(e, source=_get_source().name if _source else "unknown")
    except Exception as e:
        return handle_tool_error(e)
