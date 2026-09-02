"""行业经营证据 tool: get_industry_operating_evidence

自 workbench routers/finmcp.py + lib/fin_industry_evidence.py 下沉（SPEC F3 §3.3）。
壳逻辑照抄原实现: 行业全景取市值前列样本 → 并发拉财务指标/年报摘要 →
industry_evidence.aggregate_industry_operating_evidence 确定性聚合。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..industry_evidence import aggregate_industry_operating_evidence
from .financial import get_financial_indicator, get_financial_report_summary
from .industry import get_industry_overview


def get_industry_operating_evidence(
    industry_name: str,
    level: int = 2,
    sample_limit: int = 5,
) -> dict[str, Any]:
    """获取行业市值前列样本的同期年报经营指标。

    该工具是有界的样本证据层，不将公司样本统计冒充为全行业总量。

    Args:
        industry_name: 申万行业名称（如"半导体"）
        level: 申万行业级别（1/2/3）, 默认 2
        sample_limit: 样本公司数（2~5）, 默认 5
    """
    if not industry_name or not industry_name.strip():
        return error_response(code="INVALID_PARAM", message="industry_name 不能为空")

    bounded_limit = max(2, min(int(sample_limit or 5), 5))
    overview_result = get_industry_overview(
        industry_name=industry_name,
        level=level,
        sort_by="total_mv",
        limit=bounded_limit,
    )
    if not isinstance(overview_result, dict) or not overview_result.get("ok"):
        # 行业全景失败: 透传其封套（已是本包标准 error_response）
        if isinstance(overview_result, dict):
            return overview_result
        return error_response(code="INTERNAL_ERROR", message="行业全景返回格式无效")

    overview_data = overview_result.get("data") or {}
    stocks = [row for row in (overview_data.get("stocks") or []) if isinstance(row, dict)]
    selected = stocks[:bounded_limit]
    financial_results: dict[str, Any] = {}

    if selected:
        with ThreadPoolExecutor(max_workers=min(len(selected), 5)) as pool:
            futures = {}
            for row in selected:
                code = str(row.get("stock_code") or "")
                if code:
                    futures[pool.submit(get_financial_indicator, code, None, 3)] = code
            for future in as_completed(futures):
                code = futures[future]
                try:
                    financial_results[code] = future.result()
                except Exception as exc:
                    financial_results[code] = {"ok": False, "error": str(exc)[:200]}

    evidence = aggregate_industry_operating_evidence(
        industry_name=industry_name,
        overview_data=overview_data,
        financial_results_by_code=financial_results,
        sample_limit=bounded_limit,
    )
    report_period = evidence.get("report_period")
    annual_report_results: dict[str, dict[str, Any]] = {}
    if report_period:
        prior_period = f"{int(report_period[:4]) - 1}-12-31"
        report_calls: list[tuple[str, str]] = []
        for entity in evidence.get("sample_entities") or []:
            code = str(entity.get("stock_code") or "")
            if code and report_period in (entity.get("annual_periods") or []):
                report_calls.extend(((code, report_period), (code, prior_period)))

        with ThreadPoolExecutor(max_workers=min(len(report_calls), 10) or 1) as pool:
            report_futures = {
                pool.submit(get_financial_report_summary, code, period): (code, period) for code, period in report_calls
            }
            for future in as_completed(report_futures):
                code, period = report_futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)[:200]}
                annual_report_results.setdefault(code, {})[period] = result

        evidence = aggregate_industry_operating_evidence(
            industry_name=industry_name,
            overview_data=overview_data,
            financial_results_by_code=financial_results,
            sample_limit=bounded_limit,
            annual_report_results_by_code=annual_report_results,
        )
    overview_meta = overview_result.get("meta") or {}
    return ok_response(
        data=evidence,
        source=str(overview_meta.get("source") or "tushare"),
        cache_hit=bool(overview_meta.get("cache_hit")),
    )
