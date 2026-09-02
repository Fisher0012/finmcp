"""北向/南向资金 tool: get_northbound_flow (SPEC F5)

接口存在性: 2026-09-02 带 token 实调验证 pro.moneyflow_hsgt(start_date, end_date) 有真实返回
（北向可得性调研结论=可得）。
单位口径（tushare 官方文档 doc_id=47 + SDK reference.py docstring, 2026-09-02 双源核实）:
hgt / sgt / north_money / south_money 单位均为百万元。

2024 口径调整背景: 交易所自 2024-08 起调整沪深港通信息披露, 盘中实时北向资金流向已停发,
本接口为日度收盘口径数据; 个别日期字段缺失时透传 None, 不做估算填充。
"""

import math
from datetime import datetime, timedelta
from typing import Any

from finmcp_common.responses import EMPTY_CONFIRMED_ABSENT, error_response, ok_response

_MAX_DAYS = 365  # tushare moneyflow_hsgt 单次最多 300 条记录, 365 自然日内交易日不超上限

_UNIT_NOTE = (
    "单位: 百万元 (tushare moneyflow_hsgt 官方口径, hgt/sgt/north_money/south_money 均为百万元); "
    "north_money=北向资金, south_money=南向资金, hgt=沪股通, sgt=深股通; "
    "2024-08 起盘中实时北向资金已停发, 本数据为日度收盘口径, 缺失值透传 None"
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


def get_northbound_flow(days: int = 30) -> dict[str, Any]:
    """沪深港通资金流向 (tushare moneyflow_hsgt): 近 N 天北向/南向资金日度数据。

    金额单位为百万元（tushare 官方口径, 原值透传不换算）。
    2024-08 起交易所停止盘中实时披露北向资金, 本工具仅提供日度收盘口径数据。

    Args:
        days: 回溯自然日天数, 默认 30, 最大 365
    """
    if days < 1:
        return error_response(code="INVALID_PARAM", message="days 必须 >= 1")
    days = min(days, _MAX_DAYS)
    try:
        import tushare as ts

        pro = ts.pro_api()
        now = datetime.now()
        start_date = (now - timedelta(days=days)).strftime("%Y%m%d")
        end_date = now.strftime("%Y%m%d")
        df = pro.moneyflow_hsgt(start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return ok_response(
                data={"daily": [], "note": f"近 {days} 天无沪深港通资金数据"},
                source="tushare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        rows: list[dict[str, Any]] = []
        for _, r in df.sort_values("trade_date", ascending=False).iterrows():
            rows.append(
                {
                    "trade_date": str(r.get("trade_date") or ""),
                    "north_money": _num(r.get("north_money")),
                    "south_money": _num(r.get("south_money")),
                    "hgt": _num(r.get("hgt")),
                    "sgt": _num(r.get("sgt")),
                }
            )
        return ok_response(data={"daily": rows, "note": _UNIT_NOTE}, source="tushare")
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"tushare moneyflow_hsgt 调用失败: {str(e)[:200]}",
            source="tushare",
        )
