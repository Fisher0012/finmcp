"""get_event_market_alignment — 事件-市场反应对齐（SPEC F5 / 姊妹规格 9.3 数据基础）。

给定事件日 D 与对象, 计算:
- D 前 window 个交易日对象相对基准的累计超额表现
- D 日（非交易日顺延并标注）与 D 后 1~3 交易日的反应
- 同主题新闻时间线（可选, 依赖 fin-news 包与 FIN_NEWS_DB）

纯事实计算, **不做形态判定**（预期先行/兑现回落等分类归产品判断层, 见姊妹规格 9.3）。
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from finmcp_common.errors import FinMCPError
from finmcp_common.responses import error_response, ok_response

from ..errors import handle_tool_error

logger = logging.getLogger(__name__)

_NEWS_COVERAGE_NOTE = "新闻库覆盖自 2026-05-31 起(约 3 个月存量), 更早时段时间线不完整"


def _norm_date(s: str) -> str:
    """YYYY-MM-DD / YYYYMMDD → YYYYMMDD, 非法抛 ValueError"""
    s = (s or "").strip().replace("-", "")
    datetime.strptime(s, "%Y%m%d")
    return s


def _fetch_daily(code: str, is_index: bool, start: str, end: str) -> list[dict[str, Any]]:
    """拉日线收盘序列(升序)。个股 pro_bar(前复权), 指数 index_daily(含申万 .SI)。"""
    import tushare as ts

    if is_index:
        pro = ts.pro_api()
        df = pro.index_daily(ts_code=code, start_date=start, end_date=end)
    else:
        df = ts.pro_bar(ts_code=code, start_date=start, end_date=end, adj="qfq")
    if df is None or df.empty:
        return []
    rows = [
        {
            "trade_date": str(r["trade_date"]),
            "close": float(r["close"]),
            "pct_chg": float(r["pct_chg"]) if r.get("pct_chg") == r.get("pct_chg") else None,
        }
        for _, r in df.iterrows()
    ]
    rows.sort(key=lambda x: str(x["trade_date"]))
    return rows


def _cum_pct(rows: list[dict[str, Any]]) -> float | None:
    """区间累计涨幅%（首日前收为基准: 用首日 close/(1+首日 pct) 反推）。"""
    if not rows:
        return None
    first = rows[0]
    first_pct = first.get("pct_chg")
    if first_pct is None or not isinstance(first_pct, (int, float)):
        return None
    base = float(first["close"]) / (1 + float(first_pct) / 100)
    if not base:
        return None
    return round((float(rows[-1]["close"]) / base - 1) * 100, 2)


def _news_timeline(theme_query: str, start_yyyymmdd: str) -> dict[str, Any] | None:
    """同主题新闻按天聚合时间线（软依赖 fin-news, 不可用返回 None 并由调用方标注）。"""
    try:
        from fin_news import search_news
    except Exception:
        return None
    days_back = max(1, (datetime.now() - datetime.strptime(start_yyyymmdd, "%Y%m%d")).days + 1)
    resp = search_news(theme_query, days=min(days_back, 365), limit=200)
    if not resp.get("ok"):
        return {"available": False, "reason": "新闻库查询失败"}
    by_day: dict[str, dict[str, Any]] = {}
    for it in resp["data"]["items"]:
        day = datetime.fromtimestamp(it["fetched_at"]).strftime("%Y-%m-%d")
        bucket = by_day.setdefault(day, {"date": day, "count": 0, "first_title": it["title"]})
        bucket["count"] += 1
    timeline = sorted(by_day.values(), key=lambda x: x["date"])
    return {
        "available": True,
        "query": theme_query,
        "daily": timeline,
        "total": len(resp["data"]["items"]),
        "coverage_note": _NEWS_COVERAGE_NOTE,
        "staleness_warning": resp["meta"].get("staleness_warning"),
    }


def get_event_market_alignment(
    event_date: str,
    target: str,
    window: int = 20,
    target_type: str = "stock",
    benchmark: str = "000300.SH",
    theme_query: str = "",
) -> dict[str, Any]:
    """事件日前后对象相对基准的表现对齐（纯事实, 供预期-兑现形态分类的输入）。

    Args:
        event_date: 事件日 YYYY-MM-DD 或 YYYYMMDD（非交易日自动顺延到下一交易日并标注）
        target: 对象代码（个股如 600519.SH; 指数/申万行业指数如 801080.SI 需 target_type="index"）
        window: 事件前观察窗口的交易日数, 默认 20, 范围 5~60
        target_type: "stock" | "index"（代码无法自判个股/指数, 显式指定）
        benchmark: 基准指数, 默认沪深300
        theme_query: 可选, 同主题新闻时间线关键词（依赖 fin-news 新闻库）

    Returns data:
        pre_window:  {trading_days, target_cum_pct, benchmark_cum_pct, excess_pct}
        event_day:   {date, adjusted(顺延标注), target_pct, benchmark_pct}
        post_window: {trading_days, target_cum_pct, benchmark_cum_pct, excess_pct, partial}
        news_timeline: 见 _news_timeline（不可用时为 null + note）
    """
    try:
        d0 = _norm_date(event_date)
    except ValueError:
        return error_response(
            code="INVALID_PARAM",
            message=f"event_date 格式非法: {event_date!r}, 需 YYYY-MM-DD 或 YYYYMMDD",
        )
    if target_type not in ("stock", "index"):
        return error_response(code="INVALID_PARAM", message='target_type 仅支持 "stock"/"index"')
    if not target or not target.strip():
        return error_response(code="INVALID_PARAM", message="target 不能为空")
    target = target.strip()
    window = max(5, min(int(window or 20), 60))

    try:
        # 拉足够宽的自然日窗口: 前 window*2+30 天缓冲(节假日), 后 10 天
        d0_dt = datetime.strptime(d0, "%Y%m%d")
        start = (d0_dt - timedelta(days=window * 2 + 30)).strftime("%Y%m%d")
        end = (d0_dt + timedelta(days=10)).strftime("%Y%m%d")

        tgt = _fetch_daily(target, target_type == "index", start, end)
        bench = _fetch_daily(benchmark, True, start, end)
        if not tgt:
            return error_response(
                code="DATA_NOT_FOUND",
                message=f"未取到 {target} 在 {start}~{end} 的行情",
                hint="检查代码与 target_type; 申万行业指数(.SI)需 target_type=index",
            )
        if not bench:
            return error_response(code="UPSTREAM_ERROR", message=f"基准 {benchmark} 行情未取到")

        tgt_dates = [r["trade_date"] for r in tgt]
        # 事件日对齐: D 当日或其后的第一个交易日
        event_td = next((d for d in tgt_dates if d >= d0), None)
        if event_td is None:
            return error_response(
                code="DATA_NOT_FOUND",
                message=f"事件日 {d0} 之后无交易数据(事件太近或对象停牌)",
            )
        idx = tgt_dates.index(event_td)
        if idx < window:
            return error_response(
                code="DATA_NOT_FOUND",
                message=f"事件日前交易数据不足 {window} 日(仅 {idx} 日), 无法构成观察窗口",
                hint="缩小 window 或确认对象上市时间",
            )

        bench_by_date = {r["trade_date"]: r for r in bench}

        def _pair_cum(rows: list[dict[str, Any]]) -> tuple[float | None, float | None]:
            t_cum = _cum_pct(rows)
            b_rows = [bench_by_date[r["trade_date"]] for r in rows if r["trade_date"] in bench_by_date]
            b_cum = _cum_pct(b_rows)
            return t_cum, b_cum

        pre_rows = tgt[idx - window : idx]
        pre_t, pre_b = _pair_cum(pre_rows)
        event_row = tgt[idx]
        event_b = bench_by_date.get(event_td, {})
        post_rows = tgt[idx + 1 : idx + 4]
        post_t, post_b = _pair_cum(post_rows) if post_rows else (None, None)

        def _excess(t: float | None, b: float | None) -> float | None:
            return round(t - b, 2) if t is not None and b is not None else None

        data: dict[str, Any] = {
            "target": target,
            "target_type": target_type,
            "benchmark": benchmark,
            "requested_event_date": d0,
            "pre_window": {
                "trading_days": window,
                "target_cum_pct": pre_t,
                "benchmark_cum_pct": pre_b,
                "excess_pct": _excess(pre_t, pre_b),
            },
            "event_day": {
                "date": event_td,
                "adjusted": event_td != d0,
                "target_pct": event_row.get("pct_chg"),
                "benchmark_pct": event_b.get("pct_chg"),
            },
            "post_window": {
                "trading_days": len(post_rows),
                "target_cum_pct": post_t,
                "benchmark_cum_pct": post_b,
                "excess_pct": _excess(post_t, post_b),
                "partial": len(post_rows) < 3,
            },
            "news_timeline": None,
            "note": "纯事实对齐数据; 形态判定(预期先行/兑现回落等)由产品判断层完成",
        }
        if theme_query.strip():
            tl = _news_timeline(theme_query.strip(), tgt_dates[idx - window])
            data["news_timeline"] = tl
            if tl is None:
                data["note"] += "; 新闻时间线不可用(fin-news 未安装或 FIN_NEWS_DB 未配置)"
        return ok_response(data=data, source="tushare", as_of=event_td)
    except FinMCPError as e:
        return handle_tool_error(e, source="tushare")
    except Exception as e:
        return handle_tool_error(e)
