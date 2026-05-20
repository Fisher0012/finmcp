"""list_concept_stocks tool — 按概念/题材搜索相关股票"""

import logging
from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager
from ..errors import handle_tool_error
from ..utils import get_data_source

logger = logging.getLogger(__name__)
_cache = CacheManager()
_source = None


def _get_source():  # noqa: ANN202
    global _source
    if _source is None:
        _source = get_data_source()
    return _source


def list_concept_stocks(concept_name: str, limit: int = 20) -> dict[str, Any]:
    """按概念/题材名称搜索相关 A 股股票。

    与 list_industry_constituents（申万行业分类）不同，本工具基于市场概念/题材板块，
    覆盖"存储芯片""AI芯片""固态电池"等热门投资概念。

    工作方式：
    1. 先在 tushare 概念板块中精确匹配，获取概念成份股
    2. 同时用关键词搜索补充（覆盖概念库未收录的相关股票）
    3. 去重合并，返回完整列表

    典型场景：用户问"存储芯片有哪些股票""AI芯片龙头"等概念性问题时调用。

    Args:
        concept_name: 概念名称（如"存储芯片""AI芯片""固态电池"）
        limit: 返回数量上限，默认 20，最大 50
    """
    if not concept_name or not concept_name.strip():
        return error_response(
            code="INVALID_PARAM",
            message="概念名称不能为空",
            hint="请提供概念名称，如'存储芯片'、'AI芯片'",
        )

    concept_name = concept_name.strip()
    limit = min(max(1, limit), 50)

    try:
        source = _get_source()

        # 检查缓存
        cache_key = _cache.make_key(source.name, "concept", concept_name, str(limit))
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source=source.name, cache_hit=True)

        seen_codes: set[str] = set()
        results: list[dict[str, Any]] = []

        # 1. tushare 概念板块匹配（仅 tushare 数据源支持）
        if source.name == "tushare":
            try:
                # 通过数据源实例的 _pro 访问 tushare API，不硬依赖 tushare
                pro = source._pro  # type: ignore[attr-defined]
                concept_df = pro.concept(src="ts")
                # 模糊匹配概念名
                matches = concept_df[concept_df["name"].str.contains(concept_name, na=False)]
                for _, row in matches.iterrows():
                    concept_id = row["code"]
                    detail_df = pro.concept_detail(id=concept_id)
                    if detail_df is not None and not detail_df.empty:
                        for _, stock in detail_df.iterrows():
                            code = stock.get("ts_code", "")
                            if code and code not in seen_codes:
                                seen_codes.add(code)
                                results.append({
                                    "stock_code": code,
                                    "name": stock.get("name", ""),
                                    "concept": row["name"],
                                })
            except Exception as e:
                # 概念接口失败不影响后续搜索补充，但记录日志
                logger.warning("tushare 概念板块查询失败: %s", e)

        # 2. 多关键词搜索补充
        # 拆分概念名为子关键词（如"存储芯片"→["存储芯片","存储","芯片"]）
        keywords = [concept_name]
        if len(concept_name) >= 4:
            mid = len(concept_name) // 2
            keywords.append(concept_name[:mid])
            keywords.append(concept_name[mid:])
        # 去掉太短或太通用的词
        keywords = [kw for kw in keywords if len(kw) >= 2]

        for kw in keywords:
            try:
                search_results = source.search_stocks(kw, limit=20)
                for s in search_results:
                    code = s.get("stock_code", "")
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        results.append({
                            "stock_code": code,
                            "name": s.get("name", ""),
                            "concept": f"搜索「{kw}」",
                        })
            except Exception as e:
                logger.warning("关键词搜索「%s」失败: %s", kw, e)
                continue

        results = results[:limit]
        _cache.set(cache_key, results, ttl_category="basic_info")
        return ok_response(data=results, source=source.name)

    except Exception as e:
        return handle_tool_error(e)
