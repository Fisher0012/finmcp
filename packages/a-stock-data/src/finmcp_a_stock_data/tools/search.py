"""search_stocks_by_name tool"""

from typing import Any

from finmcp_common.responses import ok_response


def search_stocks_by_name(query: str, limit: int = 10) -> dict[str, Any]:
    """按公司名称模糊搜索 A 股股票，返回匹配的股票代码列表。

    支持中文全名、简称、拼音首字母（如 "茅台"、"mt"、"贵州茅台"均能命中 600519）。
    返回结果按市值降序排列。limit 默认 10，最大 100。

    典型场景：用户提到公司名但没给代码时，先用此工具解析代码。

    注意：拼音搜索仅匹配首字母缩写，不支持全拼。
    """
    # Stage 1: stub 数据
    stub_data = [
        {
            "stock_code": "600519.SH",
            "name": "贵州茅台",
            "industry": "白酒",
            "market_cap_yi": 19500.5,
        }
    ]
    return ok_response(data=stub_data, source="stub", note="Stage 1 stub 数据")
