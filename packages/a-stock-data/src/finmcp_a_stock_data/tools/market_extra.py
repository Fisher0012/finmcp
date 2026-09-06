"""公开源补遗 Top8 余项（batch-9 T31）: 财经日历/雪球热度。

两接口结构经生产实调确认(2026-09-06 深夜)。
明确不可得(实测确认, 不上线): 新增投资者(东财整理表停更于 2023-08, 中登官方亦停更——
陈旧数据进材料时效风险>价值); 处罚问询函/WSTS 无现成 akshare 接口, 自建抓取转下轮评估。
"""

from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager

_cache = CacheManager()


def get_econ_calendar(days: int = 7) -> dict[str, Any]:
    """财经日历(百度, 近期宏观事件): 日期/时间/地区/事件/公布值/预期值。

    典型场景: "本周有什么重要数据/FOMC什么时候"。含中外宏观事件(CPI/议息/PMI等)。
    """
    try:
        cache_key = _cache.make_key("baidu", "econ_calendar")
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source="baidu", cache_hit=True)
        import akshare as ak

        df = ak.news_economic_baidu()
        if df is None or df.empty:
            return error_response(code="DATA_NOT_FOUND", message="财经日历无数据")
        items = []
        for _, r in df.head(60).iterrows():
            items.append(
                {
                    "date": str(r.get("日期") or ""),
                    "time": str(r.get("时间") or ""),
                    "region": str(r.get("地区") or ""),
                    "event": str(r.get("事件") or "")[:60],
                    "actual": str(r.get("公布") or ""),
                    "expect": str(r.get("预期") or ""),
                }
            )
        data = {"items": items, "note": "百度财经日历; 公布值为空=尚未公布(未来事件)"}
        _cache.set(cache_key, data, ttl_category="realtime")
        return ok_response(data=data, source="baidu")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"财经日历获取失败: {e}"[:120])


def get_xueqiu_hot(stock_code: str | None = None, top_n: int = 20) -> dict[str, Any]:
    """雪球关注热度: 全市场关注人数排行或指定个股关注数(5636只全表)。

    典型场景: 情绪面/散户关注度("XX热度高吗")。与 get_stock_attention(东财)互补口径。
    """
    try:
        code6 = "".join(c for c in (stock_code or "") if c.isdigit())[:6]
        cache_key = _cache.make_key("xq", "hot_follow_table")
        table = _cache.get(cache_key)
        if table is None:
            import akshare as ak

            df = ak.stock_hot_follow_xq(symbol="最热门")
            table = df.to_dict("records")
            _cache.set(cache_key, table, ttl_category="daily")
        if code6:
            row = next((r for r in table if code6 in str(r.get("股票代码"))), None)
            if row is None:
                return ok_response(
                    data={"note": f"{code6} 不在雪球热度表(confirmed_absent, 全表{len(table)}只)"}, source="xueqiu"
                )
            rank = next((i + 1 for i, r in enumerate(table) if code6 in str(r.get("股票代码"))), None)
            data = {
                "name": str(row.get("股票简称") or ""),
                "followers": int(float(row.get("关注") or 0)),
                "rank": rank,
                "note": f"雪球关注人数, 全市场排名第{rank}/{len(table)}",
            }
            return ok_response(data=data, source="xueqiu")
        items = [
            {"name": str(r.get("股票简称") or ""), "followers": int(float(r.get("关注") or 0))} for r in table[:top_n]
        ]
        return ok_response(data={"items": items, "note": "雪球关注人数排行(前N)"}, source="xueqiu")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"雪球热度获取失败: {e}"[:120])
