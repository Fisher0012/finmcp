# FinMCP — 技术架构

> 本文档定义 FinMCP 项目的代码结构、技术栈、模块划分、关键技术决策。
> 面向 Claude Code 和未来贡献者，作为代码组织的最高约束。

---

## 1. 技术栈总览

| 层 | 选型 | 理由 |
|------|------|------|
| **语言** | Python 3.10+ | 数据生态成熟、akshare/tushare 原生、用户群熟悉 |
| **MCP 框架** | FastMCP（`mcp` SDK 内置） | 官方推荐、装饰器风格、最少样板代码 |
| **类型系统** | Pydantic v2 | LLM 工具参数校验的事实标准 |
| **HTTP 客户端** | httpx | async + sync 双模式 |
| **数据层** | akshare（开源） + tushare Pro（付费可选） | akshare 兜底所有场景，tushare 提供专业数据 |
| **缓存** | diskcache | 本地持久化、无外部依赖、对 LLM 调用模式友好 |
| **测试** | pytest + pytest-asyncio | 标准 |
| **打包** | hatchling + pyproject.toml | 现代 Python 打包标准 |
| **CI/CD** | GitHub Actions | 免费、标准 |
| **代码质量** | ruff（lint + format） + mypy（类型检查） | 速度快、配置简单 |
| **文档** | Markdown + mkdocs-material（v1.5+） | MVP 阶段只用 Markdown，后期加 mkdocs |

## 2. 仓库结构（Monorepo）

采用 monorepo 管理整个工具集，但每个 server 是独立可发布的子包。

```
finmcp/                           # 仓库根目录（GitHub: yourname/finmcp）
├── README.md                     # 项目门面
├── LICENSE                       # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
├── .gitignore
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                # 测试 + lint
│   │   └── publish.yml           # 标签触发发布到 PyPI
│   └── ISSUE_TEMPLATE/
├── docs/
│   ├── design/                   # 本文档集放这里
│   ├── ARCHITECTURE.md
│   ├── TOOLKIT_SPEC.md
│   └── examples/
│       ├── claude-desktop.md
│       ├── cursor.md
│       └── claude-code.md
├── packages/                     # 各个独立 server 子包
│   ├── a-stock-data/             # MVP 优先做这个
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── CHANGELOG.md
│   │   ├── src/
│   │   │   └── finmcp_a_stock_data/
│   │   │       ├── __init__.py
│   │   │       ├── server.py          # MCP server 入口
│   │   │       ├── tools/             # 每个 tool 一个文件
│   │   │       │   ├── __init__.py
│   │   │       │   ├── price.py
│   │   │       │   ├── financial.py
│   │   │       │   ├── basic.py
│   │   │       │   └── industry.py
│   │   │       ├── data_sources/      # 数据源适配
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py        # 抽象基类
│   │   │       │   ├── akshare_src.py
│   │   │       │   └── tushare_src.py
│   │   │       ├── models.py          # Pydantic models
│   │   │       ├── cache.py
│   │   │       ├── errors.py
│   │   │       └── utils.py
│   │   └── tests/
│   │       ├── unit/
│   │       └── integration/
│   ├── stock-valuation/          # P1，M3 启动
│   ├── financial-research/       # P1，M4 启动
│   └── ...
└── shared/                       # 跨包共享代码
    ├── finmcp_common/
    │   ├── __init__.py
    │   ├── responses.py
    │   ├── stock_code.py
    │   ├── date_utils.py
    │   └── logging.py
    └── pyproject.toml
```

**MVP 阶段（第一个月）**：只创建仓库根目录 + `packages/a-stock-data/` + `shared/finmcp_common/`，其他子包目录暂不创建。

## 3. 关键技术决策（ADR）

### ADR-001：MCP 框架选 FastMCP 而非手写 SDK

**决策**：使用官方 `mcp` SDK 中的 FastMCP 装饰器风格。

**理由**：
- 减少 90% 样板代码（无需手写 tool schema）
- 自动从 Python 类型注解生成 MCP schema
- 官方维护，跟随协议演进

**示例**：

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("finmcp-a-stock-data")

@mcp.tool()
def get_stock_price(stock_code: str, date: str | None = None) -> dict:
    """获取 A 股个股行情..."""
    ...

if __name__ == "__main__":
    mcp.run()
```

### ADR-002：每个 tool 独立文件而非聚合到一个 server.py

**决策**：tools 按功能领域拆分文件，server.py 只做注册。

**理由**：
- 单文件不超过 300 行（可维护性）
- 便于按 tool 做单元测试
- 未来重构/拆 server 时迁移成本低

### ADR-003：数据源用 Adapter 模式

**决策**：定义 `DataSource` 抽象基类，akshare 和 tushare 各实现一个 adapter。

**理由**：
- 用户可选择数据源（免费 / 付费）
- 未来加 Wind / 同花顺 API 不破坏现有代码
- 测试时易于 mock

**示例**：

```python
# data_sources/base.py
from abc import ABC, abstractmethod

class StockDataSource(ABC):
    @abstractmethod
    def get_daily_price(self, code: str, start: str, end: str) -> list[dict]: ...

# data_sources/akshare_src.py
import akshare as ak

class AkshareSource(StockDataSource):
    def get_daily_price(self, code: str, start: str, end: str) -> list[dict]:
        df = ak.stock_zh_a_hist(symbol=code, start_date=start, end_date=end)
        return df.to_dict(orient="records")
```

### ADR-004：本地缓存使用 diskcache

**决策**：用 `diskcache` 做本地数据缓存，缓存键包含数据源 + 参数 + 数据日期。

**理由**：
- LLM 调用模式经常重复（同一 stock_code 反复查）
- akshare 上游限流，缓存能显著提升体验
- diskcache 零外部依赖（SQLite-based）

**缓存策略**：
- 历史数据（已收盘）：TTL = 7 天
- 当日实时数据：TTL = 60 秒
- 基础信息（公司名、行业）：TTL = 30 天
- 财务数据：TTL = 1 天

### ADR-005：股票代码统一格式

**决策**：内部统一使用 `{code}.{exchange}` 格式（如 `600519.SH`、`000001.SZ`、`430564.BJ`），但 tool 接口接受两种格式（自动识别）。

**理由**：
- 多交易所并存（沪/深/北），不带 exchange 后缀有歧义
- 用户习惯用 6 位代码，强制后缀降低体验
- 内部归一化便于路由到不同数据源

**实现**（`shared/finmcp_common/stock_code.py`）：

```python
def normalize_stock_code(code: str) -> str:
    """
    "600519" -> "600519.SH"
    "000001" -> "000001.SZ"
    "430564" -> "430564.BJ"
    "600519.SH" -> "600519.SH" (passthrough)
    """
```

### ADR-006：日志和遥测原则

**决策**：使用 Python 标准 `logging`，写到 stderr。**绝对不上报任何遥测**。

**理由**：
- MCP server 的 stdout 是协议通道，日志必须用 stderr
- 遥测违背"用户隐私优先"原则
- 用户可以自己接日志收集

### ADR-007：付费版的实现方式

**决策**：付费数据源（tushare Pro）通过**环境变量 + 可选 import** 实现，**不做付费版闭源**。

**理由**：
- 开源不阻止商业化：tushare Pro 本身需要付费 token，FinMCP 只是 connector
- 用户体验：装一个包，免费/付费功能都在，按环境变量切换

**实现**：

```python
# data_sources/tushare_src.py
import os

class TushareSource(StockDataSource):
    def __init__(self):
        token = os.getenv("TUSHARE_TOKEN")
        if not token:
            raise AuthRequiredError("tushare 数据源需要 TUSHARE_TOKEN 环境变量")
        import tushare as ts
        self.pro = ts.pro_api(token)
```

**真正的付费层**未来通过：
- 独立的高级 server 包（如 `finmcp-pro-research`）
- 或 SaaS 化的 Alpha Press 产品

## 4. 数据流与调用链路

典型一次 `get_stock_price` 调用的完整链路：

```
Claude Desktop / Cursor
        │
        │ MCP stdio
        ▼
finmcp-a-stock-data (本地进程)
        │
        ├── 1. 参数校验 (Pydantic)
        │
        ├── 2. 股票代码归一化 (finmcp_common.stock_code)
        │
        ├── 3. 缓存查询 (diskcache)
        │       │
        │       ├── 命中 ──► 返回（meta.cache_hit=True）
        │       │
        │       └── 未命中 ──► 4. 数据源调用
        │                       │
        │                       ├── AkshareSource (默认)
        │                       │       │
        │                       │       └── akshare → 东财/新浪/腾讯接口
        │                       │
        │                       └── TushareSource (有 token 时)
        │                               │
        │                               └── tushare → tushare.pro API
        │
        ├── 5. 数据规整 (转 Pydantic model)
        │
        ├── 6. 写缓存
        │
        └── 7. 构造标准响应（带 meta.source / meta.fetched_at）
        │
        ▼
返回给 Claude（LLM 看到结构化结果）
```

## 5. 配置管理

用户配置通过**环境变量**管理（不引入 config file，降低门槛）：

| 环境变量 | 必需 | 默认 | 说明 |
|----------|------|------|------|
| `FINMCP_CACHE_DIR` | 否 | `~/.finmcp/cache` | 本地缓存目录 |
| `FINMCP_DATA_SOURCE` | 否 | `akshare` | `akshare` / `tushare` / `auto` |
| `FINMCP_LOG_LEVEL` | 否 | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `TUSHARE_TOKEN` | 仅 tushare 模式 | - | tushare Pro 的 token |
| `FINMCP_CACHE_TTL_REALTIME` | 否 | `60` | 实时数据缓存秒数 |

## 6. MCP 客户端集成

用户通过修改客户端配置接入：

### Claude Desktop

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

### Claude Code

```bash
claude mcp add finmcp-a-stock-data uvx finmcp-a-stock-data
```

### Cursor

通过 Cursor Settings → MCP 添加同样的 command。

**关键设计**：使用 `uvx` 启动而非 `python -m`，避免用户配 PYTHONPATH 的痛苦。

## 7. 安全与合规

### 7.1 数据合规

- akshare 数据基于公开接口，个人使用无合规风险
- tushare 数据需用户自己付费获取 token，FinMCP 只是 connector
- **不抓取需要登录的数据源**（如东方财富 Choice、Wind 客户端）
- **不绕过任何数据源的反爬措施**

### 7.2 用户安全

- 不写任何文件到非约定目录（仅 `FINMCP_CACHE_DIR`）
- 不发起非数据源相关的网络请求
- 不读取环境变量中除明确声明外的任何变量
- MCP server 默认只读，写操作（如 `wechat-publisher`）必须有显式 confirm 参数

### 7.3 责任声明

所有数据 / 分析输出在 README 和返回 meta 中明确：
- "数据来源于公开接口，仅供参考"
- "不构成投资建议"
- "实际数据请以交易所官方为准"

## 8. 性能目标

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| 冷启动时间 | < 2 秒 | 从 client 启动 server 到第一次 ready |
| 单 tool 调用延迟（缓存命中） | < 50ms | 本地测试 |
| 单 tool 调用延迟（缓存未命中） | < 3 秒 | 取决于 akshare 上游 |
| 内存占用（idle） | < 100MB | 启动后无调用时 |
| 安装包大小 | < 50MB（含依赖） | pip download |

## 9. 监控与可观测性（本地）

由于不上报遥测，用户可通过日志自查：

- DEBUG 级别：每次 tool 调用的输入、缓存命中、上游调用耗时
- INFO 级别：tool 调用次数、错误率
- ERROR 级别：未处理异常 + stack trace

未来可选提供 `finmcp doctor` 命令：检查环境、数据源连通性、缓存状态。

## 10. 不在 v1.0 范围内的事项

明确**不做**的事，避免范围蔓延：

- 不做 Web UI（即使是 debug 用的）
- 不做用户认证 / 多租户
- 不做云端同步
- 不做实时推送 / WebSocket
- 不做插件系统（v1.0 没人会写插件）
- 不做国际化（i18n），文档双语足够
- 不内置数据可视化（图表交给上层工具）

---

## 11. 给 Claude Code 的硬约束

**以下是 Claude Code 开发时必须遵守的硬性规则**：

1. **不允许引入未在本文档列出的依赖**，如有需要先在 issue 中讨论
2. **不允许在 src 中使用相对导入超过两层**（`from ..foo import bar` 是上限）
3. **所有 tool 函数必须有完整的 docstring**（按 `2_MCP_TOOLKIT_SPEC.md` §4 规范）
4. **所有 tool 必须有至少 1 个 unit test + 1 个 integration test**
5. **commit message 遵循 Conventional Commits**（`feat:`, `fix:`, `docs:` 等）
6. **不允许直接 push 到 main**，所有改动通过 PR（个人项目阶段可自审，但走流程）
7. **任何时候不允许 `# type: ignore` 全文件**，只能精确到行
8. **不允许在代码中硬编码任何路径、URL、token**

违反任一条规则的 commit 必须 revert。
