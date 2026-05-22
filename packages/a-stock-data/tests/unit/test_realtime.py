"""新浪财经实时行情模块单元测试"""

from unittest.mock import MagicMock, patch

from finmcp_a_stock_data.realtime import _to_sina_symbol, _safe_float, fetch_sina_realtime


class TestToSinaSymbol:
    def test_sz_code(self) -> None:
        assert _to_sina_symbol("002475.SZ") == "sz002475"

    def test_sh_code(self) -> None:
        assert _to_sina_symbol("600519.SH") == "sh600519"

    def test_bj_code(self) -> None:
        assert _to_sina_symbol("430047.BJ") == "bj430047"

    def test_invalid_exchange(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="不支持的交易所后缀"):
            _to_sina_symbol("000001.XX")


class TestSafeFloat:
    def test_normal_value(self) -> None:
        assert _safe_float("72.4") == 72.4

    def test_empty_string(self) -> None:
        assert _safe_float("") is None

    def test_invalid_string(self) -> None:
        assert _safe_float("abc") is None

    def test_none_value(self) -> None:
        assert _safe_float(None) is None


# 模拟新浪正常响应
_MOCK_SINA_RESPONSE = (
    'var hq_str_sz002475="立讯精密,69.500,67.870,72.400,72.880,68.900,'
    '72.390,72.400,186637744,13302102231.430,'
    '181000,72.390,37400,72.380,23300,72.370,43238,72.360,4300,72.350,'
    '310403,72.400,25200,72.410,18100,72.420,9800,72.430,1800,72.440,'
    '2026-05-22,15:00:00,00";'
)


class TestFetchSinaRealtime:
    @patch("finmcp_a_stock_data.realtime.requests.get")
    def test_success(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _MOCK_SINA_RESPONSE
        mock_get.return_value = mock_resp

        result = fetch_sina_realtime("002475.SZ")
        assert result is not None
        assert result["stock_code"] == "002475.SZ"
        assert result["name"] == "立讯精密"
        assert result["current_price"] == 72.4
        assert result["prev_close"] == 67.87
        assert result["pct_change"] == 6.67
        # 成交量: 186637744股 / 100 = 1866377.44手
        assert result["volume"] == 1866377.44
        # 成交额: 13302102231.43元 / 1000 = 13302102.23千元
        assert result["amount"] == 13302102.23

    @patch("finmcp_a_stock_data.realtime.requests.get")
    def test_network_error_returns_none(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("网络超时")
        result = fetch_sina_realtime("002475.SZ")
        assert result is None

    @patch("finmcp_a_stock_data.realtime.requests.get")
    def test_empty_response_returns_none(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.text = 'var hq_str_sz002475="";'
        mock_get.return_value = mock_resp
        result = fetch_sina_realtime("002475.SZ")
        assert result is None

    @patch("finmcp_a_stock_data.realtime.requests.get")
    def test_suspended_stock_returns_none(self, mock_get: MagicMock) -> None:
        """停牌股票当前价为 0"""
        # 模拟停牌：所有价格字段为 0
        mock_resp = MagicMock()
        mock_resp.text = (
            'var hq_str_sz002475="停牌股,0.000,10.000,0.000,0.000,0.000,'
            '0.000,0.000,0,0.000,'
            '0,0,0,0,0,0,0,0,0,0,'
            '0,0,0,0,0,0,0,0,0,0,'
            '2026-05-22,09:30:00,00";'
        )
        mock_get.return_value = mock_resp
        result = fetch_sina_realtime("002475.SZ")
        assert result is None

    def test_invalid_code_returns_none(self) -> None:
        result = fetch_sina_realtime("000001.XX")
        assert result is None
