"""业绩预告 tool: get_earnings_forecast

自 workbench routers/finmcp.py 下沉（SPEC F3 §3.3）。
单位口径: tushare forecast 的 net_profit_min/max 单位为万元, 万元/10_000=亿元,
已对 tushare 原始数据独立核实（docs/EARNINGS_FORECAST_UNIT_VERIFICATION.md【已验证】）,
换算保持 /10_000 不变。
"""

from typing import Any

from finmcp_common.responses import EMPTY_CONFIRMED_ABSENT, error_response, ok_response


def get_earnings_forecast(stock_code: str) -> dict[str, Any]:
    """业绩预告 (tushare forecast): 预增/预减/扭亏 + 净利润区间 + 变动原因。

    业绩超预期是大涨核心驱动, 业绩雷是大跌核心驱动。
    净利润区间单位为亿元（net_profit_min_yi / net_profit_max_yi）。

    Args:
        stock_code: 股票代码（如 600519.SH）
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    try:
        import tushare as ts

        pro = ts.pro_api()
        df = pro.forecast(
            ts_code=stock_code,
            fields="ann_date,end_date,type,p_change_min,p_change_max,net_profit_min,net_profit_max,change_reason,summary",
        )
        if df is None or df.empty:
            # tushare 正常响应且明确空 → confirmed_absent（note 保留在 data 内, 兼容原实现）
            return ok_response(
                data={"forecasts": [], "note": "近期无业绩预告"},
                source="tushare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        df = df.head(5).fillna("")
        rows = []
        for _, r in df.iterrows():
            rows.append(
                {
                    "ann_date": str(r.get("ann_date", "")),
                    "end_date": str(r.get("end_date", "")),
                    "type": r.get("type", ""),
                    "p_change_min": float(r.get("p_change_min") or 0),
                    "p_change_max": float(r.get("p_change_max") or 0),
                    # Tushare forecast 的 net_profit_min/max 单位是万元；1 亿元 = 1 万万元。
                    "net_profit_min_yi": round(float(r.get("net_profit_min") or 0) / 10_000, 2),
                    "net_profit_max_yi": round(float(r.get("net_profit_max") or 0) / 10_000, 2),
                    "change_reason": (r.get("change_reason") or "")[:200],
                    "summary": (r.get("summary") or "")[:200],
                }
            )
        return ok_response(data={"forecasts": rows}, source="tushare")
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"tushare forecast 调用失败: {str(e)[:200]}",
            source="tushare",
        )
