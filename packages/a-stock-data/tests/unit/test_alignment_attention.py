"""F5: get_event_market_alignment / get_stock_attention 单元测试（mock, 零网络）。"""

from typing import Any
from unittest.mock import patch

from finmcp_a_stock_data.tools import alignment as al
from finmcp_a_stock_data.tools import attention as att


def _mk_rows(dates_pcts: list[tuple[str, float]], start_close: float = 100.0) -> list[dict[str, Any]]:
    rows = []
    close = start_close
    for d, pct in dates_pcts:
        close = close * (1 + pct / 100)
        rows.append({"trade_date": d, "close": round(close, 4), "pct_chg": pct})
    return rows


class TestAlignment:
    def _series(self):
        # 7 个交易日: 5 日窗口 + 事件日 + 1 日后窗
        days = ["20260810", "20260811", "20260812", "20260813", "20260814", "20260817", "20260818"]
        tgt = _mk_rows([(d, 1.0) for d in days])  # 每日 +1%
        bench = _mk_rows([(d, 0.5) for d in days])  # 每日 +0.5%
        return tgt, bench

    def test_excess_and_adjustment(self):
        tgt, bench = self._series()
        with patch.object(al, "_fetch_daily", side_effect=lambda code, is_idx, s, e: bench if is_idx else tgt):
            r = al.get_event_market_alignment("2026-08-15", "600519.SH", window=5)
        assert r["ok"]
        d = r["data"]
        # 事件日 8-15 为周六 → 顺延 8-17
        assert d["event_day"]["date"] == "20260817"
        assert d["event_day"]["adjusted"] is True
        # 前 5 日: 标的 (1.01^5-1)=5.1%, 基准 (1.005^5-1)=2.53% → 超额 2.57
        assert d["pre_window"]["target_cum_pct"] == 5.1
        assert d["pre_window"]["benchmark_cum_pct"] == 2.53
        assert d["pre_window"]["excess_pct"] == 2.57
        assert d["post_window"]["partial"] is True  # 只有 1 个后窗日
        assert d["news_timeline"] is None  # 未传 theme_query

    def test_insufficient_pre_window(self):
        tgt, bench = self._series()
        with patch.object(al, "_fetch_daily", side_effect=lambda code, is_idx, s, e: bench if is_idx else tgt):
            r = al.get_event_market_alignment("2026-08-15", "600519.SH", window=10)
        assert not r["ok"]
        assert r["error"]["code"] == "DATA_NOT_FOUND"
        assert "不足" in r["error"]["message"]

    def test_target_not_found_and_param_validation(self):
        with patch.object(al, "_fetch_daily", return_value=[]):
            r = al.get_event_market_alignment("2026-08-15", "600519.SH")
        assert not r["ok"] and r["error"]["code"] == "DATA_NOT_FOUND"
        r = al.get_event_market_alignment("bad-date", "600519.SH")
        assert not r["ok"] and r["error"]["code"] == "INVALID_PARAM"
        r = al.get_event_market_alignment("2026-08-15", "600519.SH", target_type="board")
        assert not r["ok"] and r["error"]["code"] == "INVALID_PARAM"

    def test_pure_facts_no_verdict_fields(self):
        """红线协同: 输出仅事实字段, 不含形态判定/方向结论(归产品层)"""
        tgt, bench = self._series()
        with patch.object(al, "_fetch_daily", side_effect=lambda code, is_idx, s, e: bench if is_idx else tgt):
            r = al.get_event_market_alignment("2026-08-15", "600519.SH", window=5)
        flat = str(r["data"])
        for banned in ("看涨", "看跌", "利好", "利空", "sell", "形态判定完成"):
            assert banned not in flat


class _NoCache:
    def make_key(self, *a):
        return "|".join(a)

    def get(self, key):
        return None

    def set(self, *a, **k):
        pass


class TestAttention:
    def test_success_schema(self):
        def fake_post(path, body):
            if path == "getCurrentLatest":
                return {"code": 0, "data": {"rank": 42, "marketAllCount": 5554, "calcTime": "2026-09-02 20:00"}}
            return {"code": 0, "data": [{"calcTime": "2026-09-01", "rank": 50}]}

        with patch.object(att, "_post", side_effect=fake_post), patch.object(att, "_cache", _NoCache()):
            r = att.get_stock_attention("300750.SZ", days=5)
        assert r["ok"]
        assert r["data"]["current"]["rank"] == 42
        assert r["data"]["history"] == [{"date": "2026-09-01", "rank": 50}]

    def test_upstream_bad_status_is_error(self):
        with (
            patch.object(att, "_post", return_value={"code": 500, "data": None}),
            patch.object(att, "_cache", _NoCache()),
        ):
            r = att.get_stock_attention("300750.SZ")
        assert not r["ok"]
        assert r["error"]["code"] == "UPSTREAM_ERROR"

    def test_invalid_code(self):
        r = att.get_stock_attention("300750")
        assert not r["ok"] and r["error"]["code"] == "INVALID_PARAM"
