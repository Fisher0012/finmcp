"""date_utils 模块测试"""

from datetime import date

import pytest
from finmcp_common.date_utils import (
    date_range_or_default,
    format_date,
    get_recent_trading_date,
    is_likely_trading_day,
    is_weekend,
    parse_date,
)


class TestParseDate:
    def test_valid(self) -> None:
        assert parse_date("2026-05-14") == date(2026, 5, 14)

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="日期格式错误"):
            parse_date("2026/05/14")

    def test_invalid_date(self) -> None:
        with pytest.raises(ValueError, match="日期格式错误"):
            parse_date("2026-13-01")


class TestFormatDate:
    def test_format(self) -> None:
        assert format_date(date(2026, 5, 14)) == "2026-05-14"


class TestIsWeekend:
    def test_monday(self) -> None:
        # 2026-05-11 是周一
        assert is_weekend(date(2026, 5, 11)) is False

    def test_saturday(self) -> None:
        # 2026-05-16 是周六
        assert is_weekend(date(2026, 5, 16)) is True

    def test_sunday(self) -> None:
        # 2026-05-17 是周日
        assert is_weekend(date(2026, 5, 17)) is True


class TestIsLikelyTradingDay:
    def test_weekday(self) -> None:
        assert is_likely_trading_day(date(2026, 5, 14)) is True

    def test_weekend(self) -> None:
        assert is_likely_trading_day(date(2026, 5, 16)) is False


class TestGetRecentTradingDate:
    def test_weekday_unchanged(self) -> None:
        d = date(2026, 5, 14)  # 周四
        assert get_recent_trading_date(d) == d

    def test_saturday_to_friday(self) -> None:
        assert get_recent_trading_date(date(2026, 5, 16)) == date(2026, 5, 15)

    def test_sunday_to_friday(self) -> None:
        assert get_recent_trading_date(date(2026, 5, 17)) == date(2026, 5, 15)


class TestDateRangeOrDefault:
    def test_both_specified(self) -> None:
        start, end = date_range_or_default("2026-01-01", "2026-05-14")
        assert start == date(2026, 1, 1)
        assert end == date(2026, 5, 14)

    def test_neither_specified(self) -> None:
        start, end = date_range_or_default(None, None, default_days=30)
        assert (end - start).days == 30

    def test_only_end(self) -> None:
        start, end = date_range_or_default(None, "2026-05-14", default_days=10)
        assert end == date(2026, 5, 14)
        assert start == date(2026, 5, 4)
