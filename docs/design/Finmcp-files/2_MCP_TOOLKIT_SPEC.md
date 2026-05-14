# FinMCP — 工具集规格说明 (Toolkit Spec)

> 本文档定义 FinMCP 完整工具集的设计原则、命名规范、接口约定。
> **当前 MVP 阶段只实现 `finmcp-a-stock-data`，但所有 server 都必须遵循本文档的统一规范。**

---

## 1. 设计原则

### 1.1 核心原则

| 原则 | 说明 |
|------|------|
| **LLM-First** | 所有 tool 的输入参数、返回值、错误信息都以"LLM 容易理解"为最高优先级 |
| **无副作用优先** | 默认只读，写操作必须显式标记并要求用户确认 |
| **数据可追溯** | 所有返回数据必须带数据源、获取时间戳，便于幻觉检测 |
| **失败优雅** | 永远不抛裸异常，所有错误返回结构化的 ErrorResult |
| **本地运行** | 不依赖云端服务，用户本地安装即用 |
| **零配置启动** | 90% 的功能不需要 API key 即可使用（基于免费数据源） |

### 1.2 反原则（避免做的事）

- 不做 GUI / 不做 Web 服务
- 不存储用户数据
- 不收集用户行为遥测（即使匿名）
- 不做"魔法默认值"——所有重要参数必须显式
- 不在 tool 描述里塞营销话术，描述只为帮助 LLM 正确调用

## 2. 命名规范

### 2.1 包名

- 主包：`finmcp` （PyPI 包名）
- 子 server 包：`finmcp-{domain}-{action}`
  - 例：`finmcp-a-stock-data`, `finmcp-stock-valuation`, `finmcp-xhs-formatter`

### 2.2 Tool 命名

工具名遵循 `{verb}_{noun}` 模式，统一使用 snake_case：

| 推荐 | 不推荐 | 说明 |
|------|--------|------|
| `get_stock_price` | `getStockPrice`, `stock_price`, `fetch_price` | 动词清晰、snake_case |
| `list_industry_constituents` | `industries`, `get_all` | 集合返回用 list_，单条用 get_ |
| `search_stocks_by_name` | `find_stocks`, `query_stocks` | 搜索类用 search_ |
| `calculate_pe_ratio` | `pe`, `compute_pe` | 计算类用 calculate_ |

### 2.3 参数命名

| 类型 | 命名规范 | 示例 |
|------|----------|------|
| 股票代码 | `stock_code` | `"600519"` 或 `"600519.SH"` |
| 日期 | `date` / `start_date` / `end_date` | `"2026-05-14"` (ISO 8601) |
| 周期 | `period` | `"daily"`, `"weekly"`, `"monthly"` |
| 行业代码 | `industry_code` | `"801080"` (申万) |
| 限制数量 | `limit` | 默认 20, 最大 1000 |

## 3. 统一返回结构

### 3.1 成功返回

所有 tool 返回必须是 `Dict` 类型，包含以下顶层字段：

```python
{
    "ok": True,                    # 固定布尔
    "data": {...} | [...],         # 实际数据，结构由具体 tool 定义
    "meta": {                      # 元数据
        "source": "akshare",       # 数据源标识
        "fetched_at": "2026-05-14T10:30:00+08:00",  # 获取时间（带时区）
        "cache_hit": False,        # 是否命中本地缓存
        "note": "..."              # 可选：人类可读的补充说明
    }
}
```

### 3.2 失败返回

```python
{
    "ok": False,
    "error": {
        "code": "DATA_NOT_FOUND",  # 机读错误码（见 §3.3）
        "message": "未找到代码为 600519 在 2024-12-31 的数据",  # 人读描述
        "hint": "可能原因：当日为非交易日，建议使用最近交易日"  # LLM 可读的恢复建议
    },
    "meta": {
        "source": "akshare",
        "fetched_at": "2026-05-14T10:30:00+08:00"
    }
}
```

### 3.3 标准错误码

| Code | 含义 | LLM 应如何应对 |
|------|------|----------------|
| `INVALID_PARAM` | 参数格式错误 | 检查参数格式，重试 |
| `DATA_NOT_FOUND` | 数据不存在 | 提示用户或换参数 |
| `RATE_LIMITED` | 上游数据源限流 | 等待后重试 |
| `UPSTREAM_ERROR` | 上游数据源故障 | 告知用户上游问题 |
| `NOT_TRADING_DAY` | 非交易日 | 换最近交易日 |
| `AUTH_REQUIRED` | 需要付费 API key（如 tushare Pro） | 提示用户配置 |
| `INTERNAL_ERROR` | 内部错误 | 上报 issue |

## 4. Tool 描述规范

每个 tool 的 description（提供给 LLM 的提示）必须包含：

1. **一句话功能**（动词开头）
2. **核心参数说明**（不要重复 schema）
3. **典型场景**（让 LLM 知道何时该调用）
4. **限制和注意事项**（避免 LLM 误用）

**好例子**：

```python
@mcp.tool()
def get_stock_price(
    stock_code: str,
    date: str | None = None,
    period: str = "daily"
) -> dict:
    """
    获取 A 股个股的历史或最新行情。

    支持沪深京三所，stock_code 可以是 "600519"（自动识别）或 "600519.SH" 格式。
    date 为 None 时返回最新交易日数据；指定日期且为非交易日时返回 NOT_TRADING_DAY 错误。
    period 支持 daily / weekly / monthly。

    典型场景：用户问某只股票当前价格、某天的涨跌、最近一周走势时调用。

    注意：当日数据需在收盘后获取才完整；盘中获取的当日数据是实时快照，open/high/low 已确定但 close 未定。
    """
```

**坏例子**（描述对 LLM 无用）：

```python
"""获取股票价格。"""
```

## 5. 各 Server 功能边界（防重叠）

工具集扩展时容易出现"这个 tool 放哪个 server 好"的纠结，按下表划界：

| Server | 职责边界 | 不做的事 |
|--------|----------|----------|
| `a-stock-data` | 原始数据获取（行情、财报、基本面） | 不做计算、不做分析 |
| `stock-valuation` | 基于原始数据的估值计算 | 不做数据获取（依赖 a-stock-data） |
| `financial-research` | 综合分析、产业链、归因 | 不做数据获取、不做发布 |
| `xhs-formatter` | Xhs 平台图文排版 | 只管 Xhs，不管公众号 |
| `wechat-publisher` | 公众号推送 | 只管公众号，不管 Xhs |
| `macro-data` | 宏观数据（CPI/M2/利率） | 不做个股数据 |
| `research-fetch` | 卖方研报抓取 | 不做内容生成 |
| `portfolio-tracker` | 组合管理 | 不做交易执行 |

**原则**：**单一职责**。如果某个功能跨两个 server，宁可在两个 server 里都重复一个轻量包装，也不要做"大而全"的 server。

## 6. 版本管理

- 遵循 **语义化版本** (Semantic Versioning 2.0)
- `v0.x.y`：开发期，API 可能 breaking
- `v1.0.0`：API 稳定承诺
- 每个 server 独立版本号（不强求统一）

## 7. 依赖管理

### 7.1 通用依赖（所有 server 共用）

```
python >= 3.10
mcp >= 1.0.0        # MCP Python SDK
pydantic >= 2.0     # 类型校验
httpx >= 0.27       # HTTP 客户端
```

### 7.2 数据层依赖

| Server | 主依赖 | 备注 |
|--------|--------|------|
| `a-stock-data` | `akshare >= 1.16` | 主力，免费 |
| `a-stock-data` (付费版) | `tushare >= 1.4` | 可选，需 token |
| `stock-valuation` | `numpy`, `pandas` | 计算 |
| `xhs-formatter` | `Pillow`, `playwright` | 图片渲染 |

### 7.3 依赖最小化原则

每个 server 的依赖列表越少越好。能用标准库就不用第三方。**用户安装时 pip 拉取时间应 < 30 秒**。

## 8. 测试规范

| 类型 | 覆盖率要求 | 工具 |
|------|------------|------|
| 单元测试 | ≥ 80% 函数覆盖 | pytest |
| 集成测试 | 每个 tool 至少 1 个真实调用用例 | pytest + 真实数据 |
| MCP 协议测试 | 验证 server 能被标准客户端调用 | mcp inspector |

**所有测试必须可在 CI 中运行**（GitHub Actions）。

## 9. 文档规范

每个 server 必须有：

1. `README.md`：安装、快速开始、配置（顶层）
2. `docs/TOOLS.md`：所有 tool 的详细参数和返回示例
3. `docs/EXAMPLES.md`：3-5 个典型场景的端到端示例
4. `CHANGELOG.md`：版本变更记录
5. `LICENSE`：MIT

## 10. 发布流程

```
本地开发 → 单元测试 → 集成测试 → 文档更新 → 版本号 bump →
GitHub Release → PyPI 发布 → MCP Registry 提交 → 社交媒体公告
```

每次发布的"社交媒体公告"包含：
- GitHub Release Notes
- 一条 Twitter / X 公告
- 一条即刻动态
- 一条 Xhs 笔记（针对中文创作者用户）

---

**当前阶段重点**：本文档定义的所有规范，**MVP 第一个 server `finmcp-a-stock-data` 必须 100% 遵循**。后续 server 的开发都以此为基线。
