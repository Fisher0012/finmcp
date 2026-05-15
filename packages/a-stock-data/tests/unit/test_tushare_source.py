"""TushareSource 单元测试

mock tushare.pro_api，测试数据转换逻辑。
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from finmcp_common.errors import AuthRequiredError, DataNotFoundError


class TestTushareSourceInit:
    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_init_with_valid_token(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        source = TushareSource(token="test_token")
        assert source.name == "tushare"
        mock_ts.set_token.assert_called_once_with("test_token")

    def test_init_without_token_raises(self) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        with pytest.raises(AuthRequiredError):
            TushareSource(token="")


class TestTushareSearchStocks:
    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_search_by_name(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        mock_pro = MagicMock()
        mock_ts.pro_api.return_value = mock_pro
        mock_pro.stock_basic.return_value = pd.DataFrame({
            "ts_code": ["600519.SH", "000858.SZ", "000001.SZ"],
            "name": ["贵州茅台", "五粮液", "平安银行"],
            "industry": ["白酒", "白酒", "银行"],
            "market": ["主板", "主板", "主板"],
            "list_date": ["20010827", "19980427", "19910403"],
        })

        source = TushareSource(token="test")
        results = source.search_stocks("茅台", limit=5)

        assert len(results) == 1
        assert results[0]["stock_code"] == "600519.SH"
        assert results[0]["name"] == "贵州茅台"

    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_search_empty_result(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        mock_pro = MagicMock()
        mock_ts.pro_api.return_value = mock_pro
        mock_pro.stock_basic.return_value = pd.DataFrame({
            "ts_code": ["600519.SH"],
            "name": ["贵州茅台"],
            "industry": ["白酒"],
            "market": ["主板"],
            "list_date": ["20010827"],
        })

        source = TushareSource(token="test")
        results = source.search_stocks("不存在的公司")
        assert len(results) == 0


class TestTushareGetBasicInfo:
    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_get_basic_info(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        mock_pro = MagicMock()
        mock_ts.pro_api.return_value = mock_pro

        mock_pro.stock_basic.return_value = pd.DataFrame({
            "ts_code": ["600519.SH"],
            "name": ["贵州茅台"],
            "fullname": ["贵州茅台酒股份有限公司"],
            "enname": ["Kweichow Moutai Co.,Ltd."],
            "industry": ["白酒"],
            "area": ["贵州"],
            "list_date": ["20010827"],
            "market": ["主板"],
            "exchange": ["SSE"],
            "is_hs": ["H"],
        })
        mock_pro.daily_basic.return_value = pd.DataFrame({
            "ts_code": ["600519.SH"],
            "total_share": [125619.78],
            "float_share": [125619.78],
        })

        source = TushareSource(token="test")
        result = source.get_basic_info("600519.SH")

        assert result["stock_code"] == "600519.SH"
        assert result["name"] == "贵州茅台"
        assert result["full_name"] == "贵州茅台酒股份有限公司"
        assert result["total_share"] == 125619.78

    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_not_found(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        mock_pro = MagicMock()
        mock_ts.pro_api.return_value = mock_pro
        mock_pro.stock_basic.return_value = pd.DataFrame()

        source = TushareSource(token="test")
        with pytest.raises(DataNotFoundError):
            source.get_basic_info("999999.SH")


class TestTushareGetDailyPrice:
    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_get_daily_price(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        mock_pro = MagicMock()
        mock_ts.pro_api.return_value = mock_pro
        mock_ts.pro_bar.return_value = pd.DataFrame({
            "ts_code": ["600519.SH", "600519.SH"],
            "trade_date": ["20260514", "20260513"],
            "open": [1580.0, 1570.0],
            "high": [1600.0, 1585.0],
            "low": [1575.0, 1565.0],
            "close": [1595.0, 1578.0],
            "vol": [25000.0, 22000.0],
            "amount": [3987500.0, 3456000.0],
            "pct_chg": [1.08, -0.32],
        })

        source = TushareSource(token="test")
        results = source.get_daily_price("600519.SH", "20260501", "20260514")

        assert len(results) == 2
        assert results[0]["date"] == "2026-05-14"
        assert results[0]["close"] == 1595.0
        assert results[0]["pct_change"] == 1.08

    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_empty_result_raises(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        mock_pro = MagicMock()
        mock_ts.pro_api.return_value = mock_pro
        mock_ts.pro_bar.return_value = pd.DataFrame()

        source = TushareSource(token="test")
        with pytest.raises(DataNotFoundError):
            source.get_daily_price("600519.SH", "20300101", "20300201")


class TestTushareGetLatestQuote:
    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_get_latest_quote(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        mock_pro = MagicMock()
        mock_ts.pro_api.return_value = mock_pro
        mock_ts.pro_bar.return_value = pd.DataFrame({
            "ts_code": ["600519.SH", "600519.SH"],
            "trade_date": ["20260514", "20260513"],
            "open": [1580.0, 1570.0],
            "high": [1600.0, 1585.0],
            "low": [1575.0, 1565.0],
            "close": [1595.0, 1578.0],
            "vol": [25000.0, 22000.0],
            "amount": [3987500.0, 3456000.0],
            "pct_chg": [1.08, -0.32],
        })
        mock_pro.daily_basic.return_value = pd.DataFrame({
            "ts_code": ["600519.SH"],
            "pe_ttm": [26.5],
            "pb": [8.2],
            "total_mv": [200358000.0],
        })
        mock_pro.stock_basic.return_value = pd.DataFrame({
            "ts_code": ["600519.SH"],
            "name": ["贵州茅台"],
        })

        source = TushareSource(token="test")
        result = source.get_latest_quote("600519.SH")

        assert result["current_price"] == 1595.0
        assert result["prev_close"] == 1578.0
        assert result["pe_ttm"] == 26.5


class TestTushareGetFinancialIndicator:
    @patch("finmcp_a_stock_data.data_sources.tushare_src.ts")
    def test_get_indicators(self, mock_ts: MagicMock) -> None:
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        mock_pro = MagicMock()
        mock_ts.pro_api.return_value = mock_pro
        mock_pro.fina_indicator.return_value = pd.DataFrame({
            "ts_code": ["600519.SH", "600519.SH"],
            "ann_date": ["20260401", "20250401"],
            "end_date": ["20251231", "20241231"],
            "roe": [30.5, 29.8],
            "roa": [22.1, 21.5],
            "grossprofit_margin": [91.5, 91.3],
            "netprofit_margin": [51.2, 50.8],
            "revenue_yoy": [15.0, 12.0],
            "net_profit_yoy": [14.0, 11.0],
            "debt_to_assets": [32.0, 33.0],
            "current_ratio": [3.5, 3.2],
            "assets_turn": [0.45, 0.42],
            "inventory_turn": [0.35, 0.33],
            "eps": [60.8, 57.2],
            "bvps": [200.0, 190.0],
            "ocfps": [55.0, 52.0],
        })
        mock_pro.daily_basic.return_value = pd.DataFrame()

        source = TushareSource(token="test")
        results = source.get_financial_indicator("600519.SH", years=2)

        assert len(results) == 2
        assert results[0]["report_period"] == "2025-12-31"
        assert results[0]["roe"] == 30.5
        assert results[0]["gross_margin"] == 91.5
