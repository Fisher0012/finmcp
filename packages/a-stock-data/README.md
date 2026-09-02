# finmcp-a-stock-data

A 股行情、财务、基础数据 MCP server。

让 Claude、Cursor 等支持 MCP 协议的 AI 客户端直接获取 A 股真实数据，消灭数据幻觉。

> 数据来源于公开接口，仅供参考，不构成投资建议。实际数据请以交易所官方为准。

## 安装

```bash
pip install finmcp-a-stock-data
```

当前仅支持 tushare Pro 数据源（akshare 适配层尚未实现），使用前需配置 token：

```bash
export TUSHARE_TOKEN="你的token"
```

## 接入 Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "finmcp-a-stock-data": {
      "command": "uvx",
      "args": ["finmcp-a-stock-data"]
    }
  }
}
```

## 接入 Claude Code

```bash
claude mcp add finmcp-a-stock-data uvx finmcp-a-stock-data
```

## 接入 Cursor

Cursor Settings > MCP > Add Server，填写：
- Command: `uvx`
- Args: `finmcp-a-stock-data`

## 提供的工具（25 个）

### 基础信息与板块

| 工具 | 功能 |
|---|---|
| `search_stocks_by_name` | 按名称/拼音搜索 A 股股票 |
| `get_stock_basic_info` | 获取个股基础信息（行业含申万 L1/L2/L3、上市日期等） |
| `list_industry_constituents` | 列出申万行业成份股 |
| `list_concept_stocks` | 按概念/题材搜索成份股（同花顺→tushare→关键词三级） |
| `list_stock_concepts` | 个股→概念反查：某只股票所属的全部概念板块 |
| `get_industry_overview` | 行业全景：成份股行情/估值批量排名 |
| `get_industry_operating_evidence` | 行业市值前列样本的同期年报经营指标（有界样本证据） |

### 行情数据

| 工具 | 功能 |
|---|---|
| `get_stock_price` | 获取个股历史行情（日/周/月线，前复权/后复权） |
| `get_latest_quote` | 获取个股实时报价快照 |
| `get_index_price` | 获取指数历史行情 |
| `get_market_snapshot` | 大盘实时快照（指数 + 涨跌家数 + 两市成交额，东财实时） |
| `get_money_flow` | 个股主力资金流（东财实时优先，tushare EOD 回退） |
| `get_sector_ranking` | 当日板块主力资金排行/板块名点查（东财实时） |

### 财务数据

| 工具 | 功能 |
|---|---|
| `get_financial_indicator` | 获取核心财务指标（ROE、毛利率、EPS 等） |
| `get_financial_report_summary` | 获取三大表关键科目摘要 |
| `get_earnings_forecast` | 业绩预告（预增/预减/扭亏 + 净利润区间，亿元口径） |

### 公司深度信息

| 工具 | 功能 |
|---|---|
| `get_company_profile` | 公司主营业务/经营范围/公司介绍 |
| `get_annual_report_mdna` | 年报 MD&A 战略段落抽取（巨潮 PDF，需 `[disclosure]` extras） |
| `get_investor_qa` | 投资者互动问答（互动易/上证 e 互动，需 `[akshare]` extras） |
| `get_major_shareholder_change` | 大股东增减持 |
| `get_pledge_status` | 股票质押状态 |
| `get_broker_ratings` | 券商研报评级+目标价（第三方观点标注透传，需 `[akshare]` extras） |
| `get_buyback` | 公司回购（需 `[akshare]` extras） |

### 公告与异动

| 工具 | 功能 |
|---|---|
| `get_stock_news` | 个股公告（巨潮公告 + 东财公告双源；非 7x24 快讯） |
| `get_market_signals` | 近期异动信号（涨跌停日线阈值判定 + 龙虎榜） |

optional extras 未安装时，对应工具返回 `NOT_SUPPORTED` 错误而非 ImportError：

```bash
pip install 'finmcp-a-stock-data[akshare]'     # 互动问答/券商评级/回购
pip install 'finmcp-a-stock-data[disclosure]'  # 年报 MD&A（pdfplumber）
```

## 使用示例

安装并接入后，直接用自然语言提问：

- "茅台最近五年 ROE 怎么样？"
- "宁德时代今天涨了多少？"
- "半导体板块有哪些龙头股？"
- "上证指数最近一个月走势"
- "比亚迪 2024 年报营收多少？"

Claude 会自动调用对应工具获取真实数据并回答。

## 配置

通过环境变量配置（均为可选）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TUSHARE_TOKEN` | - | tushare Pro token，设置后自动切换为 tushare 数据源 |
| `FINMCP_DATA_SOURCE` | `auto` | 数据源：`auto` / `tushare`（akshare 尚未实现，指定会得到显式错误） |
| `FINMCP_CACHE_DIR` | `~/.finmcp/cache` | 本地缓存目录 |
| `FINMCP_LOG_LEVEL` | `INFO` | 日志级别 |
| `FINMCP_CACHE_TTL_REALTIME` | `60` | 实时数据缓存秒数 |

## License

MIT

---

# finmcp-a-stock-data (English)

MCP server for A-share (Chinese mainland) stock data — quotes, financials, and basic info.

Enables Claude, Cursor, and other MCP-compatible AI clients to query real A-share market data, eliminating data hallucination.

## Quick Start

```bash
pip install finmcp-a-stock-data
claude mcp add finmcp-a-stock-data uvx finmcp-a-stock-data
```

Then ask Claude: "What's Kweichow Moutai's ROE for the past 5 years?"

See the Chinese section above for full documentation.
