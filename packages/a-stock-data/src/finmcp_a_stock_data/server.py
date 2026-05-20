"""finmcp-a-stock-data MCP server 入口

注册所有 tool 到 FastMCP 实例，处理启动和生命周期。
"""

from mcp.server.fastmcp import FastMCP

from .tools.basic import get_stock_basic_info
from .tools.concept import list_concept_stocks
from .tools.financial import get_financial_indicator, get_financial_report_summary
from .tools.index import get_index_price
from .tools.industry import list_industry_constituents
from .tools.price import get_stock_price
from .tools.quote import get_latest_quote
from .tools.search import search_stocks_by_name

# 创建 MCP server 实例
mcp = FastMCP(
    "finmcp-a-stock-data",
    instructions="A 股行情、财务、基础数据 MCP server。数据来源于公开接口，仅供参考，不构成投资建议。",
)

# 注册所有 tool
mcp.tool()(search_stocks_by_name)
mcp.tool()(get_stock_basic_info)
mcp.tool()(list_industry_constituents)
mcp.tool()(list_concept_stocks)
mcp.tool()(get_stock_price)
mcp.tool()(get_latest_quote)
mcp.tool()(get_index_price)
mcp.tool()(get_financial_indicator)
mcp.tool()(get_financial_report_summary)


def main() -> None:
    """启动 MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
