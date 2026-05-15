"""Tushare 集成测试

需要 TUSHARE_TOKEN 环境变量，没有时自动跳过。
测试真实 tushare API 调用，验证数据格式和字段完整性。
"""

import os

import pytest

# 没有 token 则跳过全部集成测试
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
pytestmark = pytest.mark.skipif(
    not TUSHARE_TOKEN,
    reason="TUSHARE_TOKEN not set, skipping integration tests",
)


@pytest.fixture(scope="module")
def source():
    """创建真实的 TushareSource 实例"""
    from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

    return TushareSource(token=TUSHARE_TOKEN)


class TestSearchStocksIntegration:
    def test_search_maotai(self, source) -> None:
        results = source.search_stocks("茅台", limit=5)
        assert len(results) >= 1
        codes = [r["stock_code"] for r in results]
        assert "600519.SH" in codes

    def test_search_by_code_prefix(self, source) -> None:
        results = source.search_stocks("600519", limit=5)
        assert len(results) >= 1

    def test_search_no_match(self, source) -> None:
        results = source.search_stocks("ZZZZZZZ不存在的公司", limit=5)
        assert len(results) == 0


class TestGetBasicInfoIntegration:
    def test_maotai_basic_info(self, source) -> None:
        result = source.get_basic_info("600519.SH")
        assert result["stock_code"] == "600519.SH"
        assert result["name"] == "贵州茅台"
        assert result["area"] == "贵州"
        assert result["list_date"]  # 非空

    def test_not_found(self, source) -> None:
        from finmcp_common.errors import DataNotFoundError

        with pytest.raises(DataNotFoundError):
            source.get_basic_info("999999.SH")


class TestGetDailyPriceIntegration:
    def test_maotai_recent(self, source) -> None:
        results = source.get_daily_price(
            "600519.SH", "20260101", "20260515",
        )
        assert len(results) > 0
        first = results[0]
        assert "date" in first
        assert "open" in first
        assert "close" in first
        assert "volume" in first

    def test_weekly(self, source) -> None:
        results = source.get_daily_price(
            "600519.SH", "20260101", "20260515", period="weekly",
        )
        assert len(results) > 0


class TestGetLatestQuoteIntegration:
    def test_maotai_quote(self, source) -> None:
        result = source.get_latest_quote("600519.SH")
        assert result["stock_code"] == "600519.SH"
        assert result["current_price"] > 0
        assert "pct_change" in result


class TestGetIndexPriceIntegration:
    def test_shanghai_index(self, source) -> None:
        results = source.get_index_price(
            "000001.SH", "20260101", "20260515",
        )
        assert len(results) > 0
        assert results[0]["close"] > 0

    def test_csi300(self, source) -> None:
        results = source.get_index_price(
            "000300.SH", "20260101", "20260515",
        )
        assert len(results) > 0


class TestGetIndustryConstituentsIntegration:
    def test_baijiu(self, source) -> None:
        results = source.get_industry_constituents(industry_name="白酒")
        assert len(results) > 0
        # 茅台应该在白酒行业
        codes = [r["stock_code"] for r in results]
        assert any("600519" in c for c in codes)


class TestGetFinancialIndicatorIntegration:
    def test_maotai_roe(self, source) -> None:
        results = source.get_financial_indicator(
            "600519.SH", indicators=["roe", "eps"], years=3,
        )
        assert len(results) >= 1
        assert results[0]["report_period"]
        assert results[0]["roe"] is not None
        assert results[0]["roe"] > 0  # 茅台 ROE 一定为正

    def test_all_indicators(self, source) -> None:
        results = source.get_financial_indicator("600519.SH", years=1)
        assert len(results) >= 1
        # 应该有所有字段
        assert "gross_margin" in results[0]


class TestGetFinancialReportIntegration:
    def test_maotai_annual_report(self, source) -> None:
        result = source.get_financial_report("600519.SH", "20241231")
        assert result["stock_code"] == "600519.SH"
        assert result["revenue"] is not None
        assert result["revenue"] > 0
        assert result["net_profit"] is not None

    def test_maotai_latest(self, source) -> None:
        result = source.get_financial_report("600519.SH")
        assert result["stock_code"] == "600519.SH"
        assert result["report_period"]


class TestEndToEndScenarios:
    """设计文档 4_MVP_SCOPE.md §6 的 10 个验收用例"""

    def test_scenario_1_maotai_roe_5y(self, source) -> None:
        """茅台最近五年 ROE"""
        search = source.search_stocks("茅台", limit=1)
        assert search[0]["stock_code"] == "600519.SH"
        indicators = source.get_financial_indicator(
            "600519.SH", indicators=["roe"], years=5,
        )
        assert len(indicators) >= 3  # 至少 3 年数据

    def test_scenario_3_ningde_quote(self, source) -> None:
        """宁德时代今天涨了多少"""
        search = source.search_stocks("宁德时代", limit=1)
        assert any("300750" in r["stock_code"] for r in search)
        quote = source.get_latest_quote("300750.SZ")
        assert quote["current_price"] > 0

    def test_scenario_4_shanghai_index_1m(self, source) -> None:
        """上证指数最近一个月"""
        results = source.get_index_price("000001.SH", "20260415", "20260515")
        assert len(results) > 10

    def test_scenario_9_cmb_industry(self, source) -> None:
        """招商银行所属行业"""
        result = source.get_basic_info("600036.SH")
        assert result["name"] == "招商银行"
        assert result["industry_l1"]  # 非空

    def test_scenario_10_maotai_business(self, source) -> None:
        """600519 这家公司是做什么的"""
        result = source.get_basic_info("600519.SH")
        assert result["name"] == "贵州茅台"
        assert result["full_name"]
