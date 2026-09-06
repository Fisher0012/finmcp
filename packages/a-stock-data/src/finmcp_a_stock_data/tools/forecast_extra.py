"""公开源补遗 Top8 首批（batch-8 T27）: 东财盈利预测/期权QVIX/回购汇总。

三接口结构均经生产实调确认(2026-09-06); 全部免费(R20: 无付费源)。
"""

from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager

_cache = CacheManager()


def get_broker_profit_forecast(stock_code: str) -> dict[str, Any]:
    """东财机构盈利预测(个股): 研报数/近6月评级分布/2025-2028预测EPS。

    源=akshare stock_profit_forecast_em 全市场表(2891只)按代码过滤, 表级缓存1天。
    典型场景: "机构怎么看XX/盈利预测/评级"。与 get_consensus_forecast(tushare口径)互补。
    """
    try:
        code6 = (stock_code or "").strip()[:6]
        if not code6.isdigit():
            code6 = "".join(c for c in (stock_code or "") if c.isdigit())[:6]
        if len(code6) != 6:
            return error_response(code="INVALID_PARAM", message=f"无法解析股票代码: {stock_code}")
        cache_key = _cache.make_key("em", "profit_forecast_table")
        table = _cache.get(cache_key)
        if table is None:
            import akshare as ak

            df = ak.stock_profit_forecast_em()
            table = df.to_dict("records")
            _cache.set(cache_key, table, ttl_category="daily")
        row = next((r for r in table if str(r.get("代码")) == code6), None)
        if row is None:
            return ok_response(
                data={"note": f"{code6} 无机构盈利预测覆盖(confirmed_absent, 全表{len(table)}只)"}, source="eastmoney"
            )
        data = {
            "name": str(row.get("名称") or ""),
            "report_count": int(float(row.get("研报数") or 0)),
            "ratings": {
                k: int(float(row.get(f"机构投资评级(近六个月)-{k}") or 0))
                for k in ("买入", "增持", "中性", "减持", "卖出")
            },
            "eps_forecast": {
                y: round(float(row[f"{y}预测每股收益"]), 2)
                for y in ("2025", "2026", "2027", "2028")
                if row.get(f"{y}预测每股收益") == row.get(f"{y}预测每股收益")
            },
            "note": "东财机构盈利预测(近6月研报聚合); 与券商一致预期(tushare)口径可能有差异",
        }
        return ok_response(data=data, source="eastmoney")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"盈利预测获取失败: {e}"[:120])


def get_option_qvix(days: int = 30) -> dict[str, Any]:
    """50ETF 期权 QVIX 波动率指数(A股恐慌指数), 近 days 日序列。

    典型场景: 市场情绪/恐慌程度判断。QVIX 高=期权隐含波动率高=避险情绪重。
    """
    try:
        cache_key = _cache.make_key("ak", "qvix", str(days))
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source="akshare", cache_hit=True)
        import akshare as ak

        df = ak.index_option_50etf_qvix()
        if df is None or df.empty:
            return error_response(code="DATA_NOT_FOUND", message="QVIX 无数据")
        df = df.tail(days)
        items = [
            {"date": str(r["date"]), "close": float(r["close"])}
            for _, r in df.iterrows()
            if r.get("close") == r.get("close")
        ]
        cur, first = items[-1]["close"], items[0]["close"]
        data = {
            "items": items,
            "note": f"50ETF期权QVIX(恐慌指数): 当前{cur:.1f}, {days}日前{first:.1f}; "
            "上升=避险情绪升温; 历史中枢约15-20, >25=显著恐慌",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="akshare")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"QVIX 获取失败: {e}"[:120])


def get_repurchase(stock_code: str | None = None, limit: int = 20) -> dict[str, Any]:
    """股票回购计划/进度汇总(东财): 全市场最新或指定个股回购记录。

    典型场景: "XX回购了吗/最近哪些公司在回购"。回购=公司层面积极信号(事实非建议)。
    """
    try:
        code6 = "".join(c for c in (stock_code or "") if c.isdigit())[:6]
        cache_key = _cache.make_key("em", "repurchase_table")
        table = _cache.get(cache_key)
        if table is None:
            import akshare as ak

            df = ak.stock_repurchase_em()
            table = df.head(3000).to_dict("records")
            _cache.set(cache_key, table, ttl_category="daily")
        rows = [r for r in table if not code6 or str(r.get("股票代码")) == code6]
        if code6 and not rows:
            return ok_response(
                data={"items": [], "note": f"{code6} 近期无回购记录(confirmed_absent)"}, source="eastmoney"
            )
        items = []
        for r in rows[:limit]:
            items.append(
                {
                    "name": str(r.get("股票简称") or ""),
                    "plan_price_range": str(r.get("计划回购价格区间") or ""),
                    "progress": str(r.get("实施进度") or "") if "实施进度" in r else "",
                    "announce_date": str(r.get("最新公告日期") or r.get("公告日期") or ""),
                }
            )
        data = {"items": items, "note": "东财回购汇总(计划+进度); 回购为公司既成事实陈述"}
        return ok_response(data=data, source="eastmoney")
    except Exception as e:
        return error_response(code="UPSTREAM_ERROR", message=f"回购数据获取失败: {e}"[:120])
