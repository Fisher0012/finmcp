"""get_valuation_history — 历史估值分位（数据层补强②, 2026-09-03）。

补"当前 PE/PB 处于历史什么位置"这一高频刚需（此前无数据, 评测 Q1-06 只能答缺口）。
数据源: tushare daily_basic 历史序列（pe_ttm/pb 日频）。
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


def _percentile_rank(series: list[float], value: float) -> float:
    """value 在 series 中的分位(0~100, 越高越贵)"""
    below = sum(1 for x in series if x <= value)
    return round(below / len(series) * 100, 1)


def get_valuation_history(stock_code: str, years: int = 5) -> dict[str, Any]:
    """获取个股历史估值序列与当前分位。

    返回当前 pe_ttm/pb 在近 N 年日频序列中的百分位（越高越贵）、
    区间最高/最低/中位数。序列不足 250 个交易日时显式拒绝分位计算（样本不足不硬算）。

    Args:
        stock_code: 股票代码（如 600519.SH）
        years: 回溯年数, 默认 5, 范围 1~10
    """
    code = (stock_code or "").strip()
    if not code:
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    years = max(1, min(int(years or 5), 10))

    cache_key = _cache.make_key("tushare", "val_history", code, str(years))
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="tushare", cache_hit=True)

    try:
        import tushare as ts

        pro = ts.pro_api()
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=int(years * 365.25))).strftime("%Y%m%d")
        df = pro.daily_basic(
            ts_code=code,
            start_date=start,
            end_date=end,
            fields="trade_date,pe_ttm,pb,total_mv",
        )
        if df is None or df.empty:
            return error_response(
                code="DATA_NOT_FOUND",
                message=f"未取得 {code} 的历史估值序列",
                hint="检查代码是否正确; 新股可能无足够历史",
                source="tushare",
            )
        rows = df.dropna(subset=["pe_ttm"])
        pe_series = [float(x) for x in rows["pe_ttm"].tolist() if x == x and x > 0]
        pb_series = [float(x) for x in df.dropna(subset=["pb"])["pb"].tolist() if x == x and x > 0]
        if len(pe_series) < 250:
            return ok_response(
                data={
                    "stock_code": code,
                    "years": years,
                    "sample_days": len(pe_series),
                    "note": f"有效样本仅 {len(pe_series)} 个交易日(<250), 不足以计算可靠历史分位",
                },
                source="tushare",
            )
        latest = df.sort_values("trade_date").iloc[-1]
        cur_pe = float(latest["pe_ttm"]) if latest["pe_ttm"] == latest["pe_ttm"] else None
        cur_pb = float(latest["pb"]) if latest["pb"] == latest["pb"] else None
        pe_sorted = sorted(pe_series)
        data = {
            "stock_code": code,
            "years": years,
            "sample_days": len(pe_series),
            "as_of": str(latest["trade_date"]),
            "current_pe_ttm": cur_pe,
            "pe_percentile": _percentile_rank(pe_series, cur_pe) if cur_pe else None,
            "pe_min": round(pe_sorted[0], 2),
            "pe_median": round(pe_sorted[len(pe_sorted) // 2], 2),
            "pe_max": round(pe_sorted[-1], 2),
            "current_pb": cur_pb,
            "pb_percentile": _percentile_rank(pb_series, cur_pb) if cur_pb and pb_series else None,
            "note": "分位为近 N 年日频序列中的百分位, 越高越贵; 剔除负 PE 样本",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except FinMCPError as e:
        return handle_tool_error(e, source="tushare")
    except Exception as e:
        return handle_tool_error(e)
