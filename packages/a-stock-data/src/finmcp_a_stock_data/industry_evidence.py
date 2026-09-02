"""行业经营样本证据的确定性聚合。

本模块不发起网络请求，只把市值前列成分的同期年报指标聚合为
可追溯的样本证据。样本统计不代表全行业总量或行业景气结论。

（自 workbench lib/fin_industry_evidence.py 下沉, SPEC F3 §3.3；逻辑保持一致）
"""

from __future__ import annotations

import math
import re
from statistics import median
from typing import Any

EVIDENCE_VERSION = "2026.08.31-v1"
EVIDENCE_TYPE = "market_cap_leading_constituent_annual_sample"

METRIC_DEFINITIONS = {
    "revenue_yoy": ("营收同比", "%", True, "direct_or_recalculated_from_annual_reports"),
    "net_profit_yoy": ("净利润同比", "%", True, "direct_or_recalculated_when_prior_profit_positive"),
    "gross_margin": ("毛利率", "%", False, "direct_financial_indicator"),
    "net_margin": ("净利率", "%", False, "direct_financial_indicator"),
    "inventory_turnover": ("存货周转率", "次", False, "direct_financial_indicator_only"),
    "inventory_to_revenue_pct": ("存货/营收", "%", False, "recalculated_from_same_period_annual_report"),
    "operating_cashflow_margin": ("经营现金流/营收", "%", False, "recalculated_from_same_period_annual_report"),
    "rd_expense_ratio": ("研发费用/营收", "%", False, "recalculated_from_same_period_annual_report"),
}

UNAVAILABLE_DIRECT_SERIES = (
    "orders",
    "backlog",
    "capacity_utilization",
    "product_or_spot_price",
    "shipments",
    "industry_inventory_series",
    "industry_aggregate_revenue_or_profit",
)


def _finite_number(value: Any) -> float | None:
    """只接受可可靠聚合的有限数值，排除 bool、NaN 和无穷值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _annual_records(result: Any) -> dict[str, dict[str, Any]]:
    """把单只公司返回值收敛为年报期 -> 指标记录。"""
    if not isinstance(result, dict) or not result.get("ok"):
        return {}
    records = result.get("data")
    if not isinstance(records, list):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        period = str(record.get("report_period") or "")
        if re.fullmatch(r"\d{4}-12-31", period):
            output.setdefault(period, record)
    return output


def _market_cap(row: dict[str, Any]) -> float | None:
    return _finite_number(row.get("market_cap_yi"))


def _report_data(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict) or not result.get("ok"):
        return {}
    data = result.get("data")
    return data if isinstance(data, dict) else {}


def _ratio_percent(numerator: Any, denominator: Any) -> float | None:
    numerator_value = _finite_number(numerator)
    denominator_value = _finite_number(denominator)
    if numerator_value is None or denominator_value is None or denominator_value == 0:
        return None
    return numerator_value / denominator_value * 100


def _metric_value(
    field: str,
    indicator_record: dict[str, Any],
    current_report: dict[str, Any],
    prior_report: dict[str, Any],
) -> float | None:
    direct_value = _finite_number(indicator_record.get(field))
    if direct_value is not None:
        return direct_value
    if field == "revenue_yoy":
        current_revenue = _finite_number(current_report.get("revenue"))
        prior_revenue = _finite_number(prior_report.get("revenue"))
        if current_revenue is not None and prior_revenue is not None and prior_revenue > 0:
            return _ratio_percent(
                current_revenue - prior_revenue,
                prior_revenue,
            )
    if field == "net_profit_yoy":
        current_profit = _finite_number(current_report.get("net_profit"))
        prior_profit = _finite_number(prior_report.get("net_profit"))
        if current_profit is not None and prior_profit is not None and prior_profit > 0:
            return _ratio_percent(
                current_profit - prior_profit,
                prior_profit,
            )
    if field == "inventory_to_revenue_pct":
        return _ratio_percent(current_report.get("inventory"), current_report.get("revenue"))
    if field == "operating_cashflow_margin":
        return _ratio_percent(current_report.get("operating_cashflow"), current_report.get("revenue"))
    if field == "rd_expense_ratio":
        return _ratio_percent(current_report.get("rd_expense"), current_report.get("revenue"))
    return None


def aggregate_industry_operating_evidence(
    industry_name: str,
    overview_data: dict[str, Any],
    financial_results_by_code: dict[str, Any],
    sample_limit: int,
    annual_report_results_by_code: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    聚合市值前列公司的最新共同年报期指标。

    若成功样本间没有共同年报期，或共同期样本少于 2 家，则返回
    `insufficient_evidence`，不输出任何样本中位数。
    """
    overview = overview_data if isinstance(overview_data, dict) else {}
    stocks = [row for row in (overview.get("stocks") or []) if isinstance(row, dict)]
    bounded_limit = max(1, min(int(sample_limit or 1), 10))
    selected = stocks[:bounded_limit]

    sample_records: dict[str, dict[str, dict[str, Any]]] = {}
    entities: list[dict[str, Any]] = []
    for row in selected:
        code = str(row.get("stock_code") or row.get("ts_code") or row.get("code") or "")
        records = _annual_records((financial_results_by_code or {}).get(code))
        if records:
            sample_records[code] = records
        entities.append(
            {
                "stock_code": code,
                "name": str(row.get("name") or ""),
                "market_cap_yi": _market_cap(row),
                "annual_periods": sorted(records, reverse=True),
            }
        )

    period_sets = [set(records) for records in sample_records.values() if records]
    common_periods = set.intersection(*period_sets) if period_sets else set()
    report_period = max(common_periods) if common_periods else None
    included_codes = [code for code, records in sample_records.items() if report_period in records]

    industry_total_market_cap = _finite_number(
        ((overview.get("summary") or {}).get("total_market_cap_yi"))
        if isinstance(overview.get("summary"), dict)
        else None
    )
    evidence_market_cap = sum(
        _market_cap(row) or 0.0
        for row in selected
        if str(row.get("stock_code") or row.get("ts_code") or row.get("code") or "") in included_codes
    )
    market_cap_coverage = (
        round(evidence_market_cap / industry_total_market_cap * 100, 2)
        if industry_total_market_cap and industry_total_market_cap > 0
        else None
    )

    metrics: dict[str, dict[str, Any]] = {}
    enough_sample = len(included_codes) >= 2 and report_period is not None
    if enough_sample and report_period is not None:
        prior_period = f"{int(report_period[:4]) - 1}-12-31"
        annual_reports = annual_report_results_by_code or {}
        for field, (label, unit, include_direction_counts, calculation_method) in METRIC_DEFINITIONS.items():
            values = []
            for code in included_codes:
                reports = annual_reports.get(code) or {}
                value = _metric_value(
                    field,
                    sample_records[code][report_period],
                    _report_data(reports.get(report_period)),
                    _report_data(reports.get(prior_period)),
                )
                if value is not None:
                    values.append(value)
            item: dict[str, Any] = {
                "label": label,
                "unit": unit,
                "calculation_method": calculation_method,
                "available_count": len(values),
                "sample_count": len(included_codes),
                "median": round(float(median(values)), 2) if len(values) >= 2 else None,
                "status": "available" if len(values) >= 2 else "insufficient_metric_coverage",
            }
            if include_direction_counts:
                item.update(
                    {
                        "positive_count": sum(1 for value in values if value > 0),
                        "zero_count": sum(1 for value in values if value == 0),
                        "negative_count": sum(1 for value in values if value < 0),
                    }
                )
            metrics[field] = item

    return {
        "evidence_version": EVIDENCE_VERSION,
        "evidence_type": EVIDENCE_TYPE,
        "status": "verified_sample" if enough_sample else "insufficient_evidence",
        "industry": industry_name,
        "source": {
            "provider": "Tushare",
            "datasets": ["index_member", "daily_basic", "fina_indicator", "income", "balancesheet", "cashflow"],
            "data_nature": "published_public_market_and_annual_report_data",
        },
        "market_data_trade_date": overview.get("trade_date"),
        "report_period": report_period if enough_sample else None,
        "selection": {
            "method": "market_cap_desc_leading_constituents",
            "sample_limit": bounded_limit,
            "industry_constituent_count": overview.get("total_count"),
            "selected_count": len(selected),
            "financial_success_count": len(sample_records),
            "common_period_sample_count": len(included_codes) if report_period else 0,
            "market_cap_coverage_pct": market_cap_coverage if enough_sample else None,
        },
        "metrics": metrics,
        "sample_entities": entities,
        "unavailable_direct_series": list(UNAVAILABLE_DIRECT_SERIES),
        "boundary": (
            "该证据只表示市值前列公司的同期年报样本，不等同于全行业总量或当前景气排序；"
            "未取得的直接行业序列不得由模型补写。"
        ),
    }
