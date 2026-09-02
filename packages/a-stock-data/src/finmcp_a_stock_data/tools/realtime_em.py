"""东财盘中实时 tools: get_money_flow + get_market_snapshot + get_sector_ranking

自 workbench stockbot/tools_rt.py + routers/finmcp.py 组合壳下沉（SPEC F3 §3.3）。
下沉后解除小程序对 stockbot 的跨层依赖。

- 全部走东财公开行情接口, 直连不走代理; push2 被风控时用 push2delay 兜底。
- 金额统一转亿元(保留3位), 百分比保持原始百分数值。
- get_money_flow: 东财实时(当日盘中+历史序列)优先, 失败回退 tushare EOD,
  两级尝试逐一记入 meta.attempts（SPEC F1）。
"""

import json
import time
import urllib.request as _u
from typing import Any
from urllib.error import URLError

from finmcp_common.responses import (
    EMPTY_CONFIRMED_ABSENT,
    error_response,
    ok_response,
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}
# push2(实时)与 push2his(历史/分时)均有 push2delay 等价兜底(延迟约1-2分钟, 可接受)
_HOST_FALLBACK = {
    "push2.eastmoney.com": ["push2.eastmoney.com", "push2delay.eastmoney.com"],
    "push2his.eastmoney.com": ["push2his.eastmoney.com", "push2delay.eastmoney.com"],
}
_opener = _u.build_opener(_u.ProxyHandler({}))  # 强制直连, 忽略系统代理

_INDEX_SECIDS = "1.000001,0.399001,0.399006,1.000300,0.399106"
_INDEX_NAMES = {
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
    "000300": "沪深300",
    "399106": "深证综指",
}


def _get_json(url: str, tries_per_host: int = 2) -> dict[str, Any]:
    host = url.split("/")[2]
    last: Exception | None = None
    last_empty: dict[str, Any] | None = None  # 风控偶发返回 data=null, 视为失败重试; 全部为空时兜底返回最后一次
    for h in _HOST_FALLBACK.get(host, [host]):
        u2 = url.replace(host, h, 1)
        for _ in range(tries_per_host):
            try:
                raw = _opener.open(_u.Request(u2, headers=_HEADERS), timeout=12).read()
                j: dict[str, Any] = json.loads(raw.decode("utf-8", "replace"))
                if j.get("data"):
                    return j
                last_empty = j
            except (URLError, OSError, json.JSONDecodeError, Exception) as e:  # noqa: B014
                last = e
            time.sleep(0.6)
    if last_empty is not None:
        return last_empty
    raise RuntimeError(f"东财接口不可达: {url.split('?')[0]} ({last})")


def _secid(stock_code: str) -> str:
    """601958 / 601958.SH / 000001.SZ → 东财 secid (沪=1. 深京=0.)"""
    code = stock_code.split(".")[0].strip()
    if not (len(code) == 6 and code.isdigit()):
        raise ValueError(f"无效股票代码: {stock_code}")
    market = "1" if code[0] in ("5", "6", "9") else "0"
    return f"{market}.{code}"


def _yi(v: Any) -> float | None:
    """元 → 亿元"""
    if not isinstance(v, (int, float)):
        return None
    return round(v / 1e8, 3)


def _num(v: Any) -> Any:
    return v if isinstance(v, (int, float)) else None


# ── 1. 个股主力资金流（东财实时优先, tushare EOD 回退） ─────────────


def _history_series_em(sid: str, days: int) -> list[dict[str, Any]]:
    """东财 fflow daykline 历史序列 (fields2 顺序: 日期,主力,小单,中单,大单,超大单,
    主力%,小单%,中单%,大单%,超大单%,收盘,涨跌幅,...)。被风控时返回空列表
    （空列表由调用方回退 tushare, 非最终对外结果, 不构成静默降级）。"""
    try:
        j = _get_json(
            "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
            f"?lmt={days}&klt=101&secid={sid}"
            "&fields1=f1,f2,f3,f7"
            "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
        )
    except Exception:
        return []
    today_date = time.strftime("%Y-%m-%d")
    series = []
    for row in (j.get("data") or {}).get("klines") or []:
        p = row.split(",")
        if len(p) < 13:
            continue
        series.append(
            {
                "date": p[0],
                "main_net_yi": _yi(float(p[1])),
                "main_net_pct": round(float(p[6]), 2),
                "xlarge_net_yi": _yi(float(p[5])),
                "xlarge_net_pct": round(float(p[10]), 2),
                "large_net_yi": _yi(float(p[4])),
                "close": float(p[11]),
                "pct_change": float(p[12]),
                "intraday": p[0] == today_date,
            }
        )
    return series


def _history_series_tushare(stock_code: str, days: int) -> list[dict[str, Any]]:
    """tushare moneyflow 兜底 (EOD, 万元)。主力=大单+超大单买卖净额, 无占比字段。
    失败返回空列表（作为东财序列的补充源, 调用方仍有当日实时值, 不构成静默降级）。"""
    try:
        import tushare as ts

        code = stock_code.split(".")[0]
        ts_code = f"{code}.{'SH' if code[0] in ('5', '6', '9') else 'SZ'}"
        df = ts.pro_api().moneyflow(ts_code=ts_code, limit=days)
        if df is None or df.empty:
            return []
        series = []
        for _, r in df.iterrows():
            lg = float(r.get("buy_lg_amount") or 0) - float(r.get("sell_lg_amount") or 0)
            elg = float(r.get("buy_elg_amount") or 0) - float(r.get("sell_elg_amount") or 0)
            d = str(r.get("trade_date", ""))
            series.append(
                {
                    "date": f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d,
                    "main_net_yi": round((lg + elg) / 10000, 3),
                    "main_net_pct": None,
                    "xlarge_net_yi": round(elg / 10000, 3),
                    "xlarge_net_pct": None,
                    "large_net_yi": round(lg / 10000, 3),
                    "close": None,
                    "pct_change": None,
                    "intraday": False,
                }
            )
        series.reverse()  # tushare 按日期倒序返回, 转为时间正序
        return series
    except Exception:
        return []


def _realtime_moneyflow_em(stock_code: str, days: int) -> tuple[dict[str, Any], str]:
    """东财实时资金流主路径 → (data, source)。失败抛异常, 由 get_money_flow 记 attempts。"""
    sid = _secid(stock_code)
    # 当日盘中实时
    j = _get_json(
        "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2"
        f"&secids={sid}"
        "&fields=f2,f3,f9,f12,f14,f18,f23,f62,f66,f69,f72,f75,f78,f81,f84,f87,f100,f114,f115,f124,f184"
    )
    diff = (j.get("data") or {}).get("diff") or []
    if not diff:
        raise RuntimeError(f"未查到 {stock_code} 的实时资金流")
    d = diff[0]
    today = {
        "name": d.get("f14"),
        "price": _num(d.get("f2")),
        "pct_change": _num(d.get("f3")),
        "prev_close": _num(d.get("f18")),
        "main_net_yi": _yi(d.get("f62")),  # 主力净流入(亿)
        "main_net_pct": _num(d.get("f184")),  # 主力净占比%
        "xlarge_net_yi": _yi(d.get("f66")),  # 超大单净流入(亿)
        "xlarge_net_pct": _num(d.get("f69")),  # 超大单净占比%
        "large_net_yi": _yi(d.get("f72")),
        "large_net_pct": _num(d.get("f75")),
        "medium_net_yi": _yi(d.get("f78")),
        "medium_net_pct": _num(d.get("f81")),
        "small_net_yi": _yi(d.get("f84")),
        "small_net_pct": _num(d.get("f87")),
        # 三口径市盈率(东财实时): 动态=当年业绩年化, TTM=滚动四季, 静态=上年年报
        "pe_dynamic": _num(d.get("f9")),
        "pe_ttm": _num(d.get("f115")),
        "pe_static": _num(d.get("f114")),
        "pb": _num(d.get("f23")),
        "industry_board": d.get("f100"),  # 所属行业板块(与大盘档位的风口板块对照)
        "quote_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d["f124"]))
        if isinstance(d.get("f124"), (int, float))
        else None,
    }
    # 历史日度序列: 东财 daykline 优先(含占比), 被风控/为空时降级 tushare EOD
    series = _history_series_em(sid, days)
    source = "eastmoney_realtime"
    # 盘中东财 daykline 常只返回当日 1 条(2026-08-12 实测), 会丢失近 N 日趋势;
    # 序列过短(<3)即回退 tushare EOD 拿完整历史, 当日实时值仍由下方 append 补上
    if len(series) < 3:
        series = _history_series_tushare(stock_code, days)
        source = "eastmoney_realtime(当日) + tushare_eod(历史)"
    today_date = time.strftime("%Y-%m-%d")
    # daykline 未含当日时, 用实时值补当日行
    if today["main_net_yi"] is not None and (not series or series[-1]["date"] != today_date):
        series.append(
            {
                "date": today_date,
                "main_net_yi": today["main_net_yi"],
                "main_net_pct": today["main_net_pct"],
                "xlarge_net_yi": today["xlarge_net_yi"],
                "xlarge_net_pct": today["xlarge_net_pct"],
                "large_net_yi": today["large_net_yi"],
                "close": today["price"],
                "pct_change": today["pct_change"],
                "intraday": True,
            }
        )
    series = series[-days:]
    # 派生: 连续净流入/流出天数(含当日)
    streak = 0
    for s in reversed(series):
        v = s["main_net_yi"] or 0
        if streak == 0:
            streak = 1 if v > 0 else -1 if v < 0 else 0
        elif (streak > 0 and v > 0) or (streak < 0 and v < 0):
            streak += 1 if streak > 0 else -1
        else:
            break
    data = {
        "stock_code": stock_code,
        "today_realtime": today,
        "daily_series": series,
        "main_inflow_streak_days": streak,  # 正=连续吸筹天数, 负=连续流出天数
        "note": "金额单位亿元; intraday=true 表示当日盘中值仍在变动",
    }
    return data, source


def get_money_flow(stock_code: str, days: int = 10) -> dict[str, Any]:
    """主力资金流: 东财实时(当日盘中+历史序列+连续吸筹/流出天数)优先, 风控/异常回退 tushare EOD。

    盘中问资金流必须是当天实时的, 纯 tushare 版盘中只有昨天数据（2026-08-12 结论）。
    两级数据源尝试结果见 meta.attempts。

    Args:
        stock_code: 股票代码（如 600519.SH）
        days: 历史序列天数, 默认 10
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    attempts: list[dict[str, Any]] = []
    # 一级: 东财实时
    try:
        data, source = _realtime_moneyflow_em(stock_code, days)
        if data.get("today_realtime"):
            attempts.append({"source": "eastmoney_realtime", "outcome": "ok"})
            return ok_response(data=data, source=source, attempts=attempts)
        attempts.append({"source": "eastmoney_realtime", "outcome": "empty"})
    except ValueError as e:
        return error_response(code="INVALID_PARAM", message=str(e))
    except Exception as e:
        attempts.append({"source": "eastmoney_realtime", "outcome": "error", "detail": str(e)[:200]})

    # 二级: tushare moneyflow EOD 回退
    try:
        import tushare as ts

        pro = ts.pro_api()
        df = pro.moneyflow(ts_code=stock_code, limit=days)
        if df is None or df.empty:
            attempts.append({"source": "tushare_moneyflow", "outcome": "empty"})
            return ok_response(
                data={"flows": [], "note": "无资金流数据"},
                source="tushare",
                attempts=attempts,
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        rows = []
        total_main_net = 0.0
        for _, r in df.head(days).iterrows():
            # 主力 = 大单 + 超大单
            elg = float(r.get("net_mf_amount") or 0)  # 单位:万元
            rows.append(
                {
                    "trade_date": str(r.get("trade_date", "")),
                    "net_main_flow_yi": round(elg / 10000, 3),  # 万元→亿元
                    "buy_lg_amount_yi": round(float(r.get("buy_lg_amount") or 0) / 10000, 2),
                    "sell_lg_amount_yi": round(float(r.get("sell_lg_amount") or 0) / 10000, 2),
                    "buy_elg_amount_yi": round(float(r.get("buy_elg_amount") or 0) / 10000, 2),
                    "sell_elg_amount_yi": round(float(r.get("sell_elg_amount") or 0) / 10000, 2),
                }
            )
            total_main_net += elg / 10000
        attempts.append({"source": "tushare_moneyflow", "outcome": "ok"})
        return ok_response(
            data={
                "flows_recent": rows,
                "total_main_net_yi_recent": round(total_main_net, 2),
                "note": f"近{days}日累计主力净流入(亿元): {round(total_main_net, 2)}, 正=机构在进/负=机构在撤",
            },
            source="tushare",
            attempts=attempts,
        )
    except Exception as e:
        attempts.append({"source": "tushare_moneyflow", "outcome": "error", "detail": str(e)[:200]})
        return error_response(
            code="UPSTREAM_ERROR",
            message="资金流两级数据源(东财实时/tushare EOD)全部失败",
            hint="稍后重试；逐级失败详情见 meta.attempts",
            source="eastmoney+tushare",
            attempts=attempts,
        )


# ── 2. 大盘实时快照 ───────────────────────────────────────────


def get_market_snapshot() -> dict[str, Any]:
    """大盘实时快照: 四大指数涨跌 + 全市场涨跌家数(市场宽度) + 两市成交额。

    涨跌家数=上证(沪市)+深证综指(深市); 成交额同口径。
    补 get_index_price 没有的实时涨跌家数（2026-08-12 接入东财实时层）。
    """
    try:
        j = _get_json(
            "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2"
            f"&secids={_INDEX_SECIDS}&fields=f2,f3,f6,f12,f14,f104,f105,f106,f124"
        )
        diff = (j.get("data") or {}).get("diff") or []
        if not diff:
            return error_response(
                code="UPSTREAM_ERROR",
                message="未获取到指数行情",
                source="eastmoney",
            )
        idx = {}
        for d in diff:
            code = str(d.get("f12"))
            idx[code] = {
                "name": _INDEX_NAMES.get(code, d.get("f14")),
                "point": _num(d.get("f2")),
                "pct_change": _num(d.get("f3")),
                "amount_yi": _yi(d.get("f6")),
                "up_count": _num(d.get("f104")),
                "down_count": _num(d.get("f105")),
                "flat_count": _num(d.get("f106")),
            }
        sh, szz = idx.get("000001", {}), idx.get("399106", {})
        up = (sh.get("up_count") or 0) + (szz.get("up_count") or 0)
        down = (sh.get("down_count") or 0) + (szz.get("down_count") or 0)
        flat = (sh.get("flat_count") or 0) + (szz.get("flat_count") or 0)
        amount = round((sh.get("amount_yi") or 0) + (szz.get("amount_yi") or 0), 1)
        ts_val = next((d.get("f124") for d in diff if isinstance(d.get("f124"), (int, float))), None)
        return ok_response(
            data={
                "indices": [idx[c] for c in ("000001", "399001", "399006", "000300") if c in idx],
                "market_breadth": {"up": up, "down": down, "flat": flat},
                "total_amount_yi": amount,  # 两市成交额(亿)
                "quote_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_val)) if ts_val else None,
            },
            source="eastmoney_realtime",
        )
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"大盘快照获取失败: {str(e)[:200]}",
            source="eastmoney",
        )


# ── 3. 板块资金排行 ───────────────────────────────────────────


def _fetch_boards(board_type: str) -> list[dict[str, Any]]:
    t = {"industry": "2", "concept": "3"}[board_type]
    j = _get_json(
        "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1"
        f"&fltt=2&invt=2&fid=f62&fs=m:90+t:{t}&fields=f3,f12,f14,f62,f184"
    )
    rows = []
    for d in (j.get("data") or {}).get("diff") or []:
        # 盘前竞价时段 f62(主力净额)全为"-", 保留行(资金字段置 None), 名字解析
        # 不依赖资金数据; 榜单排序侧自行过滤 None（2026-08-20 医药事故修法）。
        if not d.get("f14"):
            continue
        rows.append(
            {
                "board": d.get("f14"),
                "bk": str(d.get("f12", "")),  # 板块 BK 代码
                "pct_change": _num(d.get("f3")),
                "main_net_yi": _yi(d.get("f62")) if isinstance(d.get("f62"), (int, float)) else None,
                "main_net_pct": _num(d.get("f184")),
            }
        )
    return rows


def get_sector_ranking(top_n: int = 10, board_type: str = "industry", board_names: str = "") -> dict[str, Any]:
    """当日板块主力资金排行(流入榜+流出榜)。

    board_type: industry(行业)/concept(概念)。
    board_names: 逗号分隔的板块名点查(如 "银行,电力,贵金属"), 跨行业+概念模糊匹配,
    返回这些板块的当日涨跌+资金——用于避险/防御类问题核对具体板块表现。

    Args:
        top_n: 榜单条数, 默认 10, 最大 30
        board_type: industry / concept
        board_names: 逗号分隔的板块名点查, 空 = 返回排行榜
    """
    if board_type not in ("industry", "concept"):
        return error_response(
            code="INVALID_PARAM",
            message="board_type 仅支持 industry / concept",
        )
    top_n = max(1, min(int(top_n), 30))
    try:
        if board_names:
            queries = [q.strip() for q in str(board_names).replace("，", ",").split(",") if q.strip()]
            all_rows = _fetch_boards("industry") + _fetch_boards("concept")
            matched: list[dict[str, Any]] = []
            seen: set[str] = set()
            for q in queries:
                hits = [r for r in all_rows if q in (r["board"] or "")]
                if not hits:
                    matched.append({"board": q, "note": "未找到同名板块"})
                    continue
                for r in sorted(hits, key=lambda x: abs(x["main_net_yi"] or 0), reverse=True)[:3]:
                    if r["board"] not in seen:
                        seen.add(r["board"])
                        matched.append(r)
            return ok_response(
                data={
                    "queried": queries,
                    "boards": matched,
                    "note": "金额单位亿元, 当日盘中实时",
                },
                source="eastmoney_realtime",
            )
        rows = _fetch_boards(board_type)
        # 资金榜只用有资金数据的行(盘前竞价时段 f62 全空 → funded 为空, 如实报错,
        # 由产品层给"盘前资金流未生成"的诚实文案, 不混入 None 排序)
        funded = [r for r in rows if r.get("main_net_yi") is not None]
        if not funded:
            if rows:
                return error_response(
                    code="DATA_NOT_FOUND",
                    message="板块资金数据尚未生成(盘前竞价时段主力资金流从 9:30 开盘后才开始累计)",
                    source="eastmoney",
                )
            return error_response(
                code="UPSTREAM_ERROR",
                message="未获取到板块资金数据",
                source="eastmoney",
            )
        funded.sort(key=lambda r: r["main_net_yi"], reverse=True)
        return ok_response(
            data={
                "board_type": board_type,
                "top_inflow": funded[:top_n],
                "top_outflow": funded[-top_n:][::-1],
                "note": "金额单位亿元, 当日盘中实时",
            },
            source="eastmoney_realtime",
        )
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"板块资金排行获取失败: {str(e)[:200]}",
            source="eastmoney",
        )
