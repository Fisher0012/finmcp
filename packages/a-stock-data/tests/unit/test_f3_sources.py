"""SPEC F3 任务2/任务3 源层测试

- B 方案换源: _fetch_announcements（巨潮）/ _fetch_limit_events（pro_bar 阈值判定）
- §3.4 反查: get_basic_info industry_l2/l3 / list_stock_concepts
- get_industry_operating_evidence 壳逻辑
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
from finmcp_a_stock_data.tools import concept as concept_tool
from finmcp_a_stock_data.tools import operating as operating_tool


class _NoCache:
    def make_key(self, *a: str) -> str:
        return "|".join(a)

    def get(self, key: str) -> None:
        return None

    def set(self, *a: Any, **k: Any) -> None:
        pass


def _make_source() -> Any:
    """构造 mock 掉 tushare 顶层依赖的 TushareSource"""
    with patch("finmcp_a_stock_data.data_sources.tushare_src.ts"):
        from finmcp_a_stock_data.data_sources.tushare_src import TushareSource

        src = TushareSource(token="test")
        src._pro = MagicMock()
        return src


# ── B 方案: _fetch_announcements → 巨潮 ──────────────────────


class TestCninfoAnnouncements:
    def test_success_field_schema_unchanged(self) -> None:
        src = _make_source()
        anns = [
            {"announcementTitle": "关于重大合同的公告", "announcementTime": 1756684800000},
            {"announcementTitle": "XX律师事务所核查意见", "announcementTime": 1756684800000},  # 过滤
        ]
        with patch("finmcp_a_stock_data.cninfo.query_announcements", return_value=anns):
            results = src._fetch_announcements("600519.SH", "20260801", "20260901")
        assert len(results) == 1
        assert set(results[0]) == {"date", "title", "source"}  # 返回字段不变
        assert results[0]["title"] == "关于重大合同的公告"
        assert len(results[0]["date"]) == 8 and results[0]["date"].isdigit()  # YYYYMMDD

    def test_failure_raises_recorded_as_cninfo_ann_attempt(self) -> None:
        src = _make_source()
        with patch(
            "finmcp_a_stock_data.cninfo.query_announcements",
            side_effect=RuntimeError("cninfo down"),
        ):
            result = src.get_stock_news("600519.SH", days=30)
        att = {a["source"]: a["outcome"] for a in result["_fetch_attempts"]}
        assert "cninfo_ann" in att  # attempts source 名改为 cninfo_ann
        assert att["cninfo_ann"] == "error"

    def test_empty_is_empty_outcome(self) -> None:
        src = _make_source()
        with patch("finmcp_a_stock_data.cninfo.query_announcements", return_value=[]):
            result = src.get_stock_news("600519.SH", days=30)
        att = {a["source"]: a["outcome"] for a in result["_fetch_attempts"]}
        assert att["cninfo_ann"] == "empty"


# ── B 方案: _fetch_limit_events → pro_bar 阈值判定 ────────────


class TestProBarLimitEvents:
    def _bar_df(self, pct_list: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "trade_date": [f"2026090{i}" for i in range(1, len(pct_list) + 1)],
                "close": [10.0] * len(pct_list),
                "pct_chg": pct_list,
            }
        )

    def test_main_board_10pct_threshold(self) -> None:
        src = _make_source()
        with patch("finmcp_a_stock_data.data_sources.tushare_src.ts") as mock_ts:
            mock_ts.pro_bar.return_value = self._bar_df([10.0, 9.99, 5.0, -9.9])
            events, ok, failed = src._fetch_limit_events("600519.SH", "20260901", "20260904")
        assert (ok, failed) == (1, 0)
        assert [e["limit_type"] for e in events] == ["涨停", "涨停", "跌停"]  # 9.99>=9.85 判定涨停
        assert events[0]["open_times"] is None and events[0]["first_time"] is None

    def test_kcb_20pct_threshold(self) -> None:
        src = _make_source()
        with patch("finmcp_a_stock_data.data_sources.tushare_src.ts") as mock_ts:
            mock_ts.pro_bar.return_value = self._bar_df([19.9, 10.0, -19.99])
            events, ok, failed = src._fetch_limit_events("688256.SH", "20260901", "20260903")
        assert [e["limit_type"] for e in events] == ["涨停", "跌停"]  # 10% 不达科创 20% 阈值

    def test_bj_30pct_threshold(self) -> None:
        src = _make_source()
        with patch("finmcp_a_stock_data.data_sources.tushare_src.ts") as mock_ts:
            mock_ts.pro_bar.return_value = self._bar_df([29.9, 19.9])
            events, ok, failed = src._fetch_limit_events("830001.BJ", "20260901", "20260902")
        assert len(events) == 1 and events[0]["limit_type"] == "涨停"

    def test_failure_returns_failed_batch(self) -> None:
        src = _make_source()
        with patch("finmcp_a_stock_data.data_sources.tushare_src.ts") as mock_ts:
            mock_ts.pro_bar.side_effect = RuntimeError("down")
            events, ok, failed = src._fetch_limit_events("600519.SH", "20260901", "20260904")
        assert (events, ok, failed) == ([], 0, 1)

    def test_market_signals_marks_fields_unavailable(self) -> None:
        src = _make_source()
        with patch("finmcp_a_stock_data.data_sources.tushare_src.ts") as mock_ts:
            mock_ts.pro_bar.return_value = self._bar_df([10.0])
            src._pro.top_list.return_value = pd.DataFrame()
            result = src.get_market_signals("600519.SH", days=3)
        assert result["fields_unavailable"] == ["open_times", "first_time"]
        att = {a["source"] for a in result["_fetch_attempts"]}
        assert "tushare_probar_limit" in att


# ── §3.4: industry_l2/l3 反查 ────────────────────────────────


class TestIndustryL2L3:
    """§3.4: index_member_all(ts_code=) 反查 L2/L3（2026-09-02 实调验证接口行为后重写）"""

    def _member_all_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "ts_code": ["600519.SH"],
                "l1_name": ["食品饮料"],
                "l2_name": ["白酒Ⅱ"],
                "l3_name": ["白酒Ⅲ"],
                "is_new": ["Y"],
            }
        )

    def test_l2_l3_resolved_from_index_member_all(self) -> None:
        src = _make_source()
        src._pro.index_member_all.return_value = self._member_all_df()
        l2, l3 = src._sw_industry_l2_l3("600519.SH")
        assert (l2, l3) == ("白酒Ⅱ", "白酒Ⅲ")
        src._pro.index_member_all.assert_called_once_with(ts_code="600519.SH")

    def test_empty_member_all_returns_blank(self) -> None:
        src = _make_source()
        src._pro.index_member_all.return_value = pd.DataFrame()
        assert src._sw_industry_l2_l3("600519.SH") == ("", "")

    def test_lookup_failure_marks_partial_fields(self) -> None:
        src = _make_source()
        src._pro.stock_basic.return_value = pd.DataFrame(
            {
                "ts_code": ["600519.SH"],
                "name": ["贵州茅台"],
                "fullname": [""],
                "enname": [""],
                "industry": ["白酒"],
                "area": [""],
                "list_date": [""],
                "market": [""],
                "exchange": [""],
                "is_hs": [""],
            }
        )
        src._pro.index_member_all.side_effect = RuntimeError("接口挂")
        src._pro.daily_basic.return_value = pd.DataFrame()
        info = src.get_basic_info("600519.SH")
        assert "industry_l2" in info["_partial_fields"]
        assert "industry_l3" in info["_partial_fields"]


class TestListStockConcepts:
    """§3.4 反查: 数据源未接通, 必须显式 NOT_SUPPORTED（2026-09-02 实调: concept_detail 已下线）"""

    def test_not_supported_explicit(self) -> None:
        resp = concept_tool.list_stock_concepts("600519.SH")
        assert resp["ok"] is False
        assert resp["error"]["code"] == "NOT_SUPPORTED"
        assert "list_concept_stocks" in resp["error"]["hint"]

    def test_invalid_param_still_validated(self) -> None:
        resp = concept_tool.list_stock_concepts("")
        assert resp["ok"] is False
        assert resp["error"]["code"] == "INVALID_PARAM"


def _fin_indicator_ok(code: str, indicators: Any = None, years: int = 3) -> dict[str, Any]:
    """mock get_financial_indicator 封套: 两家公司同一年报期, 毛利率 30/50 → 中位数 40.0"""
    gm = {"600519.SH": 50.0, "000858.SZ": 30.0}.get(code, 40.0)
    return {
        "ok": True,
        "data": [
            {"report_period": "2025-12-31", "gross_margin": gm, "roe": 20.0},
        ],
        "meta": {"source": "tushare"},
    }


class TestIndustryOperatingEvidence:
    def test_success_aggregates_sample(self) -> None:
        overview = {
            "ok": True,
            "data": {
                "industry": "白酒Ⅱ",
                "trade_date": "20260901",
                "total_count": 20,
                "summary": {"total_market_cap_yi": 30000.0},
                "stocks": [
                    {"stock_code": "600519.SH", "name": "贵州茅台", "market_cap_yi": 20000.0},
                    {"stock_code": "000858.SZ", "name": "五粮液", "market_cap_yi": 5000.0},
                ],
            },
            "meta": {"source": "tushare", "cache_hit": False},
        }
        with (
            patch.object(operating_tool, "get_industry_overview", return_value=overview),
            patch.object(operating_tool, "get_financial_indicator", side_effect=_fin_indicator_ok),
            patch.object(
                operating_tool,
                "get_financial_report_summary",
                side_effect=lambda code, period: {"ok": True, "data": {"revenue": 100.0}},
            ),
        ):
            r = operating_tool.get_industry_operating_evidence("白酒", level=2, sample_limit=2)
        assert r["ok"] is True
        assert r["data"]["status"] == "verified_sample"
        assert r["data"]["report_period"] == "2025-12-31"
        assert r["data"]["selection"]["common_period_sample_count"] == 2
        assert r["data"]["metrics"]["gross_margin"]["median"] == 40.0

    def test_overview_failure_passthrough(self) -> None:
        failed = {"ok": False, "error": {"code": "UPSTREAM_ERROR", "message": "x"}, "meta": {}}
        with patch.object(operating_tool, "get_industry_overview", return_value=failed):
            r = operating_tool.get_industry_operating_evidence("白酒")
        assert r is failed  # 行业全景失败 → 透传其封套

    def test_empty_param(self) -> None:
        r = operating_tool.get_industry_operating_evidence("")
        assert r["ok"] is False
        assert r["error"]["code"] == "INVALID_PARAM"
