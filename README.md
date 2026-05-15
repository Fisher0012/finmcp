# FinMCP

> Open-Source MCP Toolkit for A-Share Financial Data
> 给 AI 财经/投研创作者的开源 MCP 工具集

FinMCP 是一组面向 A 股市场的 MCP（Model Context Protocol）工具集，让 Claude、Cursor、Claude Code 等 AI 客户端能直接获取 A 股真实数据，消灭数据幻觉。

## 当前可用的 Server

| Server | 功能 | 状态 |
|---|---|---|
| [`finmcp-a-stock-data`](packages/a-stock-data/) | A 股行情、财务、基础数据 | v0.1.0 |

## Quick Start

```bash
# 安装
pip install finmcp-a-stock-data

# 接入 Claude Code
claude mcp add finmcp-a-stock-data uvx finmcp-a-stock-data

# 接入 Claude Desktop — 编辑配置文件加入：
# {"mcpServers": {"finmcp-a-stock-data": {"command": "uvx", "args": ["finmcp-a-stock-data"]}}}
```

然后直接用自然语言提问：

- "茅台最近五年 ROE 怎么样？"
- "宁德时代今天涨了多少？"
- "半导体板块有哪些龙头股？"

## 项目结构

```
finmcp/
├── packages/
│   └── a-stock-data/     # A 股数据 MCP server (v0.1.0)
├── shared/
│   └── finmcp_common/    # 共享工具库
└── docs/
    └── design/           # 设计文档
```

## 设计原则

- **LLM-First**：接口和返回值为 LLM 优化
- **数据可追溯**：所有返回带 source + fetched_at 元数据
- **本地运行**：不依赖云端服务，用户本地安装即用
- **零配置启动**：免费数据源开箱即用，付费数据源按需配置
- **零遥测**：不收集任何用户数据

## 数据源

| 数据源 | 类型 | 配置 |
|---|---|---|
| akshare | 免费 | 零配置 |
| tushare Pro | 付费 | 设置 `TUSHARE_TOKEN` 环境变量 |

## Roadmap

详见 [PROJECT_OVERVIEW](docs/design/Finmcp-files/1_PROJECT_OVERVIEW.md)

## Contributing

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT
