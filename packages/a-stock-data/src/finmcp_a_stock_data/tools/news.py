"""个股公告 tool

数据来源：
- 巨潮公告检索（cninfo_ann）: 公司公告（原 tushare anns_d 无接口权限, F3 B 方案换源）
- 东财公告 API: 补充覆盖（announcements_em; market_news 为过渡别名）

注意: 当前无真正的 7x24 快讯源, 不得以"新闻/快讯"名义描述东财公告数据（F2 名实修正）。
"""

from typing import Any

from finmcp_common.errors import FinMCPError
from finmcp_common.responses import (
    EMPTY_CONFIRMED_ABSENT,
    EMPTY_UNKNOWN,
    error_response,
    ok_response,
    strict_contract,
)

from ..data_sources.base import StockDataSource
from ..errors import handle_tool_error
from ..utils import get_data_source

_source = None


def _get_source() -> StockDataSource:
    global _source
    if _source is None:
        _source = get_data_source()
    return _source


def _classify_attempts(attempts: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """由逐源留痕推断整体状态 → (全部源失败, 空数据时的 empty_reason)

    empty_reason 语义（SPEC F1 §2.1）: 只有所有源都正常响应且明确无记录才算
    confirmed_absent；任一源失败时空数据不可与"确无"混淆。
    """
    outcomes = [a.get("outcome") for a in attempts]
    all_failed = bool(outcomes) and all(o == "error" for o in outcomes)
    if any(o == "error" for o in outcomes):
        return all_failed, EMPTY_UNKNOWN
    return False, EMPTY_CONFIRMED_ABSENT


def get_stock_news(stock_code: str, days: int = 30) -> dict[str, Any]:
    """获取个股公告（巨潮公告 + 东财公告双源聚合）。

    覆盖业绩预告、股权变动、重大合同等公司公告，帮助分析近期
    可能影响股价的事件。注意：数据为公告而非 7x24 新闻快讯；
    各源成败见 meta.attempts，空结果语义见 meta.empty_reason。

    Args:
        stock_code: 股票代码（如 688256.SH）
        days: 查询天数（默认 30 天）
    """
    if not stock_code or not stock_code.strip():
        return error_response(
            code="INVALID_PARAM",
            message="stock_code 不能为空",
        )

    days = min(max(1, days), 90)

    try:
        source = _get_source()
        results = source.get_stock_news(stock_code, days)  # type: ignore[attr-defined]  # 仅 TushareSource 实现, 基类补齐见 SPEC F1
        attempts = results.pop("_fetch_attempts", [])
        all_failed, empty_reason = _classify_attempts(attempts)
        has_data = bool(results.get("announcements") or results.get("announcements_em") or results.get("market_news"))
        if all_failed and strict_contract():
            return error_response(
                code="UPSTREAM_ERROR",
                message="公告/新闻上游数据源全部失败",
                hint="稍后重试；各源失败详情见 meta.attempts",
                source=source.name,
                attempts=attempts,
            )
        return ok_response(
            data=results,
            source=source.name,
            attempts=attempts,
            empty_reason=None if has_data else empty_reason,
        )
    except FinMCPError as e:
        return handle_tool_error(e, source=_get_source().name if _source else "unknown")
    except Exception as e:
        return handle_tool_error(e)


def get_market_signals(stock_code: str, days: int = 5) -> dict[str, Any]:
    """获取个股近期市场异动信号。

    检测涨跌停、龙虎榜上榜等异常交易信号，
    帮助判断市场对该股票的关注度和资金动向。

    Args:
        stock_code: 股票代码（如 688256.SH）
        days: 查询天数（默认 5 个交易日）
    """
    if not stock_code or not stock_code.strip():
        return error_response(
            code="INVALID_PARAM",
            message="stock_code 不能为空",
        )

    days = min(max(1, days), 30)

    try:
        source = _get_source()
        results = source.get_market_signals(stock_code, days)  # type: ignore[attr-defined]  # 仅 TushareSource 实现, 基类补齐见 SPEC F1
        attempts = results.pop("_fetch_attempts", [])
        all_failed, empty_reason = _classify_attempts(attempts)
        if all_failed:
            # API 全挂时 has_signals=False 是"未知"而非"无异动"，禁止伪装（SPEC F1）
            results["has_signals"] = None
            if strict_contract():
                return error_response(
                    code="UPSTREAM_ERROR",
                    message="异动信号上游查询全部失败",
                    hint="稍后重试；逐源失败天数见 meta.attempts",
                    source=source.name,
                    attempts=attempts,
                )
        has_data = bool(results.get("limit_events") or results.get("toplist_events"))
        return ok_response(
            data=results,
            source=source.name,
            attempts=attempts,
            empty_reason=None if has_data else empty_reason,
        )
    except FinMCPError as e:
        return handle_tool_error(e, source=_get_source().name if _source else "unknown")
    except Exception as e:
        return handle_tool_error(e)
