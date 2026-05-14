"""responses 模块测试"""

from finmcp_common.responses import error_response, ok_response


class TestOkResponse:
    def test_basic_structure(self) -> None:
        result = ok_response(data={"price": 100}, source="tushare")
        assert result["ok"] is True
        assert result["data"] == {"price": 100}
        assert result["meta"]["source"] == "tushare"
        assert "fetched_at" in result["meta"]
        assert result["meta"]["cache_hit"] is False

    def test_cache_hit(self) -> None:
        result = ok_response(data=[], source="akshare", cache_hit=True)
        assert result["meta"]["cache_hit"] is True

    def test_with_note(self) -> None:
        result = ok_response(data={}, source="akshare", note="盘中数据")
        assert result["meta"]["note"] == "盘中数据"

    def test_without_note(self) -> None:
        result = ok_response(data={}, source="akshare")
        assert "note" not in result["meta"]

    def test_list_data(self) -> None:
        data = [{"code": "600519"}, {"code": "000001"}]
        result = ok_response(data=data, source="tushare")
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2


class TestErrorResponse:
    def test_basic_structure(self) -> None:
        result = error_response(
            code="INVALID_PARAM",
            message="参数错误",
            source="akshare",
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "INVALID_PARAM"
        assert result["error"]["message"] == "参数错误"
        assert "hint" not in result["error"]
        assert result["meta"]["source"] == "akshare"

    def test_with_hint(self) -> None:
        result = error_response(
            code="NOT_TRADING_DAY",
            message="非交易日",
            hint="请换一个交易日",
        )
        assert result["error"]["hint"] == "请换一个交易日"

    def test_default_source(self) -> None:
        result = error_response(code="INTERNAL_ERROR", message="内部错误")
        assert result["meta"]["source"] == "unknown"
