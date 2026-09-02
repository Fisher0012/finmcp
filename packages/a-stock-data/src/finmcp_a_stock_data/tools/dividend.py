"""分红历史 tool: get_dividend_history (SPEC F5)

接口存在性: 2026-09-02 带 token 实调验证 pro.dividend(ts_code=...) 有真实返回。
字段口径（tushare 官方文档 doc_id=103, 2026-09-02 核实）:
- cash_div = 每股税后现金分红; cash_div_tax = 每股税前现金分红（两者均透传, 不混淆标注）
- div_proc = 实施进度（"实施" / "预案" / "股东大会通过" 等）; stk_div = 每股送转合计
"""

import math
from datetime import datetime, timedelta
from typing import Any

from finmcp_common.responses import EMPTY_CONFIRMED_ABSENT, error_response, ok_response

_NOTE = (
    "仅含 div_proc=实施 的分红记录; cash_div=每股税后现金分红(元), "
    "cash_div_tax=每股税前现金分红(元), stk_div=每股送转合计(股); 非实施状态计数见 other_proc_counts"
)


def _num(v: Any) -> float | None:
    """数值清洗: NaN/None → None"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 4)


def get_dividend_history(stock_code: str, years: int = 5) -> dict[str, Any]:
    """分红送股历史 (tushare dividend): 近 N 年已实施的现金分红与送转记录。

    只保留 div_proc="实施" 的记录（预案/股东大会通过等状态仅计数不展开）。
    cash_div 为每股税后现金分红, cash_div_tax 为每股税前现金分红（tushare 官方口径）。

    Args:
        stock_code: 股票代码（如 600519.SH）
        years: 回溯年数, 默认 5
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    if years < 1:
        return error_response(code="INVALID_PARAM", message="years 必须 >= 1")
    try:
        import tushare as ts

        pro = ts.pro_api()
        df = pro.dividend(
            ts_code=stock_code,
            fields="ts_code,end_date,ann_date,div_proc,stk_div,cash_div,cash_div_tax",
        )
        if df is None or df.empty:
            return ok_response(
                data={"stock_code": stock_code, "dividends": [], "note": "无分红记录"},
                source="tushare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        cutoff = (datetime.now() - timedelta(days=365 * years)).strftime("%Y%m%d")
        df = df[df["end_date"].astype(str) >= cutoff]
        if df.empty:
            return ok_response(
                data={"stock_code": stock_code, "dividends": [], "note": f"近 {years} 年无分红记录"},
                source="tushare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        # 只保留已实施记录, 其余进度状态计数留痕
        other_counts: dict[str, int] = {}
        rows: list[dict[str, Any]] = []
        for _, r in df.sort_values("end_date", ascending=False).iterrows():
            proc = str(r.get("div_proc") or "").strip()
            if proc != "实施":
                if proc:
                    other_counts[proc] = other_counts.get(proc, 0) + 1
                continue
            rows.append(
                {
                    "end_date": str(r.get("end_date") or ""),
                    "ann_date": str(r.get("ann_date") or ""),
                    "cash_div": _num(r.get("cash_div")),
                    "cash_div_tax": _num(r.get("cash_div_tax")),
                    "stk_div": _num(r.get("stk_div")),
                }
            )
        if not rows:
            return ok_response(
                data={
                    "stock_code": stock_code,
                    "dividends": [],
                    "other_proc_counts": other_counts,
                    "note": f"近 {years} 年无已实施分红（非实施状态计数见 other_proc_counts）",
                },
                source="tushare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        return ok_response(
            data={
                "stock_code": stock_code,
                "dividends": rows,
                "other_proc_counts": other_counts,
                "note": _NOTE,
            },
            source="tushare",
        )
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"tushare dividend 调用失败: {str(e)[:200]}",
            source="tushare",
        )
