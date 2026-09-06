"""finmcp-a-stock-data MCP server 入口

注册所有 tool 到 FastMCP 实例，处理启动和生命周期。
"""

from mcp.server.fastmcp import FastMCP

from .tools.alignment import get_event_market_alignment
from .tools.attention import get_stock_attention
from .tools.basic import get_stock_basic_info
from .tools.chips import get_block_trades, get_holder_number, get_margin_flow, get_top_float_holders
from .tools.concept import list_concept_stocks, list_stock_concepts
from .tools.dividend import get_dividend_history
from .tools.financial import get_financial_indicator, get_financial_report_summary
from .tools.forecast import get_earnings_forecast
from .tools.holder import get_major_shareholder_change, get_pledge_status
from .tools.index import get_index_price
from .tools.industry import get_industry_overview, list_industry_constituents
from .tools.investor import get_investor_qa
from .tools.ipo import get_ipo_calendar
from .tools.macro import get_macro_indicator
from .tools.meso_global import get_global_context, get_meso_indicator
from .tools.meso_scrape import (
    get_cement_price,
    get_chip_output,
    get_excavator_sales,
    get_liquor_price,
    get_storage_price,
)
from .tools.news import get_market_signals, get_stock_news
from .tools.northbound import get_northbound_flow
from .tools.operating import get_industry_operating_evidence
from .tools.price import get_stock_price
from .tools.profile import get_annual_report_mdna, get_company_profile
from .tools.quote import get_latest_quote
from .tools.ratings import get_broker_ratings, get_buyback
from .tools.realtime_em import get_market_snapshot, get_money_flow, get_sector_ranking
from .tools.search import search_stocks_by_name
from .tools.supply_expectation import get_consensus_forecast, get_share_unlock
from .tools.toplist import get_stock_margin_detail, get_top_list
from .tools.valuation_history import get_valuation_history

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
# F5 新数据域（SPEC §5, 3 个: 宏观指标 / 分红历史 / 北向资金）
mcp.tool()(get_macro_indicator)
mcp.tool()(get_dividend_history)
mcp.tool()(get_northbound_flow)
mcp.tool()(get_event_market_alignment)
mcp.tool()(get_stock_attention)
mcp.tool()(get_ipo_calendar)
mcp.tool()(get_storage_price)
mcp.tool()(get_top_list)
mcp.tool()(get_stock_margin_detail)
mcp.tool()(get_valuation_history)
mcp.tool()(get_margin_flow)
mcp.tool()(get_holder_number)
mcp.tool()(get_top_float_holders)
mcp.tool()(get_block_trades)
mcp.tool()(get_share_unlock)
mcp.tool()(get_consensus_forecast)
mcp.tool()(get_meso_indicator)
mcp.tool()(get_global_context)
# 数据缺口自建抓取（水泥/挖掘机/集成电路/白酒批价, 见 tools/meso_scrape.py）
mcp.tool()(get_cement_price)
mcp.tool()(get_excavator_sales)
mcp.tool()(get_chip_output)
mcp.tool()(get_liquor_price)


def main() -> None:
    """启动 MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
