"""CacheManager 单元测试"""

import tempfile

from finmcp_a_stock_data.cache import CacheManager


class TestCacheManager:
    def test_make_key(self) -> None:
        cache = CacheManager()
        key = cache.make_key("tushare", "price", "600519.SH", "20260514")
        assert key == "tushare:price:600519.SH:20260514"

    def test_set_and_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=tmpdir)
            cache.set("test_key", {"value": 42}, ttl_category="daily")
            result = cache.get("test_key")
            assert result == {"value": 42}
            cache.close()

    def test_get_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=tmpdir)
            result = cache.get("nonexistent")
            assert result is None
            cache.close()

    def test_different_ttl_categories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=tmpdir)
            cache.set("rt", "realtime_data", ttl_category="realtime")
            cache.set("daily", "daily_data", ttl_category="daily")
            cache.set("basic", "basic_data", ttl_category="basic_info")
            cache.set("fin", "fin_data", ttl_category="financial")

            assert cache.get("rt") == "realtime_data"
            assert cache.get("daily") == "daily_data"
            assert cache.get("basic") == "basic_data"
            assert cache.get("fin") == "fin_data"
            cache.close()
