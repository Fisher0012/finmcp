"""SPEC F1 三态封套验收测试（§2.3）

对每个静默降级改造点做 mock 验证:
- 模拟上游异常 → v2 模式断言 ok:false；v1 模式断言 ok:true + empty_reason=unknown（不得伪装 confirmed_absent）
- 模拟上游 200 + 空结果 → 断言 ok:true + empty_reason=confirmed_absent
任一用例把异常判成 confirmed_absent = 验收失败。
"""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from finmcp_a_stock_data.tools import concept as concept_tool
from finmcp_a_stock_data.tools import industry as industry_tool
from finmcp_a_stock_data.tools import news as news_tool
from finmcp_a_stock_data.tools import quote as quote_tool


class _NoCache:
    def make_key(self, *a):
        return "|".join(str(x) for x in a)

    def get(self, key):
        return None

    def set(self, *a, **k):
        pass


def _v2():
    return patch.dict(os.environ, {"FINMCP_CONTRACT": "v2"})


def _v1():
    return patch.dict(os.environ, {"FINMCP_CONTRACT": "v1"})


class NewsContractTests(unittest.TestCase):
    """get_stock_news: 双源全挂 / 双源确认空 / 单源挂"""

    def _fake_source(self, attempts, announcements=None, market_news=None):
        return SimpleNamespace(
            name="tushare",
            get_stock_news=lambda code, days: {
                "stock_code": code,
                "period": "x",
                "announcements": announcements or [],
                "market_news": market_news or [],
                "_fetch_attempts": attempts,
            },
        )

    def test_all_sources_failed_v2_returns_ok_false(self):
        fake = self._fake_source(
            [
                {"source": "cninfo_ann", "outcome": "error", "detail": "no perm"},
                {"source": "eastmoney_ann", "outcome": "error", "detail": "timeout"},
            ]
        )
        with _v2(), patch.object(news_tool, "_get_source", return_value=fake):
            resp = news_tool.get_stock_news("600519.SH")
        self.assertFalse(resp["ok"])
        self.assertEqual("UPSTREAM_ERROR", resp["error"]["code"])
        self.assertEqual(2, len(resp["meta"]["attempts"]))

    def test_all_sources_failed_v1_is_unknown_not_absent(self):
        fake = self._fake_source(
            [
                {"source": "cninfo_ann", "outcome": "error"},
                {"source": "eastmoney_ann", "outcome": "error"},
            ]
        )
        with _v1(), patch.object(news_tool, "_get_source", return_value=fake):
            resp = news_tool.get_stock_news("600519.SH")
        self.assertTrue(resp["ok"])
        self.assertEqual("unknown", resp["meta"]["empty_reason"])
        self.assertEqual("1.1", resp["meta"]["contract_version"])

    def test_confirmed_empty_both_sources(self):
        fake = self._fake_source(
            [
                {"source": "cninfo_ann", "outcome": "empty"},
                {"source": "eastmoney_ann", "outcome": "empty"},
            ]
        )
        with _v2(), patch.object(news_tool, "_get_source", return_value=fake):
            resp = news_tool.get_stock_news("600519.SH")
        self.assertTrue(resp["ok"])
        self.assertEqual("confirmed_absent", resp["meta"]["empty_reason"])
        self.assertEqual("2.0", resp["meta"]["contract_version"])

    def test_partial_failure_with_data_keeps_ok_and_attempts(self):
        fake = self._fake_source(
            [
                {"source": "cninfo_ann", "outcome": "error"},
                {"source": "eastmoney_ann", "outcome": "ok"},
            ],
            market_news=[{"title": "t"}],
        )
        with _v2(), patch.object(news_tool, "_get_source", return_value=fake):
            resp = news_tool.get_stock_news("600519.SH")
        self.assertTrue(resp["ok"])
        self.assertIsNone(resp["meta"]["empty_reason"])
        outcomes = {a["source"]: a["outcome"] for a in resp["meta"]["attempts"]}
        self.assertEqual("error", outcomes["cninfo_ann"])


class SignalsContractTests(unittest.TestCase):
    """get_market_signals: API 全挂不得伪装成"无异动" """

    def _fake_source(self, attempts, limit_events=None):
        return SimpleNamespace(
            name="tushare",
            get_market_signals=lambda code, days: {
                "stock_code": code,
                "period": "x",
                "limit_events": limit_events or [],
                "toplist_events": [],
                "has_signals": bool(limit_events),
                "_fetch_attempts": attempts,
            },
        )

    def test_all_failed_v2_ok_false(self):
        fake = self._fake_source(
            [
                {"source": "tushare_probar_limit", "outcome": "error", "ok_days": 0, "failed_days": 10},
                {"source": "tushare_top_list", "outcome": "error", "ok_days": 0, "failed_days": 10},
            ]
        )
        with _v2(), patch.object(news_tool, "_get_source", return_value=fake):
            resp = news_tool.get_market_signals("600519.SH")
        self.assertFalse(resp["ok"])
        self.assertEqual("UPSTREAM_ERROR", resp["error"]["code"])

    def test_all_failed_v1_has_signals_none_and_unknown(self):
        fake = self._fake_source(
            [
                {"source": "tushare_probar_limit", "outcome": "error", "ok_days": 0, "failed_days": 10},
                {"source": "tushare_top_list", "outcome": "error", "ok_days": 0, "failed_days": 10},
            ]
        )
        with _v1(), patch.object(news_tool, "_get_source", return_value=fake):
            resp = news_tool.get_market_signals("600519.SH")
        self.assertTrue(resp["ok"])
        # 全挂时 has_signals 必须是 None（未知），不得是 False（无异动）
        self.assertIsNone(resp["data"]["has_signals"])
        self.assertEqual("unknown", resp["meta"]["empty_reason"])

    def test_success_no_records_is_confirmed_absent(self):
        fake = self._fake_source(
            [
                {"source": "tushare_probar_limit", "outcome": "empty", "ok_days": 10, "failed_days": 0},
                {"source": "tushare_top_list", "outcome": "empty", "ok_days": 10, "failed_days": 0},
            ]
        )
        with _v2(), patch.object(news_tool, "_get_source", return_value=fake):
            resp = news_tool.get_market_signals("600519.SH")
        self.assertTrue(resp["ok"])
        self.assertIs(False, resp["data"]["has_signals"])
        self.assertEqual("confirmed_absent", resp["meta"]["empty_reason"])


class ConceptContractTests(unittest.TestCase):
    """list_concept_stocks: 三级瀑布逐级留痕, 全挂 v2 → ok:false"""

    def _run(self, ths_side, tushare_pro, search_side):
        fake_source = SimpleNamespace(
            name="tushare",
            _pro=tushare_pro,
            search_stocks=search_side,
        )
        with (
            patch.object(concept_tool, "_get_source", return_value=fake_source),
            patch.object(concept_tool, "_cache", _NoCache()),
            patch.object(concept_tool, "_ths_search_concept", side_effect=ths_side),
        ):
            return concept_tool.list_concept_stocks("算力租赁", limit=10)

    def test_three_level_all_failed_v2_ok_false_with_attempts(self):
        def boom(*a, **k):
            raise RuntimeError("network down")

        pro = SimpleNamespace(concept=boom, concept_detail=boom)
        with _v2():
            resp = self._run(boom, pro, boom)
        self.assertFalse(resp["ok"])
        self.assertEqual("UPSTREAM_ERROR", resp["error"]["code"])
        sources = [a["source"] for a in resp["meta"]["attempts"]]
        self.assertEqual(["ths_concept", "tushare_concept", "keyword_search"], sources)
        self.assertTrue(all(a["outcome"] == "error" for a in resp["meta"]["attempts"]))

    def test_three_level_all_failed_v1_unknown(self):
        def boom(*a, **k):
            raise RuntimeError("network down")

        pro = SimpleNamespace(concept=boom, concept_detail=boom)
        with _v1():
            resp = self._run(boom, pro, boom)
        self.assertTrue(resp["ok"])
        self.assertEqual([], resp["data"])
        self.assertEqual("unknown", resp["meta"]["empty_reason"])
        self.assertEqual(3, len(resp["meta"]["attempts"]))

    def test_no_match_but_sources_healthy_is_confirmed_absent(self):
        class _FakeStr:
            def contains(self, *a, **k):
                return "mask"

        class _FakeNameCol:
            str = _FakeStr()

        class _FakeMatches:
            empty = True

            def iterrows(self):
                return iter([])

        class _FakeConceptDF:
            def __getitem__(self, key):
                return _FakeNameCol() if key == "name" else _FakeMatches()

        pro = SimpleNamespace(concept=lambda src: _FakeConceptDF(), concept_detail=lambda **_k: None)
        with _v2():
            resp = self._run(lambda *a, **k: [], pro, lambda *a, **k: [])
        self.assertTrue(resp["ok"])
        self.assertEqual([], resp["data"])
        self.assertEqual("confirmed_absent", resp["meta"]["empty_reason"])


class QuoteContractTests(unittest.TestCase):
    """get_latest_quote: 估值富化失败必须 partial_fields 显式标注"""

    def test_sina_path_missing_valuation_marked_partial(self):
        fake_source = SimpleNamespace(name="tushare", _pro=SimpleNamespace())

        def fail_daily_basic(**k):
            raise RuntimeError("upstream down")

        fake_source._pro.daily_basic = fail_daily_basic
        with (
            patch.object(quote_tool, "_cache", _NoCache()),
            patch.object(quote_tool, "_get_source", return_value=fake_source),
            patch.object(
                quote_tool,
                "fetch_sina_realtime",
                return_value={"stock_code": "600519.SH", "current_price": 1500.0},
            ),
        ):
            resp = quote_tool.get_latest_quote("600519.SH")
        self.assertTrue(resp["ok"])
        self.assertEqual(["pe_ttm", "pb", "market_cap_yi"], resp["meta"]["partial_fields"])

    def test_fallback_path_propagates_partial_fields(self):
        fake_source = SimpleNamespace(
            name="tushare",
            get_latest_quote=lambda code: {
                "stock_code": code,
                "name": "",
                "current_price": 10.0,
                "_partial_fields": ["pe_ttm", "pb", "market_cap_yi", "name"],
            },
        )
        with (
            patch.object(quote_tool, "_cache", _NoCache()),
            patch.object(quote_tool, "_get_source", return_value=fake_source),
            patch.object(quote_tool, "fetch_sina_realtime", return_value=None),
        ):
            resp = quote_tool.get_latest_quote("600519.SH")
        self.assertTrue(resp["ok"])
        self.assertIn("name", resp["meta"]["partial_fields"])
        self.assertNotIn("_partial_fields", resp["data"])


class IndustryContractTests(unittest.TestCase):
    """list_industry_constituents: 200+空表 = confirmed_absent（异常路径 source 层已 raise）"""

    def test_empty_members_is_confirmed_absent(self):
        fake_source = SimpleNamespace(
            name="tushare",
            get_industry_constituents=lambda code, name, level: [],
        )
        with (
            patch.object(industry_tool, "_cache", _NoCache()),
            patch.object(industry_tool, "_get_source", return_value=fake_source),
        ):
            resp = industry_tool.list_industry_constituents(industry_name="白酒")
        self.assertTrue(resp["ok"])
        self.assertEqual("confirmed_absent", resp["meta"]["empty_reason"])

    def test_upstream_error_is_ok_false_not_empty(self):
        from finmcp_common.errors import UpstreamError

        def boom(code, name, level):
            raise UpstreamError("tushare index_member 调用失败")

        fake_source = SimpleNamespace(name="tushare", get_industry_constituents=boom)
        with (
            patch.object(industry_tool, "_cache", _NoCache()),
            patch.object(industry_tool, "_get_source", return_value=fake_source),
        ):
            resp = industry_tool.list_industry_constituents(industry_name="白酒")
        self.assertFalse(resp["ok"])
        self.assertEqual("UPSTREAM_ERROR", resp["error"]["code"])


class ContractModeTests(unittest.TestCase):
    def test_default_mode_is_v1(self):
        from finmcp_common.responses import contract_mode

        env = {k: v for k, v in os.environ.items() if k != "FINMCP_CONTRACT"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual("v1", contract_mode())

    def test_ok_response_always_carries_contract_meta(self):
        from finmcp_common.responses import ok_response

        resp = ok_response(data=[1], source="tushare")
        self.assertIn("contract_version", resp["meta"])
        self.assertIn("empty_reason", resp["meta"])
        self.assertIsNone(resp["meta"]["empty_reason"])


if __name__ == "__main__":
    unittest.main()
