"""stock_code 模块测试"""

import pytest
from finmcp_common.stock_code import normalize_stock_code, parse_stock_code


class TestNormalizeStockCode:
    # 上交所（6/9 开头）
    def test_sh_6_prefix(self) -> None:
        assert normalize_stock_code("600519") == "600519.SH"

    def test_sh_9_prefix(self) -> None:
        assert normalize_stock_code("900901") == "900901.SH"

    # 深交所（0/2/3 开头）
    def test_sz_0_prefix(self) -> None:
        assert normalize_stock_code("000001") == "000001.SZ"

    def test_sz_3_prefix(self) -> None:
        assert normalize_stock_code("300750") == "300750.SZ"

    def test_sz_2_prefix(self) -> None:
        assert normalize_stock_code("200000") == "200000.SZ"

    # 北交所（4/8 开头）
    def test_bj_4_prefix(self) -> None:
        assert normalize_stock_code("430564") == "430564.BJ"

    def test_bj_8_prefix(self) -> None:
        assert normalize_stock_code("830799") == "830799.BJ"

    # 已带后缀格式
    def test_passthrough_sh(self) -> None:
        assert normalize_stock_code("600519.SH") == "600519.SH"

    def test_passthrough_lowercase(self) -> None:
        assert normalize_stock_code("600519.sh") == "600519.SH"

    # 去除空白
    def test_strip_whitespace(self) -> None:
        assert normalize_stock_code("  600519  ") == "600519.SH"

    # 错误输入
    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="无法识别"):
            normalize_stock_code("ABC")

    def test_too_short(self) -> None:
        with pytest.raises(ValueError, match="无法识别"):
            normalize_stock_code("600")

    def test_invalid_first_digit(self) -> None:
        with pytest.raises(ValueError, match="无法根据代码"):
            normalize_stock_code("100000")


class TestParseStockCode:
    def test_parse_sh(self) -> None:
        code, exchange = parse_stock_code("600519.SH")
        assert code == "600519"
        assert exchange == "SH"

    def test_parse_sz(self) -> None:
        code, exchange = parse_stock_code("000001.SZ")
        assert code == "000001"
        assert exchange == "SZ"

    def test_parse_bj(self) -> None:
        code, exchange = parse_stock_code("430564.BJ")
        assert code == "430564"
        assert exchange == "BJ"

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="无效的完整股票代码"):
            parse_stock_code("600519")
