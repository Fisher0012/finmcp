# finmcp-a-stock-data

A 股行情、财务、基础数据 MCP server。

让 Claude、Cursor 等支持 MCP 协议的 AI 客户端直接获取 A 股真实数据，消灭数据幻觉。

> 数据来源于公开接口，仅供参考，不构成投资建议。实际数据请以交易所官方为准。

## 安装

```bash
pip install finmcp-a-stock-data
```

安装后自带免费数据源（akshare），零配置即用。如需更稳定的数据，可配置 tushare Pro：

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

## 提供的工具（8 个）

### 基础信息

| 工具 | 功能 |
|---|---|
| `search_stocks_by_name` | 按名称/拼音搜索 A 股股票 |
| `get_stock_basic_info` | 获取个股基础信息（行业、上市日期等） |
| `list_industry_constituents` | 列出申万行业成份股 |

### 行情数据

| 工具 | 功能 |
|---|---|
| `get_stock_price` | 获取个股历史行情（日/周/月线，前复权/后复权） |
| `get_latest_quote` | 获取个股实时报价快照 |
| `get_index_price` | 获取指数历史行情 |

### 财务数据

| 工具 | 功能 |
|---|---|
| `get_financial_indicator` | 获取核心财务指标（ROE、毛利率、EPS 等） |
| `get_financial_report_summary` | 获取三大表关键科目摘要 |

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
| `FINMCP_DATA_SOURCE` | `auto` | 数据源：`auto` / `tushare` / `akshare` |
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
