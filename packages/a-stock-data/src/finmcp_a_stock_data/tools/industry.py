"""list_industry_constituents tool"""

from typing import Any

from finmcp_common.responses import ok_response


def list_industry_constituents(
    industry_code: str | None = None,
    industry_name: str | None = None,
    level: int = 1,
) -> dict[str, Any]:
    """列出申万行业分类下的所有成份股。

    industry_code 和 industry_name 二选一（至少提供一个）。
    level=1/2/3 对应申万一级/二级/三级行业分类。

    典型场景：用户问"白酒板块有哪些股票"、"半导体行业龙头是谁"时调用。

    注意：行业分类基于申万标准，与证监会/中信分类可能不同。
    """
    # Stage 1: stub 数据
    stub_data = [
        {"stock_code": "600519.SH", "name": "贵州茅台", "industry": "白酒"},
        {"stock_code": "000858.SZ", "name": "五粮液", "industry": "白酒"},
    ]
    return ok_response(data=stub_data, source="stub", note="Stage 1 stub 数据")
