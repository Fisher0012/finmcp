"""供给冲击与一致预期 tools: 限售解禁日历 / 券商盈利预测聚合（数据层 2.0 批次三）。

接口与字段 2026-09-04 带 token 实调确认:
share_float(ann_date,float_date,float_share,float_ratio,holder_name,share_type) /
report_rc(org_name,report_date,quarter,op_rt,np,eps,pe,rating,max_price,min_price —
单股半年 600+ 条, 必须聚合后输出)。
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


def _pro():
    import tushare as ts

    return ts.pro_api()


def get_share_unlock(stock_code: str, days_ahead: int = 180) -> dict[str, Any]:
    """个股未来限售解禁日历。大比例解禁=潜在供给冲击, 需提前关注。

    Args:
        stock_code: 股票代码（如 600519.SH）
        days_ahead: 向前看的自然日, 默认 180, 范围 30~365
    """
    code = (stock_code or "").strip()
    if not code:
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    days_ahead = max(30, min(int(days_ahead or 180), 365))
    cache_key = _cache.make_key("tushare", "unlock", code, str(days_ahead))
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="tushare", cache_hit=True)
    try:
        start = datetime.now().strftime("%Y%m%d")
        end = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y%m%d")
        df = _pro().share_float(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            return ok_response(
                data={
                    "stock_code": code,
                    "days_ahead": days_ahead,
                    "events": [],
                    "note": f"未来{days_ahead}天无解禁记录(确认无, 非查询失败)",
                },
                source="tushare",
            )
        events = [
            {
                "float_date": r["float_date"],
                "float_ratio_pct": r["float_ratio"],
                "float_share_wan": round(float(r["float_share"]), 1) if r["float_share"] else None,
                "holder": r["holder_name"],
                "share_type": r["share_type"],
            }
            for _, r in df.sort_values("float_date").iterrows()
        ]
        total_ratio = round(sum(e["float_ratio_pct"] or 0 for e in events), 2)
        data = {
            "stock_code": code,
            "days_ahead": days_ahead,
            "events": events[:15],
            "total_ratio_pct": total_ratio,
            "note": "float_ratio 为解禁股占总股本比例(%), float_share 单位万股(tushare 口径); 比例大且股东为财务投资者时冲击更大",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except FinMCPError as e:
        return handle_tool_error(e, source="tushare")
    except Exception as e:
        return handle_tool_error(e)


def get_consensus_forecast(stock_code: str, months: int = 6) -> dict[str, Any]:
    """券商一致预期: 近N月盈利预测按年度聚合(EPS 中位数/机构数)。预期差判断的基准线。

    Args:
        stock_code: 股票代码（如 600519.SH）
        months: 采纳近几个月的研报预测, 默认 6, 范围 3~12
    """
    code = (stock_code or "").strip()
    if not code:
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    months = max(3, min(int(months or 6), 12))
    cache_key = _cache.make_key("tushare", "consensus", code, str(months))
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="tushare", cache_hit=True)
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=months * 30)).strftime("%Y%m%d")
        df = _pro().report_rc(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            return error_response(
                code="DATA_NOT_FOUND",
                message=f"近{months}个月无券商对 {code} 的盈利预测记录",
                source="tushare",
            )
        # 同机构同季度取最新一条, 再按预测年度聚合
        df = df.sort_values("report_date").drop_duplicates(
            subset=["org_name", "quarter"], keep="last"
        )
        df["year"] = df["quarter"].astype(str).str[:4]
        by_year = []
        for year, g in df.groupby("year"):
            eps = g["eps"].dropna()
            np_wan = g["np"].dropna()
            if eps.empty and np_wan.empty:
                continue
            by_year.append(
                {
                    "year": year,
                    "eps_median": round(float(eps.median()), 2) if not eps.empty else None,
                    "eps_range": [round(float(eps.min()), 2), round(float(eps.max()), 2)]
                    if not eps.empty
                    else None,
                    "np_median_yi": round(float(np_wan.median()) / 1e4, 1)
                    if not np_wan.empty
                    else None,
                    "org_count": int(g["org_name"].nunique()),
                }
            )
        ratings = df.dropna(subset=["rating"])["rating"].value_counts().to_dict()
        data = {
            "stock_code": code,
            "window_months": months,
            "report_count": len(df),
            "org_count": int(df["org_name"].nunique()),
            "forecast_by_year": by_year[:4],
            "rating_distribution": {k: int(v) for k, v in ratings.items()},
            "note": "eps 单位元/股, np_median 已换算为亿元(tushare np 原始口径万元); "
            "同机构同季度已去重取最新; 实际业绩显著低于 eps_median=低于预期, 显著高于=超预期",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="tushare")
    except FinMCPError as e:
        return handle_tool_error(e, source="tushare")
    except Exception as e:
        return handle_tool_error(e)
