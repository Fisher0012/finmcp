"""tool 层单元测试

使用 mock 数据源测试所有 8 个 tool 的逻辑分支。
"""

from unittest.mock import MagicMock, patch

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


def _assert_ok(result: dict) -> None:
    """验证成功响应结构"""
    assert result["ok"] is True
    assert "data" in result
    assert "meta" in result
    assert "source" in result["meta"]
    assert "fetched_at" in result["meta"]


def _assert_error(result: dict, code: str | None = None) -> None:
    """验证错误响应结构"""
    assert result["ok"] is False
    assert "error" in result
    assert "code" in result["error"]
    if code:
        assert result["error"]["code"] == code


def _make_mock_source() -> MagicMock:
    """创建 mock 数据源"""
    source = MagicMock()
    source.name = "mock"
    return source


# --- search_stocks_by_name ---

class TestSearchStocksByName:
    def test_empty_query_returns_error(self) -> None:
        result = search_stocks_by_name("")
        _assert_error(result, "INVALID_PARAM")

    def test_whitespace_query_returns_error(self) -> None:
        result = search_stocks_by_name("   ")
        _assert_error(result, "INVALID_PARAM")

    @patch("finmcp_a_stock_data.tools.search._get_source")
    @patch("finmcp_a_stock_data.tools.search._cache")
    def test_returns_data_from_source(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        source.search_stocks.return_value = [
            {"stock_code": "600519.SH", "name": "贵州茅台", "industry": "白酒", "market_cap_yi": None}
        ]
        mock_get_source.return_value = source
        mock_cache.get.return_value = None

        result = search_stocks_by_name("茅台")
        _assert_ok(result)
        assert len(result["data"]) == 1
        assert result["data"][0]["stock_code"] == "600519.SH"

    @patch("finmcp_a_stock_data.tools.search._get_source")
    @patch("finmcp_a_stock_data.tools.search._cache")
    def test_returns_cached_data(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        mock_get_source.return_value = source
        cached_data = [{"stock_code": "600519.SH", "name": "贵州茅台"}]
        mock_cache.get.return_value = cached_data

        result = search_stocks_by_name("茅台")
        _assert_ok(result)
        assert result["meta"]["cache_hit"] is True


# --- get_stock_basic_info ---

class TestGetStockBasicInfo:
    def test_invalid_code_returns_error(self) -> None:
        result = get_stock_basic_info("ABC")
        _assert_error(result, "INVALID_PARAM")

    @patch("finmcp_a_stock_data.tools.basic._get_source")
    @patch("finmcp_a_stock_data.tools.basic._cache")
    def test_returns_basic_info(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        source.get_basic_info.return_value = {
            "stock_code": "600519.SH",
            "name": "贵州茅台",
            "full_name": "贵州茅台酒股份有限公司",
        }
        mock_get_source.return_value = source
        mock_cache.get.return_value = None

        result = get_stock_basic_info("600519")
        _assert_ok(result)
        assert result["data"]["name"] == "贵州茅台"


# --- list_industry_constituents ---

class TestListIndustryConstituents:
    def test_no_params_returns_error(self) -> None:
        result = list_industry_constituents()
        _assert_error(result, "INVALID_PARAM")

    def test_invalid_level_returns_error(self) -> None:
        result = list_industry_constituents(industry_name="白酒", level=5)
        _assert_error(result, "INVALID_PARAM")

    @patch("finmcp_a_stock_data.tools.industry._get_source")
    @patch("finmcp_a_stock_data.tools.industry._cache")
    def test_returns_constituents(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        source.get_industry_constituents.return_value = [
            {"stock_code": "600519.SH", "name": "贵州茅台", "industry": "白酒"},
        ]
        mock_get_source.return_value = source
        mock_cache.get.return_value = None

        result = list_industry_constituents(industry_name="白酒")
        _assert_ok(result)
        assert len(result["data"]) == 1


# --- get_stock_price ---

class TestGetStockPrice:
    def test_invalid_code_returns_error(self) -> None:
        result = get_stock_price("XYZ")
        _assert_error(result, "INVALID_PARAM")

    def test_invalid_period_returns_error(self) -> None:
        result = get_stock_price("600519", period="yearly")
        _assert_error(result, "INVALID_PARAM")

    def test_invalid_adjust_returns_error(self) -> None:
        result = get_stock_price("600519", adjust="abc")
        _assert_error(result, "INVALID_PARAM")

    def test_invalid_date_returns_error(self) -> None:
        result = get_stock_price("600519", start_date="bad-date")
        _assert_error(result, "INVALID_PARAM")

    @patch("finmcp_a_stock_data.tools.price._get_source")
    @patch("finmcp_a_stock_data.tools.price._cache")
    def test_returns_price_data(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        source.get_daily_price.return_value = [
            {
                "date": "2026-05-14", "open": 1580, "high": 1600, "low": 1575,
                "close": 1595, "volume": 25000, "amount": 3987500000,
            }
        ]
        mock_get_source.return_value = source
        mock_cache.get.return_value = None

        result = get_stock_price("600519")
        _assert_ok(result)
        assert len(result["data"]) == 1
        assert result["data"][0]["close"] == 1595


# --- get_latest_quote ---

class TestGetLatestQuote:
    def test_invalid_code_returns_error(self) -> None:
        result = get_latest_quote("ABC")
        _assert_error(result, "INVALID_PARAM")

    @patch("finmcp_a_stock_data.tools.quote._get_source")
    @patch("finmcp_a_stock_data.tools.quote._cache")
    def test_returns_quote(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        source.get_latest_quote.return_value = {
            "stock_code": "600519.SH",
            "name": "贵州茅台",
            "current_price": 1595.0,
            "change": 20.0,
            "pct_change": 1.27,
        }
        mock_get_source.return_value = source
        mock_cache.get.return_value = None

        result = get_latest_quote("600519")
        _assert_ok(result)
        assert result["data"]["current_price"] == 1595.0


# --- get_index_price ---

class TestGetIndexPrice:
    def test_no_exchange_suffix_returns_error(self) -> None:
        result = get_index_price("000001")
        _assert_error(result, "INVALID_PARAM")

    def test_invalid_period_returns_error(self) -> None:
        result = get_index_price("000001.SH", period="yearly")
        _assert_error(result, "INVALID_PARAM")

    @patch("finmcp_a_stock_data.tools.index._get_source")
    @patch("finmcp_a_stock_data.tools.index._cache")
    def test_returns_index_data(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        source.get_index_price.return_value = [
            {
                "date": "2026-05-14", "open": 3150, "high": 3180, "low": 3145,
                "close": 3175, "volume": 350000000, "amount": 450000000000,
            }
        ]
        mock_get_source.return_value = source
        mock_cache.get.return_value = None

        result = get_index_price("000001.SH")
        _assert_ok(result)
        assert len(result["data"]) == 1


# --- get_financial_indicator ---

class TestGetFinancialIndicator:
    def test_invalid_code_returns_error(self) -> None:
        result = get_financial_indicator("BAD")
        _assert_error(result, "INVALID_PARAM")

    def test_invalid_indicator_returns_error(self) -> None:
        result = get_financial_indicator("600519", indicators=["fake_indicator"])
        _assert_error(result, "INVALID_PARAM")

    @patch("finmcp_a_stock_data.tools.financial._get_source")
    @patch("finmcp_a_stock_data.tools.financial._cache")
    def test_returns_indicators(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        source.get_financial_indicator.return_value = [
            {"report_period": "2025-12-31", "roe": 30.5, "eps": 60.8},
        ]
        mock_get_source.return_value = source
        mock_cache.get.return_value = None

        result = get_financial_indicator("600519", indicators=["roe", "eps"], years=3)
        _assert_ok(result)
        assert result["data"][0]["roe"] == 30.5


# --- get_financial_report_summary ---

class TestGetFinancialReportSummary:
    def test_invalid_code_returns_error(self) -> None:
        result = get_financial_report_summary("XYZ")
        _assert_error(result, "INVALID_PARAM")

    def test_invalid_period_returns_error(self) -> None:
        result = get_financial_report_summary("600519", report_period="2024-05-15")
        _assert_error(result, "INVALID_PARAM")

    @patch("finmcp_a_stock_data.tools.financial._get_source")
    @patch("finmcp_a_stock_data.tools.financial._cache")
    def test_returns_report(self, mock_cache: MagicMock, mock_get_source: MagicMock) -> None:
        source = _make_mock_source()
        source.get_financial_report.return_value = {
            "stock_code": "600519.SH",
            "report_period": "2024-12-31",
            "revenue": 170000000000.0,
            "net_profit": 86200000000.0,
        }
        mock_get_source.return_value = source
        mock_cache.get.return_value = None

        result = get_financial_report_summary("600519", report_period="2024-12-31")
        _assert_ok(result)
        assert result["data"]["revenue"] == 170000000000.0
