"""SPEC F5 新数据域工具单元测试

get_macro_indicator / get_dividend_history / get_northbound_flow
每工具 ≥3 mock 用例: 成功 schema + 空 confirmed_absent + 异常 UPSTREAM_ERROR + 参数校验。
mock 风格仿 test_sunk_tools.py: patch tushare.pro_api + pd.DataFrame 假数据。
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
from finmcp_a_stock_data.tools.dividend import get_dividend_history
from finmcp_a_stock_data.tools.macro import get_macro_indicator
from finmcp_a_stock_data.tools.northbound import get_northbound_flow


def _assert_ok(result: dict[str, Any]) -> None:
    assert result["ok"] is True
    assert "data" in result
    assert "meta" in result
    assert "contract_version" in result["meta"]


def _assert_error(result: dict[str, Any], code: str) -> None:
    assert result["ok"] is False
    assert result["error"]["code"] == code


# ── get_macro_indicator ──────────────────────────────────────


class TestMacroIndicator:
    def test_unknown_indicator_lists_supported(self) -> None:
        r = get_macro_indicator("ppi")
        _assert_error(r, "INVALID_PARAM")
        for name in ("gdp", "cpi", "pmi", "lpr"):
            assert name in r["error"]["message"]

    def test_invalid_periods(self) -> None:
        _assert_error(get_macro_indicator("gdp", periods=0), "INVALID_PARAM")

    @patch("tushare.pro_api")
    def test_gdp_success_schema(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.cn_gdp.return_value = pd.DataFrame(
            {
                "quarter": ["2025Q4", "2026Q1", "2026Q2"],
                "gdp": [1350000.0, 320000.0, 660000.0],
                "gdp_yoy": [5.0, 5.3, 5.2],
                "pi": [90000.0, 11000.0, 26000.0],
                "pi_yoy": [3.0, 3.5, 3.4],
            }
        )
        r = get_macro_indicator("gdp", periods=2)
        _assert_ok(r)
        assert r["data"]["indicator"] == "gdp"
        assert len(r["data"]["periods"]) == 2  # 尊重 periods
        # 按期标识降序取最近
        assert r["data"]["periods"][0]["quarter"] == "2026Q2"
        assert r["data"]["periods"][1]["quarter"] == "2026Q1"
        assert r["data"]["periods"][0]["gdp"] == 660000.0
        assert "note" in r["data"]

    @patch("tushare.pro_api")
    def test_pmi_uppercase_columns_normalized_with_glossary(self, mock_pro_api: MagicMock) -> None:
        """实调 cn_pmi 返回大写代码列 → 小写归一 + field_glossary 只含已核实字段"""
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.cn_pmi.return_value = pd.DataFrame(
            {
                "MONTH": ["202607", "202608"],
                "PMI010000": [49.5, 50.2],
                "PMI010702": [48.0, 48.1],
                "PMI999999": [1.0, 2.0],  # 未收录代码: 透传但不进 glossary
            }
        )
        r = get_macro_indicator("pmi", periods=12)
        _assert_ok(r)
        latest = r["data"]["periods"][0]
        assert latest["month"] == "202608"
        assert latest["pmi010000"] == 50.2
        assert latest["pmi999999"] == 2.0  # 原样透传
        glossary = r["data"]["field_glossary"]
        assert glossary["pmi010000"] == "制造业PMI"
        assert glossary["pmi010702"] == "制造业PMI:构成指数/原材料库存指数:中型企业"
        assert "pmi999999" not in glossary  # 禁止编造未核实字段含义

    @patch("tushare.pro_api")
    def test_lpr_success_schema(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.shibor_lpr.return_value = pd.DataFrame(
            {
                "date": ["20260901", "20260831"],
                "1y": [3.0, 3.0],
                "5y": [3.5, float("nan")],  # NaN → None
            }
        )
        r = get_macro_indicator("lpr", periods=5)
        _assert_ok(r)
        assert r["data"]["periods"][0]["date"] == "20260901"
        assert r["data"]["periods"][0]["1y"] == 3.0
        assert r["data"]["periods"][1]["5y"] is None

    @patch("tushare.pro_api")
    def test_empty_is_confirmed_absent(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.cn_cpi.return_value = pd.DataFrame()
        r = get_macro_indicator("cpi")
        _assert_ok(r)
        assert r["data"]["periods"] == []
        assert r["meta"]["empty_reason"] == "confirmed_absent"

    @patch("tushare.pro_api")
    def test_upstream_exception_is_error(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.cn_gdp.side_effect = RuntimeError("boom")
        _assert_error(get_macro_indicator("gdp"), "UPSTREAM_ERROR")


# ── get_dividend_history ─────────────────────────────────────


def _recent(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")


class TestDividendHistory:
    def test_empty_param(self) -> None:
        _assert_error(get_dividend_history(""), "INVALID_PARAM")
        _assert_error(get_dividend_history("600519.SH", years=0), "INVALID_PARAM")

    @patch("tushare.pro_api")
    def test_success_keeps_only_implemented(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.dividend.return_value = pd.DataFrame(
            {
                "ts_code": ["600519.SH"] * 3,
                "end_date": [_recent(400), _recent(100), _recent(30)],
                "ann_date": [_recent(350), _recent(60), _recent(20)],
                "div_proc": ["实施", "实施", "预案"],
                "stk_div": [0.0, 0.0, 0.0],
                "cash_div": [25.911, 23.882, 20.0],
                "cash_div_tax": [28.79, 26.535, 22.0],
            }
        )
        r = get_dividend_history("600519.SH", years=5)
        _assert_ok(r)
        assert len(r["data"]["dividends"]) == 2  # 预案不进列表
        d = r["data"]["dividends"][0]  # end_date 降序, 最新在前
        assert set(d) == {"end_date", "ann_date", "cash_div", "cash_div_tax", "stk_div"}
        assert d["cash_div"] == 23.882  # 税后
        assert d["cash_div_tax"] == 26.535  # 税前
        assert r["data"]["other_proc_counts"] == {"预案": 1}

    @patch("tushare.pro_api")
    def test_years_window_filters_old_records(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.dividend.return_value = pd.DataFrame(
            {
                "ts_code": ["600519.SH"] * 2,
                "end_date": [_recent(365 * 4), _recent(100)],
                "ann_date": [_recent(365 * 4 - 30), _recent(60)],
                "div_proc": ["实施", "实施"],
                "stk_div": [0.0, 0.0],
                "cash_div": [10.0, 20.0],
                "cash_div_tax": [11.0, 22.0],
            }
        )
        r = get_dividend_history("600519.SH", years=2)
        _assert_ok(r)
        assert len(r["data"]["dividends"]) == 1
        assert r["data"]["dividends"][0]["cash_div"] == 20.0

    @patch("tushare.pro_api")
    def test_empty_is_confirmed_absent(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.dividend.return_value = pd.DataFrame()
        r = get_dividend_history("600519.SH")
        _assert_ok(r)
        assert r["data"]["dividends"] == []
        assert r["meta"]["empty_reason"] == "confirmed_absent"

    @patch("tushare.pro_api")
    def test_no_implemented_is_confirmed_absent_with_counts(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.dividend.return_value = pd.DataFrame(
            {
                "ts_code": ["600519.SH"],
                "end_date": [_recent(30)],
                "ann_date": [_recent(20)],
                "div_proc": ["预案"],
                "stk_div": [0.0],
                "cash_div": [20.0],
                "cash_div_tax": [22.0],
            }
        )
        r = get_dividend_history("600519.SH")
        _assert_ok(r)
        assert r["data"]["dividends"] == []
        assert r["data"]["other_proc_counts"] == {"预案": 1}
        assert r["meta"]["empty_reason"] == "confirmed_absent"

    @patch("tushare.pro_api")
    def test_upstream_exception_is_error(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.dividend.side_effect = RuntimeError("boom")
        _assert_error(get_dividend_history("600519.SH"), "UPSTREAM_ERROR")


# ── get_northbound_flow ──────────────────────────────────────


class TestNorthboundFlow:
    def test_invalid_days(self) -> None:
        _assert_error(get_northbound_flow(days=0), "INVALID_PARAM")

    @patch("tushare.pro_api")
    def test_success_schema_and_unit_note(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.moneyflow_hsgt.return_value = pd.DataFrame(
            {
                "trade_date": ["20260831", "20260901"],
                "ggt_ss": [-476.0, 100.0],
                "ggt_sz": [-188.0, 50.0],
                "hgt": [962.68, float("nan")],  # 2024 口径调整后可能缺失 → None
                "sgt": [799.94, float("nan")],
                "north_money": [1762.62, float("nan")],
                "south_money": [-664.0, 150.0],
            }
        )
        r = get_northbound_flow(days=30)
        _assert_ok(r)
        daily = r["data"]["daily"]
        assert daily[0]["trade_date"] == "20260901"  # 降序, 最新在前
        assert set(daily[0]) == {"trade_date", "north_money", "south_money", "hgt", "sgt"}
        assert daily[0]["north_money"] is None  # NaN 透传为 None, 不估算
        assert daily[1]["north_money"] == 1762.62
        assert "百万元" in r["data"]["note"]
        # 调用参数为 YYYYMMDD 区间
        kwargs = pro.moneyflow_hsgt.call_args.kwargs
        assert len(kwargs["start_date"]) == 8 and len(kwargs["end_date"]) == 8

    @patch("tushare.pro_api")
    def test_empty_is_confirmed_absent(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.moneyflow_hsgt.return_value = pd.DataFrame()
        r = get_northbound_flow()
        _assert_ok(r)
        assert r["data"]["daily"] == []
        assert r["meta"]["empty_reason"] == "confirmed_absent"

    @patch("tushare.pro_api")
    def test_upstream_exception_is_error(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.moneyflow_hsgt.side_effect = RuntimeError("boom")
        _assert_error(get_northbound_flow(), "UPSTREAM_ERROR")
