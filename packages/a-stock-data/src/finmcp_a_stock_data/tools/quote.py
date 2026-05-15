"""get_latest_quote tool"""

from typing import Any

from finmcp_common.errors import FinMCPError, InvalidParamError
from finmcp_common.responses import ok_response
from finmcp_common.stock_code import normalize_stock_code

from ..cache import CacheManager
from ..errors import handle_tool_error
from ..utils import get_data_source

_cache = CacheManager()
_source = None


def _get_source():  # noqa: ANN202
    global _source
    if _source is None:
        _source = get_data_source()
    return _source


def get_latest_quote(stock_code: str) -> dict[str, Any]:
    """获取 A 股个股的当前快照（盘中实时，收盘后为收盘数据）。

    返回字段：current_price, change, pct_change, open, high, low,
    prev_close, volume, amount, market_cap_yi, pe_ttm, pb。

    stock_code 支持 "600519"（自动识别）或 "600519.SH" 格式。

    典型场景：用户问"XX 现在多少钱"、"今天涨了多少"时调用。

    注意：缓存 TTL 60 秒，频繁调用同一代码会返回缓存值。
    """
    try:
        code = normalize_stock_code(stock_code)
    except ValueError as e:
        return handle_tool_error(InvalidParamError(str(e)))

    try:
        source = _get_source()
        cache_key = _cache.make_key(source.name, "quote", code)
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source=source.name, cache_hit=True)

        result = source.get_latest_quote(code)
        _cache.set(cache_key, result, ttl_category="realtime")
        return ok_response(data=result, source=source.name)

    except FinMCPError as e:
        return handle_tool_error(e, source=_get_source().name if _source else "unknown")
    except Exception as e:
        return handle_tool_error(e)
