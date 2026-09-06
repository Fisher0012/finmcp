"""TOP15 第二档组2（batch-9 T29）: ETF 行情榜 + 机构调研统计。

两接口结构经生产实调确认(2026-09-06 深夜)。
"""

from datetime import datetime, timedelta
from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager

_cache = CacheManager()


def get_etf_ranking(keyword: str | None = None, top_n: int = 20) -> dict[str, Any]:
    """ETF 场内行情榜(东财, 1600+只): 按成交额降序, 可关键词过滤(如"半导体""科创")。

    典型场景: "有什么XX相关的ETF/资金在买什么ETF"。含最新价/涨跌幅/折价率。
    """
    try:
        cache_key = _cache.make_key("em", "etf_spot")
        table = _cache.get(cache_key)
        if table is None:
            import akshare as ak

            df = ak.fund_etf_spot_em()
            df = df.sort_values("成交额", ascending=False)
            table = df.head(600).to_dict("records")
            _cache.set(cache_key, table, ttl_category="realtime")
        rows = [r for r in table if not keyword or keyword in str(r.get("名称") or "")]
        if keyword and not rows:
            return ok_response(
                data={"items": [], "note": f"无名称含「{keyword}」的ETF(confirmed_absent)"}, source="eastmoney"
            )
        items = []
        for r in rows[:top_n]:
            items.append(
                {
                    "name": str(r.get("名称") or ""),
                    "price": float(r["最新价"]) if r.get("最新价") == r.get("最新价") else None,
                    "pct_chg": float(r["涨跌幅"]) if r.get("涨跌幅") == r.get("涨跌幅") else None,
                    "amount_yi": round(float(r["成交额"]) / 1e8, 2) if r.get("成交额") == r.get("成交额") else None,
                    "discount_pct": float(r["基金折价率"]) if r.get("基金折价率") == r.get("基金折价率") else None,
                }
            )
        data = {"items": items, "note": "东财 ETF 场内行情, 按成交额降序; 折价率为实时估值口径"}
        return ok_response(data=data, source="eastmoney")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"ETF 行情获取失败: {e}"[:120])


def get_institution_survey(stock_code: str | None = None, months_back: int = 1) -> dict[str, Any]:
    """机构调研统计(东财月度表): 全市场被调研排行或指定个股调研记录。

    典型场景: "机构最近在调研什么/XX有机构去调研吗"。接待机构数量=机构关注度信号。
    """
    try:
        code6 = "".join(c for c in (stock_code or "") if c.isdigit())[:6]
        d = (datetime.now() - timedelta(days=30 * months_back)).strftime("%Y%m01")
        cache_key = _cache.make_key("em", "jgdy", d)
        table = _cache.get(cache_key)
        if table is None:
            import akshare as ak

            df = ak.stock_jgdy_tj_em(date=d)
            df = df.sort_values("接待机构数量", ascending=False)
            table = df.head(800).to_dict("records")
            _cache.set(cache_key, table, ttl_category="daily")
        rows = [r for r in table if not code6 or str(r.get("代码")) == code6]
        if code6 and not rows:
            return ok_response(
                data={"items": [], "note": f"{code6} 近{months_back}月无机构调研记录(confirmed_absent)"},
                source="eastmoney",
            )
        items = []
        for r in rows[:20]:
            items.append(
                {
                    "name": str(r.get("名称") or ""),
                    "org_count": int(float(r.get("接待机构数量") or 0)),
                    "method": str(r.get("接待方式") or "")[:20],
                }
            )
        data = {
            "items": items,
            "note": f"东财机构调研统计(自 {d[:6]} 月起), 按接待机构数降序; 高调研度=机构关注信号(事实非建议)",
        }
        return ok_response(data=data, source="eastmoney")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"机构调研获取失败: {e}"[:120])
