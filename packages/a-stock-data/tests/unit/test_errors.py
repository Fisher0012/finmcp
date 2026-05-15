"""errors 模块单元测试"""

from finmcp_a_stock_data.errors import handle_tool_error
from finmcp_common.errors import DataNotFoundError, FinMCPError


class TestHandleToolError:
    def test_finmcp_error(self) -> None:
        e = DataNotFoundError("没有数据", hint="换个日期试试")
        result = handle_tool_error(e, source="tushare")

        assert result["ok"] is False
        assert result["error"]["code"] == "DATA_NOT_FOUND"
        assert "没有数据" in result["error"]["message"]
        assert result["error"]["hint"] == "换个日期试试"
        assert result["meta"]["source"] == "tushare"

    def test_generic_exception(self) -> None:
        e = RuntimeError("unexpected")
        result = handle_tool_error(e, source="akshare")

        assert result["ok"] is False
        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert "unexpected" in result["error"]["message"]

    def test_default_source(self) -> None:
        e = FinMCPError("test")
        result = handle_tool_error(e)
        assert result["meta"]["source"] == "unknown"
