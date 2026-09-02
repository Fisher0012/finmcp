"""股东侧 tools: get_major_shareholder_change + get_pledge_status

自 workbench routers/finmcp.py 下沉（SPEC F3 §3.3）。tushare 直调,
data 内层字段与原实现保持一致, 外层升级为三态封套。
"""

from typing import Any

from finmcp_common.responses import EMPTY_CONFIRMED_ABSENT, error_response, ok_response


def get_major_shareholder_change(stock_code: str) -> dict[str, Any]:
    """大股东增减持 (tushare stk_holdertrade): 减持=利空信号、增持=偏多信号。

    Args:
        stock_code: 股票代码（如 600519.SH）
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    try:
        import tushare as ts

        pro = ts.pro_api()
        df = pro.stk_holdertrade(
            ts_code=stock_code,
            fields="ann_date,holder_name,in_de,change_vol,change_ratio,after_share,after_ratio,avg_price",
        )
        if df is None or df.empty:
            return ok_response(
                data={"changes": [], "note": "近期无大股东增减持"},
                source="tushare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        df = df.head(20).fillna("")
        rows = []
        net_change = 0.0
        for _, r in df.iterrows():
            in_de = str(r.get("in_de", ""))  # IN=增持, DE=减持
            cv = float(r.get("change_vol") or 0)
            cv_yi = cv / 1e8
            ratio = float(r.get("change_ratio") or 0)
            sign = 1 if in_de == "IN" else -1
            net_change += sign * cv_yi
            rows.append(
                {
                    "ann_date": str(r.get("ann_date", "")),
                    "holder": str(r.get("holder_name", "")),
                    "direction": "增持" if in_de == "IN" else "减持",
                    "change_vol_yi": round(cv_yi, 4),
                    "change_ratio_pct": round(ratio, 4),
                    "after_ratio_pct": round(float(r.get("after_ratio") or 0), 4),
                    "avg_price": r.get("avg_price", "") if r.get("avg_price") else "",
                }
            )
        return ok_response(
            data={
                "changes": rows,
                "net_change_yi_total": round(net_change, 4),
                "note": f"汇总: 净增持{round(net_change, 4)}亿股 (正=偏多/负=偏空)",
            },
            source="tushare",
        )
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"tushare stk_holdertrade 调用失败: {str(e)[:200]}",
            source="tushare",
        )


def get_pledge_status(stock_code: str) -> dict[str, Any]:
    """股票质押状态 (tushare pledge_stat): 高质押率=黑天鹅前兆。

    Args:
        stock_code: 股票代码（如 600519.SH）
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    try:
        import tushare as ts

        pro = ts.pro_api()
        df = pro.pledge_stat(ts_code=stock_code)
        if df is None or df.empty:
            return ok_response(
                data={"latest": None, "note": "无质押数据"},
                source="tushare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        # 取最新
        r = df.head(1).iloc[0]
        return ok_response(
            data={
                "end_date": str(r.get("end_date", "")),
                "pledge_count": int(r.get("pledge_count") or 0),
                "unrest_pledge_yi": round(float(r.get("unrest_pledge") or 0) / 1e8, 2),
                "rest_pledge_yi": round(float(r.get("rest_pledge") or 0) / 1e8, 2),
                "total_share_yi": round(float(r.get("total_share") or 0) / 1e8, 2),
                "pledge_ratio_pct": round(float(r.get("pledge_ratio") or 0), 2),
                "note": "质押率>50%=高风险 / 30-50%=警惕 / <30%=正常",
            },
            source="tushare",
        )
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"tushare pledge_stat 调用失败: {str(e)[:200]}",
            source="tushare",
        )
