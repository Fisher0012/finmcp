"""finmcp-a-stock-data MCP server 入口

注册所有 tool 到 FastMCP 实例，处理启动和生命周期。
"""

from mcp.server.fastmcp import FastMCP

from .tools.basic import get_stock_basic_info
from .tools.concept import list_concept_stocks, list_stock_concepts
from .tools.financial import get_financial_indicator, get_financial_report_summary
from .tools.forecast import get_earnings_forecast
from .tools.holder import get_major_shareholder_change, get_pledge_status
from .tools.index import get_index_price
from .tools.industry import get_industry_overview, list_industry_constituents
from .tools.investor import get_investor_qa
from .tools.news import get_market_signals, get_stock_news
from .tools.operating import get_industry_operating_evidence
from .tools.price import get_stock_price
from .tools.profile import get_annual_report_mdna, get_company_profile
from .tools.quote import get_latest_quote
from .tools.ratings import get_broker_ratings, get_buyback
from .tools.realtime_em import get_market_snapshot, get_money_flow, get_sector_ranking
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
mcp.tool()(get_industry_overview)
mcp.tool()(get_stock_news)
mcp.tool()(get_market_signals)
# F3 下沉工具（SPEC §3.3, 12 个）
mcp.tool()(get_company_profile)
mcp.tool()(get_annual_report_mdna)
mcp.tool()(get_earnings_forecast)
mcp.tool()(get_investor_qa)
mcp.tool()(get_major_shareholder_change)
mcp.tool()(get_pledge_status)
mcp.tool()(get_broker_ratings)
mcp.tool()(get_buyback)
mcp.tool()(get_industry_operating_evidence)
mcp.tool()(get_money_flow)
mcp.tool()(get_market_snapshot)
mcp.tool()(get_sector_ranking)
# F3 反查补全（SPEC §3.4）
mcp.tool()(list_stock_concepts)


def main() -> None:
    """启动 MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
