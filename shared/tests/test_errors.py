"""errors 模块测试"""

from finmcp_common.errors import (
    AuthRequiredError,
    DataNotFoundError,
    FinMCPError,
    InvalidParamError,
    NotTradingDayError,
    RateLimitedError,
    UpstreamError,
)


class TestErrorCodes:
    def test_base_error(self) -> None:
        e = FinMCPError("test")
        assert e.code == "INTERNAL_ERROR"
        assert str(e) == "test"
        assert e.hint is None

    def test_invalid_param(self) -> None:
        e = InvalidParamError("参数错误", hint="检查格式")
        assert e.code == "INVALID_PARAM"
        assert e.hint == "检查格式"

    def test_data_not_found(self) -> None:
        e = DataNotFoundError("未找到数据")
        assert e.code == "DATA_NOT_FOUND"

    def test_rate_limited_defaults(self) -> None:
        e = RateLimitedError()
        assert e.code == "RATE_LIMITED"
        assert "限流" in str(e)
        assert e.hint is not None

    def test_not_trading_day(self) -> None:
        e = NotTradingDayError("2026-05-17")
        assert e.code == "NOT_TRADING_DAY"
        assert "2026-05-17" in str(e)
        assert "交易日" in str(e.hint or "")

    def test_auth_required(self) -> None:
        e = AuthRequiredError("需要 token")
        assert e.code == "AUTH_REQUIRED"

    def test_upstream_error(self) -> None:
        e = UpstreamError("akshare 故障")
        assert e.code == "UPSTREAM_ERROR"

    def test_inheritance(self) -> None:
        assert issubclass(InvalidParamError, FinMCPError)
        assert issubclass(DataNotFoundError, FinMCPError)
        assert issubclass(RateLimitedError, FinMCPError)
        assert issubclass(NotTradingDayError, FinMCPError)
        assert issubclass(AuthRequiredError, FinMCPError)
        assert issubclass(UpstreamError, FinMCPError)
