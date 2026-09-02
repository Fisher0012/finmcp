"""get_stock_attention — 个股关注度排名（L2 热度事实, SPEC F5 / 姊妹规格 9.4 / R8 裁定）。

数据源: 东财股吧人气榜（emappdata.eastmoney.com/stockrank）。
定位: 只采集"关注度排名"类可验证事实指标, 不抓取、不传播讨论内容本身——
"XX 关注度升至全市场第 N"是合规且有信息量的陈述（异动-信息缺口形态的输入之一）。
"""

import json
import logging
import urllib.request
from typing import Any

from finmcp_common.errors import FinMCPError
from finmcp_common.responses import EMPTY_CONFIRMED_ABSENT, error_response, ok_response

from ..cache import CacheManager
from ..errors import handle_tool_error

logger = logging.getLogger(__name__)

_cache = CacheManager()
# 国内接口绕过进程代理
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _em_sc(stock_code: str) -> str:
    """600519.SH → SH600519（东财 srcSecurityCode 格式）"""
    code, _, suffix = stock_code.partition(".")
    if suffix not in ("SH", "SZ", "BJ") or not code.isdigit() or len(code) != 6:
        raise ValueError(f"股票代码格式非法: {stock_code!r}, 需如 600519.SH")
    return f"{suffix}{code}"


def _post(path: str, body: dict[str, Any]) -> Any:
    payload = {"appId": "appId01", "globalId": "finmcp", **body}
    req = urllib.request.Request(
        f"https://emappdata.eastmoney.com/stockrank/{path}",
        data=json.dumps(payload).encode(),
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
    )
    with _opener.open(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_stock_attention(stock_code: str, days: int = 10) -> dict[str, Any]:
    """获取个股在东财股吧人气榜的当前排名与近 N 日排名序列。

    仅返回排名类事实指标（不含讨论内容）。排名骤升但无公开催化时,
    是"无公开催化异动"形态的辅助证据（姊妹规格 9.4）。

    Args:
        stock_code: 股票代码（如 300750.SZ）
        days: 历史排名天数, 默认 10, 范围 1~30
    """
    try:
        sc = _em_sc((stock_code or "").strip())
    except ValueError as e:
        return error_response(code="INVALID_PARAM", message=str(e))
    days = max(1, min(int(days or 10), 30))

    cache_key = _cache.make_key("eastmoney", "attention", sc, str(days))
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="eastmoney_guba", cache_hit=True)

    try:
        cur = _post("getCurrentLatest", {"srcSecurityCode": sc})
        his = _post("getHisList", {"srcSecurityCode": sc, "days": days})
        cur_data = cur.get("data") if isinstance(cur, dict) and cur.get("code") == 0 else None
        his_data = his.get("data") if isinstance(his, dict) and his.get("code") == 0 else None
        if cur_data is None and not his_data:
            return error_response(
                code="UPSTREAM_ERROR",
                message="东财人气榜接口未返回有效数据",
                hint=f"current status={cur.get('code') if isinstance(cur, dict) else '?'}",
                source="eastmoney_guba",
            )
        data = {
            "stock_code": stock_code.strip(),
            "current": {
                "rank": (cur_data or {}).get("rank"),
                "market_all_count": (cur_data or {}).get("marketAllCount"),
                "calc_time": (cur_data or {}).get("calcTime"),
            }
            if cur_data
            else None,
            "history": [{"date": str(h.get("calcTime")), "rank": h.get("rank")} for h in (his_data or [])],
            "note": "东财股吧人气榜排名(值越小关注度越高); 仅排名事实, 不含讨论内容",
        }
        _cache.set(cache_key, data, ttl_category="realtime")
        has_data = bool(data["current"] or data["history"])
        return ok_response(
            data=data,
            source="eastmoney_guba",
            empty_reason=None if has_data else EMPTY_CONFIRMED_ABSENT,
        )
    except FinMCPError as e:
        return handle_tool_error(e, source="eastmoney_guba")
    except Exception as e:
        return handle_tool_error(e)
