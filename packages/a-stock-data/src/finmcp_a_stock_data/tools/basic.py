"""get_stock_basic_info tool"""

from typing import Any

from finmcp_common.responses import ok_response


def get_stock_basic_info(stock_code: str) -> dict[str, Any]:
    """获取 A 股个股的基础信息。

    包括：公司全称、英文名、所属申万一级/二级/三级行业、上市日期、
    总股本、流通股本、注册地、主营业务简介。

    stock_code 支持 "600519"（自动识别）或 "600519.SH" 格式。

    典型场景：用户要求介绍某只股票、了解公司概况时调用。
    """
    # Stage 1: stub 数据
    stub_data = {
        "stock_code": "600519.SH",
        "name": "贵州茅台",
        "full_name": "贵州茅台酒股份有限公司",
        "english_name": "Kweichow Moutai Co.,Ltd.",
        "industry_l1": "食品饮料",
        "industry_l2": "白酒",
        "industry_l3": "白酒",
        "list_date": "2001-08-27",
        "total_share": 125619.78,
        "float_share": 125619.78,
        "area": "贵州",
        "business_scope": "茅台酒系列产品的生产与销售",
    }
    return ok_response(data=stub_data, source="stub", note="Stage 1 stub 数据")
