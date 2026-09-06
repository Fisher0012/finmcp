"""SPEC F3 下沉工具单元测试

每个下沉工具 ≥2 个 mock 用例（成功 data schema + 失败封套）:
- tushare 直调工具: patch tushare.pro_api
- akshare 工具: CI 环境无 akshare → NOT_SUPPORTED 路径实测; 成功路径注入假模块
- 东财实时工具: patch _get_json
- 巨潮/pdfplumber 工具: NOT_SUPPORTED 实测 + patch 内部辅助
"""

import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
from finmcp_a_stock_data.tools import realtime_em
from finmcp_a_stock_data.tools.forecast import get_earnings_forecast
from finmcp_a_stock_data.tools.holder import get_major_shareholder_change, get_pledge_status
from finmcp_a_stock_data.tools.investor import get_investor_qa
from finmcp_a_stock_data.tools.profile import get_annual_report_mdna, get_company_profile
from finmcp_a_stock_data.tools.ratings import get_broker_ratings, get_buyback


def _assert_ok(result: dict[str, Any]) -> None:
    assert result["ok"] is True
    assert "data" in result
    assert "meta" in result
    assert "contract_version" in result["meta"]


def _assert_error(result: dict[str, Any], code: str) -> None:
    assert result["ok"] is False
    assert result["error"]["code"] == code


class _FakeAkshare(types.ModuleType):
    """假 akshare 模块（CI 无 akshare, 成功路径用它注入 sys.modules）"""

    def __init__(self) -> None:
        super().__init__("akshare")
        self.stock_irm_cninfo = MagicMock()
        self.stock_sns_sseinfo = MagicMock()
        self.stock_research_report_em = MagicMock()
        self.stock_repurchase_em = MagicMock()


def _with_fake_akshare(fake: _FakeAkshare) -> Any:
    return patch.dict(sys.modules, {"akshare": fake})


# ── get_company_profile ──────────────────────────────────────


class TestCompanyProfile:
    @patch("tushare.pro_api")
    def test_success_schema(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.stock_company.return_value = pd.DataFrame(
            {
                "ts_code": ["600519.SH"],
                "main_business": ["酒"],
                "business_scope": ["酒类生产销售"],
                "introduction": ["x" * 800],
            }
        )
        r = get_company_profile("600519.SH")
        _assert_ok(r)
        assert r["data"]["stock_code"] == "600519.SH"
        assert r["data"]["main_business"] == "酒"
        assert len(r["data"]["introduction"]) == 500  # 截断
        assert set(r["data"]) == {"stock_code", "main_business", "business_scope", "introduction"}

    @patch("tushare.pro_api")
    def test_empty_is_data_not_found(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.stock_company.return_value = pd.DataFrame()
        r = get_company_profile("999999.SH")
        _assert_error(r, "DATA_NOT_FOUND")

    @patch("tushare.pro_api")
    def test_upstream_exception_is_error(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.stock_company.side_effect = RuntimeError("timeout")
        r = get_company_profile("600519.SH")
        _assert_error(r, "UPSTREAM_ERROR")

    def test_empty_param(self) -> None:
        _assert_error(get_company_profile(""), "INVALID_PARAM")


# ── get_earnings_forecast ────────────────────────────────────


class TestEarningsForecast:
    @patch("tushare.pro_api")
    def test_success_unit_conversion_wan_to_yi(self, mock_pro_api: MagicMock) -> None:
        """万元→亿元换算 /10_000 保持不变（docs/EARNINGS_FORECAST_UNIT_VERIFICATION.md）"""
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.forecast.return_value = pd.DataFrame(
            {
                "ann_date": ["20260711"],
                "end_date": ["20260630"],
                "type": ["预亏"],
                "p_change_min": [-120.0],
                "p_change_max": [-100.0],
                "net_profit_min": [-670000.0],  # 万元
                "net_profit_max": [-570000.0],
                "change_reason": ["猪价下行"],
                "summary": ["亏损:570,000万元至670,000万元"],
            }
        )
        r = get_earnings_forecast("002714.SZ")
        _assert_ok(r)
        f = r["data"]["forecasts"][0]
        assert f["net_profit_min_yi"] == -67.0
        assert f["net_profit_max_yi"] == -57.0

    @patch("tushare.pro_api")
    def test_empty_is_confirmed_absent(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.forecast.return_value = pd.DataFrame()
        r = get_earnings_forecast("600519.SH")
        _assert_ok(r)
        assert r["data"]["forecasts"] == []
        assert r["meta"]["empty_reason"] == "confirmed_absent"

    @patch("tushare.pro_api")
    def test_upstream_exception_is_error(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.forecast.side_effect = RuntimeError("boom")
        _assert_error(get_earnings_forecast("600519.SH"), "UPSTREAM_ERROR")


# ── get_investor_qa ──────────────────────────────────────────


class TestInvestorQa:
    def test_not_supported_without_akshare(self) -> None:
        """akshare 缺失 → NOT_SUPPORTED。batch-6 T17: 原断言 assert not in sys.modules
        是环境假设(已装环境必失败), 改为 mock 依赖缺失(sys.modules 置 None 使 import 抛 ImportError)"""
        with patch.dict(sys.modules, {"akshare": None}):
            _assert_error(get_investor_qa("000001.SZ"), "NOT_SUPPORTED")

    def test_sz_success_schema(self) -> None:
        fake = _FakeAkshare()
        fake.stock_irm_cninfo.return_value = pd.DataFrame(
            {"提问内容": ["订单情况?"], "回答内容": ["经营正常"], "提问时间": ["2026-08-01"]}
        )
        with _with_fake_akshare(fake):
            r = get_investor_qa("000001.SZ")
        _assert_ok(r)
        assert r["data"]["qa"][0]["提问内容"] == "订单情况?"

    def test_sse_failure_not_masked_as_ok_note_v1(self) -> None:
        """上证 e 互动失败: 禁止 ok:true+note 伪装, v1 必须 empty_reason=unknown"""
        fake = _FakeAkshare()
        fake.stock_sns_sseinfo.side_effect = RuntimeError("sse down")
        with _with_fake_akshare(fake), patch.dict("os.environ", {"FINMCP_CONTRACT": "v1"}):
            r = get_investor_qa("600519.SH")
        assert r["ok"] is True
        assert r["data"]["qa"] == []
        assert r["meta"]["empty_reason"] == "unknown"
        assert r["meta"]["attempts"][0]["outcome"] == "error"

    def test_sse_failure_v2_is_error(self) -> None:
        fake = _FakeAkshare()
        fake.stock_sns_sseinfo.side_effect = RuntimeError("sse down")
        with _with_fake_akshare(fake), patch.dict("os.environ", {"FINMCP_CONTRACT": "v2"}):
            r = get_investor_qa("600519.SH")
        _assert_error(r, "UPSTREAM_ERROR")

    def test_empty_is_confirmed_absent(self) -> None:
        fake = _FakeAkshare()
        fake.stock_irm_cninfo.return_value = pd.DataFrame()
        with _with_fake_akshare(fake):
            r = get_investor_qa("000001.SZ")
        _assert_ok(r)
        assert r["meta"]["empty_reason"] == "confirmed_absent"


# ── get_major_shareholder_change / get_pledge_status ─────────


class TestHolder:
    @patch("tushare.pro_api")
    def test_holdertrade_success_schema(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.stk_holdertrade.return_value = pd.DataFrame(
            {
                "ann_date": ["20260810"],
                "holder_name": ["某大股东"],
                "in_de": ["DE"],
                "change_vol": [2e8],
                "change_ratio": [1.5],
                "after_share": [1e9],
                "after_ratio": [10.0],
                "avg_price": [12.3],
            }
        )
        r = get_major_shareholder_change("600519.SH")
        _assert_ok(r)
        c = r["data"]["changes"][0]
        assert c["direction"] == "减持"
        assert c["change_vol_yi"] == 2.0
        assert r["data"]["net_change_yi_total"] == -2.0

    @patch("tushare.pro_api")
    def test_holdertrade_empty_confirmed_absent(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.stk_holdertrade.return_value = pd.DataFrame()
        r = get_major_shareholder_change("600519.SH")
        _assert_ok(r)
        assert r["data"]["changes"] == []
        assert r["meta"]["empty_reason"] == "confirmed_absent"

    @patch("tushare.pro_api")
    def test_pledge_success_schema(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.pledge_stat.return_value = pd.DataFrame(
            {
                "end_date": ["20260630"],
                "pledge_count": [3],
                "unrest_pledge": [1.2e8],
                "rest_pledge": [0.5e8],
                "total_share": [10e8],
                "pledge_ratio": [17.0],
            }
        )
        r = get_pledge_status("600519.SH")
        _assert_ok(r)
        assert r["data"]["pledge_ratio_pct"] == 17.0
        assert r["data"]["unrest_pledge_yi"] == 1.2

    @patch("tushare.pro_api")
    def test_pledge_upstream_error(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.pledge_stat.side_effect = RuntimeError("boom")
        _assert_error(get_pledge_status("600519.SH"), "UPSTREAM_ERROR")


# ── get_broker_ratings / get_buyback ─────────────────────────


class TestRatings:
    def test_not_supported_without_akshare(self) -> None:
        with patch.dict(sys.modules, {"akshare": None}):  # T17: mock 依赖缺失替代环境假设
            _assert_error(get_broker_ratings("600519.SH"), "NOT_SUPPORTED")
            _assert_error(get_buyback("600519.SH"), "NOT_SUPPORTED")

    def test_ratings_success_has_third_party_opinion_flag(self) -> None:
        fake = _FakeAkshare()
        fake.stock_research_report_em.return_value = pd.DataFrame(
            {
                "报告名称": ["深度报告"],
                "东财评级": ["买入"],
                "机构": ["某券商"],
                "目标价": ["2000"],
                "日期": ["2026-08-01"],
            }
        )
        with _with_fake_akshare(fake):
            r = get_broker_ratings("600519.SH")
        _assert_ok(r)
        assert r["data"]["third_party_opinion"] is True  # SPEC §1: 观点字段透传+标注
        assert r["data"]["reports"][0]["目标价"] == "2000"  # 目标价原样透传, 过滤归产品层

    def test_ratings_empty_confirmed_absent_keeps_flag(self) -> None:
        fake = _FakeAkshare()
        fake.stock_research_report_em.return_value = pd.DataFrame()
        with _with_fake_akshare(fake):
            r = get_broker_ratings("600519.SH")
        _assert_ok(r)
        assert r["data"]["third_party_opinion"] is True
        assert r["meta"]["empty_reason"] == "confirmed_absent"

    def test_buyback_filters_by_code(self) -> None:
        fake = _FakeAkshare()
        fake.stock_repurchase_em.return_value = pd.DataFrame(
            {
                "股票代码": ["600519", "000001"],
                "最新公告日期": ["2026-08-01", "2026-08-02"],
                "已回购金额": ["1亿", "2亿"],
                "实施进度": ["实施中", "完成"],
            }
        )
        with _with_fake_akshare(fake):
            r = get_buyback("600519.SH")
        _assert_ok(r)
        assert len(r["data"]["buybacks"]) == 1
        assert r["data"]["buybacks"][0]["已回购金额"] == "1亿"

    def test_buyback_no_match_confirmed_absent(self) -> None:
        fake = _FakeAkshare()
        fake.stock_repurchase_em.return_value = pd.DataFrame({"股票代码": ["000001"], "最新公告日期": ["2026-08-02"]})
        with _with_fake_akshare(fake):
            r = get_buyback("600519.SH")
        _assert_ok(r)
        assert r["data"]["buybacks"] == []
        assert r["meta"]["empty_reason"] == "confirmed_absent"

    def test_buyback_upstream_error(self) -> None:
        fake = _FakeAkshare()
        fake.stock_repurchase_em.side_effect = RuntimeError("boom")
        with _with_fake_akshare(fake):
            _assert_error(get_buyback("600519.SH"), "UPSTREAM_ERROR")


# ── get_annual_report_mdna ───────────────────────────────────


class TestAnnualReportMdna:
    def test_not_supported_without_pdfplumber(self) -> None:
        """pdfplumber 缺失 → NOT_SUPPORTED。T17: mock 依赖缺失替代环境假设"""
        with patch.dict(sys.modules, {"pdfplumber": None}):
            _assert_error(get_annual_report_mdna("600519.SH"), "NOT_SUPPORTED")

    def _with_pdfplumber_stub(self) -> Any:
        return patch.dict(sys.modules, {"pdfplumber": types.ModuleType("pdfplumber")})

    def test_success_schema_and_cache_write(self) -> None:
        cache = MagicMock()
        cache.get.return_value = None
        cache.make_key = lambda *a: ":".join(a)
        with (
            self._with_pdfplumber_stub(),
            patch("finmcp_a_stock_data.tools.profile._cache", cache),
            patch(
                "finmcp_a_stock_data.tools.profile.cninfo.latest_annual_report",
                return_value={"title": "2025年年度报告", "url": "http://x/a.pdf", "date_ms": 1745000000000},
            ),
            patch("finmcp_a_stock_data.tools.profile.cninfo.download", return_value=b"%PDF"),
            patch("finmcp_a_stock_data.tools.profile._extract_mdna_excerpt", return_value="战略段落"),
        ):
            r = get_annual_report_mdna("600519.SH")
        _assert_ok(r)
        assert r["data"]["report_year"] == "2025"
        assert r["data"]["mdna_excerpt"] == "战略段落"
        assert r["data"]["from_cache"] is False
        cache.set.assert_called_once()
        assert cache.set.call_args.kwargs.get("ttl_category") == "quarterly"

    def test_cache_hit(self) -> None:
        cache = MagicMock()
        cache.get.return_value = {"report_year": "2025", "report_date": "2026-04-01", "mdna_excerpt": "x"}
        cache.make_key = lambda *a: ":".join(a)
        with self._with_pdfplumber_stub(), patch("finmcp_a_stock_data.tools.profile._cache", cache):
            r = get_annual_report_mdna("600519.SH")
        _assert_ok(r)
        assert r["data"]["from_cache"] is True
        assert r["meta"]["cache_hit"] is True

    def test_cninfo_not_found(self) -> None:
        cache = MagicMock()
        cache.get.return_value = None
        cache.make_key = lambda *a: ":".join(a)
        with (
            self._with_pdfplumber_stub(),
            patch("finmcp_a_stock_data.tools.profile._cache", cache),
            patch("finmcp_a_stock_data.tools.profile.cninfo.latest_annual_report", return_value=None),
        ):
            _assert_error(get_annual_report_mdna("600519.SH"), "DATA_NOT_FOUND")

    def test_upstream_failure(self) -> None:
        cache = MagicMock()
        cache.get.return_value = None
        cache.make_key = lambda *a: ":".join(a)
        with (
            self._with_pdfplumber_stub(),
            patch("finmcp_a_stock_data.tools.profile._cache", cache),
            patch(
                "finmcp_a_stock_data.tools.profile.cninfo.latest_annual_report",
                side_effect=RuntimeError("cninfo down"),
            ),
        ):
            _assert_error(get_annual_report_mdna("600519.SH"), "UPSTREAM_ERROR")


# ── get_money_flow ───────────────────────────────────────────


def _em_ulist_moneyflow_payload() -> dict[str, Any]:
    return {
        "data": {
            "diff": [
                {
                    "f14": "贵州茅台",
                    "f2": 1500.0,
                    "f3": 1.2,
                    "f18": 1482.0,
                    "f62": 2.5e8,
                    "f184": 12.0,
                    "f66": 1.5e8,
                    "f69": 7.0,
                    "f72": 1.0e8,
                    "f75": 5.0,
                    "f78": -0.5e8,
                    "f81": -2.0,
                    "f84": -0.6e8,
                    "f87": -3.0,
                    "f9": 30.0,
                    "f115": 28.0,
                    "f114": 27.0,
                    "f23": 8.0,
                    "f100": "白酒",
                    "f124": 1750000000,
                }
            ]
        }
    }


class TestMoneyFlow:
    def test_east_realtime_success(self) -> None:
        def fake_get_json(url: str, tries_per_host: int = 2) -> dict[str, Any]:
            if "ulist.np" in url:
                return _em_ulist_moneyflow_payload()
            # daykline 历史序列
            return {
                "data": {
                    "klines": [
                        "2026-08-28,1e8,0,0,5e7,5e7,10.0,0,0,5.0,5.0,1490.0,0.5",
                        "2026-08-29,2e8,0,0,1e8,1e8,11.0,0,0,5.5,5.5,1495.0,0.3",
                        "2026-09-01,1.5e8,0,0,8e7,7e7,9.0,0,0,4.0,5.0,1498.0,0.2",
                    ]
                }
            }

        with patch.object(realtime_em, "_get_json", side_effect=fake_get_json):
            r = realtime_em.get_money_flow("600519.SH", days=5)
        _assert_ok(r)
        assert r["data"]["today_realtime"]["main_net_yi"] == 2.5
        assert r["data"]["today_realtime"]["name"] == "贵州茅台"
        assert len(r["data"]["daily_series"]) >= 3
        assert r["meta"]["attempts"][0] == {"source": "eastmoney_realtime", "outcome": "ok"}

    @patch("tushare.pro_api")
    def test_east_fail_falls_back_to_tushare(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.moneyflow.return_value = pd.DataFrame(
            {
                "trade_date": ["20260901"],
                "net_mf_amount": [25000.0],  # 万元
                "buy_lg_amount": [80000.0],
                "sell_lg_amount": [60000.0],
                "buy_elg_amount": [50000.0],
                "sell_elg_amount": [45000.0],
            }
        )
        with patch.object(realtime_em, "_get_json", side_effect=RuntimeError("push2 风控")):
            r = realtime_em.get_money_flow("600519.SH", days=5)
        _assert_ok(r)
        assert r["data"]["flows_recent"][0]["net_main_flow_yi"] == 2.5
        outcomes = {a["source"]: a["outcome"] for a in r["meta"]["attempts"]}
        assert outcomes == {"eastmoney_realtime": "error", "tushare_moneyflow": "ok"}

    @patch("tushare.pro_api")
    def test_both_fail_is_upstream_error(self, mock_pro_api: MagicMock) -> None:
        pro = MagicMock()
        mock_pro_api.return_value = pro
        pro.moneyflow.side_effect = RuntimeError("tushare down")
        with patch.object(realtime_em, "_get_json", side_effect=RuntimeError("push2 down")):
            r = realtime_em.get_money_flow("600519.SH")
        _assert_error(r, "UPSTREAM_ERROR")
        assert len(r["meta"]["attempts"]) == 2

    def test_invalid_code(self) -> None:
        _assert_error(realtime_em.get_money_flow("abc"), "INVALID_PARAM")


# ── get_market_snapshot ──────────────────────────────────────


class TestMarketSnapshot:
    def test_success_schema(self) -> None:
        payload = {
            "data": {
                "diff": [
                    {
                        "f12": "000001",
                        "f14": "上证指数",
                        "f2": 3800.0,
                        "f3": 0.5,
                        "f6": 5000e8,
                        "f104": 1200,
                        "f105": 800,
                        "f106": 100,
                        "f124": 1750000000,
                    },
                    {
                        "f12": "399106",
                        "f14": "深证综指",
                        "f2": 2300.0,
                        "f3": 0.8,
                        "f6": 6000e8,
                        "f104": 1500,
                        "f105": 900,
                        "f106": 120,
                    },
                    {"f12": "399001", "f14": "深证成指", "f2": 12000.0, "f3": 0.7},
                    {"f12": "399006", "f14": "创业板指", "f2": 2500.0, "f3": 1.0},
                    {"f12": "000300", "f14": "沪深300", "f2": 4400.0, "f3": 0.4},
                ]
            }
        }
        with patch.object(realtime_em, "_get_json", return_value=payload):
            r = realtime_em.get_market_snapshot()
        _assert_ok(r)
        assert r["data"]["market_breadth"] == {"up": 2700, "down": 1700, "flat": 220}
        assert r["data"]["total_amount_yi"] == 11000.0
        assert len(r["data"]["indices"]) == 4

    def test_upstream_failure_is_error(self) -> None:
        with patch.object(realtime_em, "_get_json", side_effect=RuntimeError("down")):
            _assert_error(realtime_em.get_market_snapshot(), "UPSTREAM_ERROR")

    def test_empty_diff_is_error(self) -> None:
        with patch.object(realtime_em, "_get_json", return_value={"data": None}):
            _assert_error(realtime_em.get_market_snapshot(), "UPSTREAM_ERROR")


# ── get_sector_ranking ───────────────────────────────────────


def _boards_payload() -> dict[str, Any]:
    return {
        "data": {
            "diff": [
                {"f14": "银行", "f12": "BK0475", "f3": 1.0, "f62": 5e8, "f184": 8.0},
                {"f14": "半导体", "f12": "BK1036", "f3": -0.5, "f62": -3e8, "f184": -4.0},
                {"f14": "白酒", "f12": "BK0896", "f3": 0.2, "f62": 1e8, "f184": 2.0},
            ]
        }
    }


class TestSectorRanking:
    def test_rank_success(self) -> None:
        with patch.object(realtime_em, "_get_json", return_value=_boards_payload()):
            r = realtime_em.get_sector_ranking(top_n=2, board_type="industry")
        _assert_ok(r)
        assert r["data"]["top_inflow"][0]["board"] == "银行"
        assert r["data"]["top_outflow"][0]["board"] == "半导体"
        assert r["data"]["board_type"] == "industry"

    def test_board_names_query(self) -> None:
        with patch.object(realtime_em, "_get_json", return_value=_boards_payload()):
            r = realtime_em.get_sector_ranking(board_names="银行,不存在的板块")
        _assert_ok(r)
        boards = {b["board"]: b for b in r["data"]["boards"]}
        assert "银行" in boards
        assert boards["不存在的板块"]["note"] == "未找到同名板块"

    def test_invalid_board_type(self) -> None:
        _assert_error(realtime_em.get_sector_ranking(board_type="xxx"), "INVALID_PARAM")

    def test_premarket_no_funding_is_explicit_error(self) -> None:
        """盘前 f62 全空: 显式报错而非混入 None 排序"""
        payload = {"data": {"diff": [{"f14": "银行", "f12": "BK0475", "f3": None, "f62": "-", "f184": None}]}}
        with patch.object(realtime_em, "_get_json", return_value=payload):
            r = realtime_em.get_sector_ranking()
        _assert_error(r, "DATA_NOT_FOUND")

    def test_upstream_failure(self) -> None:
        with patch.object(realtime_em, "_get_json", side_effect=RuntimeError("down")):
            _assert_error(realtime_em.get_sector_ranking(), "UPSTREAM_ERROR")
