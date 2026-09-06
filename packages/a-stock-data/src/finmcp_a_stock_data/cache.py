"""本地缓存层

使用 diskcache 做本地持久化缓存，减少上游数据源调用。
"""

import os
from typing import Any

from finmcp_common.logging import get_logger

logger = get_logger(__name__)

# 缓存 TTL 策略（秒）
CACHE_TTL = {
    "realtime": int(os.getenv("FINMCP_CACHE_TTL_REALTIME", "60")),
    "daily": 7 * 24 * 3600,  # 历史数据：7 天
    "basic_info": 30 * 24 * 3600,  # 基础信息：30 天
    "financial": 24 * 3600,  # 财务数据：1 天
    "quarterly": 90 * 24 * 3600,  # 季度级披露（年报 MD&A 等）：90 天
}


class CacheManager:
    """diskcache 缓存管理器"""

    def __init__(self, cache_dir: str | None = None) -> None:
        default_dir = os.getenv("FINMCP_CACHE_DIR") or os.path.expanduser("~/.finmcp/cache")
        self._cache_dir: str = cache_dir or default_dir
        self._cache: Any = None

    def _get_cache(self) -> Any:
        """懒初始化 diskcache.Cache"""
        if self._cache is None:
            import diskcache

            os.makedirs(self._cache_dir, exist_ok=True)
            self._cache = diskcache.Cache(self._cache_dir)
            logger.debug("缓存目录: %s", self._cache_dir)
        return self._cache

    def get(self, key: str) -> Any | None:
        """查询缓存，未命中返回 None"""
        cache = self._get_cache()
        value = cache.get(key)
        if value is not None:
            logger.debug("缓存命中: %s", key)
        return value

    def set(self, key: str, value: Any, ttl_category: str = "daily") -> None:
        """写入缓存

        Args:
            key: 缓存键
            value: 缓存值
            ttl_category: TTL 类别（realtime/daily/basic_info/financial）
        """
        ttl = CACHE_TTL.get(ttl_category, CACHE_TTL["daily"])
        cache = self._get_cache()
        cache.set(key, value, expire=ttl)
        logger.debug("缓存写入: %s (TTL=%ds)", key, ttl)

    def make_key(self, *parts: str | int | float) -> str:
        """构造缓存键

        Args:
            parts: 键的组成部分（如 data_source, tool_name, stock_code, date）

        2026-09-06 修复(batch-5 T9): 调用方以位置参数误传 int(如 limit 落到 sort_by 位)
        时 join 抛 "sequence item N: expected str instance, int found", 被错误处理器包成
        INTERNAL_ERROR, 掩盖真实参数问题——键构造对类型鲁棒, 统一 str 化。
        """
        return ":".join(str(p) for p in parts)

    def close(self) -> None:
        """关闭缓存"""
        if self._cache is not None:
            self._cache.close()
