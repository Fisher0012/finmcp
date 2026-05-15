"""list_industry_constituents tool"""

from typing import Any

from finmcp_common.errors import FinMCPError
from finmcp_common.responses import error_response, ok_response

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


def list_industry_constituents(
    industry_code: str | None = None,
    industry_name: str | None = None,
    level: int = 1,
) -> dict[str, Any]:
    """列出申万行业分类下的所有成份股。

    industry_code 和 industry_name 二选一（至少提供一个）。
    level=1/2/3 对应申万一级/二级/三级行业分类。

    典型场景：用户问"白酒板块有哪些股票"、"半导体行业龙头是谁"时调用。

    注意：行业分类基于申万标准，与证监会/中信分类可能不同。
    """
    if not industry_code and not industry_name:
        return error_response(
            code="INVALID_PARAM",
            message="industry_code 和 industry_name 至少提供一个",
            hint="请指定行业名称（如 '白酒'）或行业代码",
        )

    if level not in (1, 2, 3):
        return error_response(
            code="INVALID_PARAM",
            message=f"level 必须是 1、2 或 3，收到: {level}",
            hint="level=1 一级行业，level=2 二级行业，level=3 三级行业",
        )

    try:
        source = _get_source()
        cache_key = _cache.make_key(
            source.name, "industry",
            industry_code or "", industry_name or "", str(level),
        )
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source=source.name, cache_hit=True)

        results = source.get_industry_constituents(industry_code, industry_name, level)
        _cache.set(cache_key, results, ttl_category="basic_info")
        return ok_response(data=results, source=source.name)

    except FinMCPError as e:
        return handle_tool_error(e, source=_get_source().name if _source else "unknown")
    except Exception as e:
        return handle_tool_error(e)
