"""Stage 1 stub tool 测试

验证所有 8 个 tool 返回符合标准响应结构。
"""

from finmcp_a_stock_data.tools.basic import get_stock_basic_info
from finmcp_a_stock_data.tools.financial import (
    get_financial_indicator,
    get_financial_report_summary,
)
from finmcp_a_stock_data.tools.index import get_index_price
from finmcp_a_stock_data.tools.industry import list_industry_constituents
from finmcp_a_stock_data.tools.price import get_stock_price
from finmcp_a_stock_data.tools.quote import get_latest_quote
from finmcp_a_stock_data.tools.search import search_stocks_by_name


def _assert_ok_response(result: dict) -> None:
    """验证标准成功响应结构"""
    assert result["ok"] is True
    assert "data" in result
    assert "meta" in result
    assert "source" in result["meta"]
    assert "fetched_at" in result["meta"]


class TestSearchStocksByName:
    def test_returns_ok_response(self) -> None:
        result = search_stocks_by_name("茅台")
        _assert_ok_response(result)
        assert isinstance(result["data"], list)
        assert len(result["data"]) > 0

    def test_result_has_required_fields(self) -> None:
        result = search_stocks_by_name("茅台")
        item = result["data"][0]
        assert "stock_code" in item
        assert "name" in item


class TestGetStockBasicInfo:
    def test_returns_ok_response(self) -> None:
        result = get_stock_basic_info("600519")
        _assert_ok_response(result)
        assert isinstance(result["data"], dict)

    def test_result_has_required_fields(self) -> None:
        result = get_stock_basic_info("600519")
        data = result["data"]
        assert "stock_code" in data
        assert "name" in data


class TestListIndustryConstituents:
    def test_returns_ok_response(self) -> None:
        result = list_industry_constituents(industry_name="白酒")
        _assert_ok_response(result)
        assert isinstance(result["data"], list)


class TestGetStockPrice:
    def test_returns_ok_response(self) -> None:
        result = get_stock_price("600519")
        _assert_ok_response(result)
        assert isinstance(result["data"], list)

    def test_price_bar_fields(self) -> None:
        result = get_stock_price("600519")
        bar = result["data"][0]
        for field in ["date", "open", "high", "low", "close", "volume"]:
            assert field in bar


class TestGetLatestQuote:
    def test_returns_ok_response(self) -> None:
        result = get_latest_quote("600519")
        _assert_ok_response(result)
        assert isinstance(result["data"], dict)

    def test_quote_fields(self) -> None:
        result = get_latest_quote("600519")
        data = result["data"]
        for field in ["current_price", "change", "pct_change"]:
            assert field in data


class TestGetIndexPrice:
    def test_returns_ok_response(self) -> None:
        result = get_index_price("000001.SH")
        _assert_ok_response(result)
        assert isinstance(result["data"], list)


class TestGetFinancialIndicator:
    def test_returns_ok_response(self) -> None:
        result = get_financial_indicator("600519")
        _assert_ok_response(result)
        assert isinstance(result["data"], list)

    def test_has_report_period(self) -> None:
        result = get_financial_indicator("600519")
        assert "report_period" in result["data"][0]


class TestGetFinancialReportSummary:
    def test_returns_ok_response(self) -> None:
        result = get_financial_report_summary("600519")
        _assert_ok_response(result)
        assert isinstance(result["data"], dict)

    def test_has_key_fields(self) -> None:
        result = get_financial_report_summary("600519")
        data = result["data"]
        assert "stock_code" in data
        assert "report_period" in data
        assert "revenue" in data
