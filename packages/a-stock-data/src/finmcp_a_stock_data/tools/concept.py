"""list_concept_stocks tool — 按概念/题材搜索相关股票

数据源：同花顺概念板块（360+ 概念，覆盖算力租赁、AI、机器人等热门板块）
同花顺网页版可从腾讯云直连，无需代理。
"""

import logging
import re
import ssl
import urllib.request
from typing import Any

from finmcp_common.responses import (
    EMPTY_CONFIRMED_ABSENT,
    EMPTY_UNKNOWN,
    error_response,
    ok_response,
    strict_contract,
)

from ..cache import CacheManager
from ..data_sources.base import StockDataSource
from ..errors import handle_tool_error
from ..utils import get_data_source

logger = logging.getLogger(__name__)
_cache = CacheManager()
_source = None

# 同花顺概念板块（腾讯云可直连，无需代理）
_ssl_ctx = ssl.create_default_context()
_no_proxy_opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=_ssl_ctx),
)
_THS_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _get_source() -> StockDataSource:
    global _source
    if _source is None:
        _source = get_data_source()
    return _source


def _ths_get(url: str) -> str:
    """请求同花顺网页，返回 HTML 文本（GBK 解码）"""
    req = urllib.request.Request(url, headers={"User-Agent": _THS_UA})
    resp = _no_proxy_opener.open(req, timeout=15)
    body: bytes = resp.read()
    return body.decode("gbk", errors="replace")


def _ths_fetch_concept_list() -> list[dict[str, str]]:
    """从同花顺获取全部概念板块列表，返回 [{code, name}, ...]"""
    cache_key = "ths_concept_list"
    cached: list[dict[str, str]] | None = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        html = _ths_get("https://q.10jqka.com.cn/gn/")
        # 提取: href="http://q.10jqka.com.cn/gn/detail/code/309068/">算力租赁</a>
        # 也可能是 //q.10jqka.com.cn/gn/detail/code/...
        matches = re.findall(
            r'href="[^"]*?/gn/detail/code/(\d+)/"[^>]*>([^<]{2,20})</a>',
            html,
        )
        seen = set()
        result = []
        for code, name in matches:
            name = name.strip()
            if code not in seen and name:
                seen.add(code)
                result.append({"code": code, "name": name})

        if result:
            _cache.set(cache_key, result, ttl_category="basic_info")
            logger.info("同花顺概念列表: %d 个", len(result))
        return result
    except Exception:
        # 失败向上抛: 由 list_concept_stocks 记入 attempts(outcome=error),
        # 吞掉会把"网络挂"伪装成"无此概念"(SPEC F1)
        raise


def _ths_fetch_concept_stocks(ths_code: str, concept_name: str, limit: int = 50) -> list[dict[str, str]]:
    """从同花顺获取指定概念板块的成份股"""
    cache_key = f"ths_stocks_{ths_code}"
    cached = _cache.get(cache_key)
    if cached is not None:
        # 缓存存的是原始 code+name 对，重新组装带 concept 的结果
        return [{**s, "concept": concept_name} for s in cached[:limit]]

    try:
        html = _ths_get(f"http://q.10jqka.com.cn/gn/detail/code/{ths_code}/")
        # 表格结构: 成对 stockpage 链接，第一个是代码，第二个是名称
        pairs = re.findall(
            r'stockpage[^/]*/(\d{6})/?"[^>]*>\d{6}</a>\s*</td>\s*<td>'
            r"<a[^>]*>([^<]+)</a>",
            html,
        )
        results = []
        seen = set()
        for code_6, name in pairs:
            name = name.strip()
            if code_6 in seen or not name:
                continue
            seen.add(code_6)
            # 转为 tushare 格式
            if code_6.startswith("6"):
                ts_code = f"{code_6}.SH"
            elif code_6.startswith(("0", "3")):
                ts_code = f"{code_6}.SZ"
            elif code_6.startswith(("4", "8")):
                ts_code = f"{code_6}.BJ"
            else:
                ts_code = code_6
            results.append(
                {
                    "stock_code": ts_code,
                    "name": name,
                    "concept": concept_name,
                }
            )
            if len(results) >= limit:
                break
        if results:
            # 缓存不含 concept 字段的原始数据，供不同概念名复用
            cache_data = [{"stock_code": s["stock_code"], "name": s["name"]} for s in results]
            _cache.set(cache_key, cache_data, ttl_category="basic_info")
        return results
    except Exception:
        # 同上: 失败向上抛, 由调用链记 error, 不伪装成空
        raise


def _ths_search_concept(concept_name: str, limit: int) -> list[dict[str, str]]:
    """在同花顺概念板块中搜索匹配的概念，返回成份股"""
    concepts = _ths_fetch_concept_list()
    if not concepts:
        return []

    # 模糊匹配：概念名包含搜索词，或搜索词包含概念名
    matched = []
    for c in concepts:
        cname = c.get("name", "")
        if concept_name in cname or cname in concept_name:
            matched.append((c["code"], cname))

    # 拆词匹配兜底
    if not matched and len(concept_name) >= 4:
        parts = [concept_name[: len(concept_name) // 2], concept_name[len(concept_name) // 2 :]]
        for c in concepts:
            cname = c.get("name", "")
            if any(p in cname for p in parts if len(p) >= 2):
                matched.append((c["code"], cname))

    results = []
    seen = set()
    for ths_code, cname in matched[:3]:
        stocks = _ths_fetch_concept_stocks(ths_code, cname, limit=limit)
        for s in stocks:
            code = s.get("stock_code", "")
            if code and code not in seen:
                seen.add(code)
                results.append(s)

    return results[:limit]


def list_concept_stocks(concept_name: str, limit: int = 20) -> dict[str, Any]:
    """按概念/题材名称搜索相关 A 股股票。

    与 list_industry_constituents（申万行业分类）不同，本工具基于市场概念/题材板块，
    覆盖"存储芯片""AI芯片""固态电池""算力""算力租赁""机器人"等热门投资概念。

    数据源：同花顺概念板块（360+ 概念）+ tushare 概念板块 + 关键词搜索。

    Args:
        concept_name: 概念名称（如"存储芯片""AI芯片""算力""算力租赁"）
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
        cache_key = _cache.make_key("ths+ts", "concept", concept_name, str(limit))
        cached = _cache.get(cache_key)
        if cached is not None:
            return ok_response(data=cached, source="ths+tushare", cache_hit=True)

        seen_codes: set[str] = set()
        results: list[dict[str, Any]] = []
        # 三级瀑布逐级留痕（SPEC F1）: outcome ∈ ok / empty / error
        attempts: list[dict[str, Any]] = []

        # 1. 同花顺概念板块（主要数据源）
        try:
            ths_results = _ths_search_concept(concept_name, limit=limit)
            for s in ths_results:
                code = s.get("stock_code", "")
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    results.append(s)
            if ths_results:
                logger.info("同花顺概念「%s」匹配 %d 只", concept_name, len(ths_results))
            attempts.append({"source": "ths_concept", "outcome": "ok" if ths_results else "empty"})
        except Exception as e:
            logger.warning("同花顺概念查询失败: %s", e)
            attempts.append({"source": "ths_concept", "outcome": "error", "detail": str(e)[:200]})

        # 2. tushare 概念板块补充
        if source.name == "tushare" and len(results) < limit:
            try:
                n_before = len(results)
                pro = source._pro  # type: ignore[attr-defined]
                concept_df = pro.concept(src="ts")
                matches = concept_df[concept_df["name"].str.contains(concept_name, na=False)]
                for _, row in matches.iterrows():
                    concept_id = row["code"]
                    detail_df = pro.concept_detail(id=concept_id)
                    if detail_df is not None and not detail_df.empty:
                        for _, stock in detail_df.iterrows():
                            code = stock.get("ts_code", "")
                            if code and code not in seen_codes:
                                seen_codes.add(code)
                                results.append(
                                    {
                                        "stock_code": code,
                                        "name": stock.get("name", ""),
                                        "concept": row["name"],
                                    }
                                )
                attempts.append({"source": "tushare_concept", "outcome": "ok" if len(results) > n_before else "empty"})
            except Exception as e:
                logger.warning("tushare 概念板块查询失败: %s", e)
                attempts.append({"source": "tushare_concept", "outcome": "error", "detail": str(e)[:200]})

        # 3. 关键词搜索兜底（当概念板块都未匹配时）
        if not results:
            keywords = [concept_name]
            if len(concept_name) >= 4:
                mid = len(concept_name) // 2
                keywords.extend([concept_name[:mid], concept_name[mid:]])
            keywords = [kw for kw in keywords if len(kw) >= 2]

            kw_errors: list[str] = []
            for kw in keywords:
                try:
                    search_results = source.search_stocks(kw, limit=20)
                    for s in search_results:
                        code = s.get("stock_code", "")
                        if code and code not in seen_codes:
                            seen_codes.add(code)
                            results.append(
                                {
                                    "stock_code": code,
                                    "name": s.get("name", ""),
                                    "concept": f"搜索「{kw}」",
                                }
                            )
                except Exception as e:
                    logger.warning("关键词搜索「%s」失败: %s", kw, e)
                    kw_errors.append(str(e)[:120])
            if kw_errors and not results:
                outcome = "error" if len(kw_errors) == len(keywords) else "empty"
            else:
                outcome = "ok" if results else "empty"
            attempts.append({"source": "keyword_search", "outcome": outcome})

        results = results[:limit]
        outcomes = [a.get("outcome") for a in attempts]
        all_failed = bool(outcomes) and all(o == "error" for o in outcomes)
        if not results and all_failed and strict_contract():
            return error_response(
                code="UPSTREAM_ERROR",
                message=f"概念「{concept_name}」三级数据源全部失败",
                hint="稍后重试；逐级失败详情见 meta.attempts",
                source="ths+tushare",
                attempts=attempts,
            )
        # 只有结果充足时才缓存（避免缓存坏结果）
        if len(results) >= 3:
            _cache.set(cache_key, results, ttl_category="basic_info")
        empty_reason = None
        if not results:
            empty_reason = EMPTY_UNKNOWN if any(o == "error" for o in outcomes) else EMPTY_CONFIRMED_ABSENT
        return ok_response(
            data=results,
            source="ths+tushare",
            attempts=attempts,
            empty_reason=empty_reason,
        )

    except Exception as e:
        return handle_tool_error(e)
