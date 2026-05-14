# FinMCP — MVP 范围 (`finmcp-a-stock-data` v0.1.0)

> 本文档定义 FinMCP 项目第一个、也是唯一一个 MVP 交付物的精确范围。
> **任何不在本文档中列出的功能，都不是 MVP 范围。**

---

## 1. MVP 目标

**核心目标**：让 Claude 能正确回答中文用户关于 A 股的真实数据问题。

**成功画面**：

用户在 Claude Desktop 中问：
> "茅台最近五年 ROE 怎么样？"

Claude 自动调用 `get_financial_indicator(stock_code="600519", indicator="roe", years=5)`，返回真实数据，并基于数据回答。**用户不需要做任何额外配置**（除了首次安装）。

## 2. MVP 包含的 Tools

**共 8 个 tool**，覆盖财经创作者最高频的查询场景。

### 2.1 基础信息类（3 个）

#### Tool 1: `search_stocks_by_name`

按公司名称或拼音首字母模糊搜索 A 股股票。

```python
def search_stocks_by_name(
    query: str,
    limit: int = 10
) -> dict:
    """
    按公司名称模糊搜索 A 股股票，返回匹配的股票代码列表。

    支持中文全名、简称、拼音首字母（如 "茅台"、"mt"、"贵州茅台"均能命中 600519）。
    返回结果按市值降序排列。

    典型场景：用户提到公司名但没给代码时，先用此工具解析代码。
    """
```

**返回示例**：

```json
{
  "ok": true,
  "data": [
    {
      "stock_code": "600519.SH",
      "name": "贵州茅台",
      "industry": "白酒",
      "market_cap_yi": 19500.5
    }
  ],
  "meta": {"source": "akshare", "fetched_at": "2026-05-14T10:30:00+08:00"}
}
```

#### Tool 2: `get_stock_basic_info`

获取股票的基础信息（公司全称、所属行业、上市日期、总股本等）。

```python
def get_stock_basic_info(stock_code: str) -> dict:
    """
    获取 A 股个股的基础信息。

    包括：公司全称、英文名、所属申万一级/二级/三级行业、上市日期、
    总股本、流通股本、注册地、主营业务简介。

    典型场景：用户要求介绍某只股票时调用。
    """
```

#### Tool 3: `list_industry_constituents`

列出某个申万行业下的所有成份股。

```python
def list_industry_constituents(
    industry_code: str | None = None,
    industry_name: str | None = None,
    level: int = 1
) -> dict:
    """
    列出申万行业分类下的所有成份股。

    industry_code 和 industry_name 二选一。level=1/2/3 对应申万一级/二级/三级。

    典型场景：用户问"白酒板块有哪些股票"、"半导体行业龙头是谁"时调用。
    """
```

### 2.2 行情数据类（3 个）

#### Tool 4: `get_stock_price`

获取个股的历史行情数据。

```python
def get_stock_price(
    stock_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily",
    adjust: str = "qfq"
) -> dict:
    """
    获取 A 股个股的历史行情。

    period: daily / weekly / monthly
    adjust: qfq（前复权） / hfq（后复权） / none（不复权）
    start_date / end_date 格式 YYYY-MM-DD；都为 None 时返回最近 60 个交易日。

    返回字段：date, open, high, low, close, volume, amount, pct_change, turnover_rate

    典型场景：分析走势、计算涨跌、回测时调用。
    """
```

#### Tool 5: `get_latest_quote`

获取个股的实时报价快照。

```python
def get_latest_quote(stock_code: str) -> dict:
    """
    获取 A 股个股的当前快照（盘中实时，收盘后为收盘数据）。

    返回字段：current_price, change, pct_change, open, high, low,
    prev_close, volume, amount, bid_ask_spread, market_cap_yi, pe_ttm, pb

    注意：缓存 TTL 60 秒，频繁调用同一代码会返回缓存值。

    典型场景：用户问"XX 现在多少钱"时调用。
    """
```

#### Tool 6: `get_index_price`

获取指数（上证指数、沪深300、创业板指等）的历史行情。

```python
def get_index_price(
    index_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily"
) -> dict:
    """
    获取主要 A 股指数的历史行情。

    支持常见指数：
    - 000001.SH (上证指数)
    - 399001.SZ (深证成指)
    - 399006.SZ (创业板指)
    - 000300.SH (沪深300)
    - 000905.SH (中证500)
    - 000852.SH (中证1000)
    - 399986.SZ (中证银行)
    - 等约 30 个主流指数

    典型场景：分析大盘走势、计算个股相对收益时调用。
    """
```

### 2.3 财务数据类（2 个）

#### Tool 7: `get_financial_indicator`

获取个股的核心财务指标（按报告期）。

```python
def get_financial_indicator(
    stock_code: str,
    indicators: list[str] | None = None,
    years: int = 5
) -> dict:
    """
    获取个股的核心财务指标，按报告期返回。

    indicators 支持：
    - 盈利能力：roe, roa, gross_margin, net_margin
    - 成长性：revenue_yoy, net_profit_yoy
    - 偿债能力：debt_to_asset, current_ratio
    - 运营效率：asset_turnover, inventory_turnover
    - 估值：pe_ttm, pb, ps_ttm
    - 其他：eps, bvps, ocf_per_share

    indicators=None 返回全部指标。years 控制返回多少年数据（默认 5 年）。
    返回数据按报告期降序排列。

    典型场景：财务分析、ROE/利润趋势分析、估值时调用。
    """
```

#### Tool 8: `get_financial_report_summary`

获取个股最新一期财报的关键科目。

```python
def get_financial_report_summary(
    stock_code: str,
    report_period: str | None = None
) -> dict:
    """
    获取个股指定报告期的财报关键科目摘要。

    report_period 格式 "YYYY-MM-DD"，必须是 0331/0630/0930/1231。
    为 None 时返回最新一期。

    返回三大表关键科目：
    - 利润表：营收、毛利、营业利润、净利润、扣非净利润、研发费用、销售费用
    - 资产负债表：总资产、总负债、股东权益、货币资金、应收账款、存货、商誉
    - 现金流量表：经营性现金流、投资性现金流、筹资性现金流、自由现金流

    典型场景：财报分析、深度研究时调用。
    """
```

## 3. MVP 不包含的功能（明确排除）

下面列出的功能**已经被讨论过、但被推迟到后续版本**，避免范围蔓延：

| 功能 | 推迟到 | 原因 |
|------|--------|------|
| 龙虎榜数据 | v0.2 | 数据更新慢、非高频需求 |
| 股东户数 / 十大流通股东 | v0.2 | 同上 |
| 北上资金流向 | v0.2 | 数据源不稳定 |
| 大宗交易 | v0.2 | 利基场景 |
| 港股 / 美股数据 | v1.0+ | MVP 聚焦 A 股 |
| 期货 / 期权 / 可转债 | v1.0+ | 用户群不同 |
| ETF / 基金数据 | v0.3 | 不同 server |
| 实时 tick 数据 | 不做 | 数据量过大，akshare 不稳定 |
| 财报 PDF 下载 / 解析 | 不做 | 不在数据获取 server 范围 |
| 估值计算（PE/PB 给具体股) | v0.2，独立 server | 见 `stock-valuation` |
| 产业链分析 | v0.3，独立 server | 见 `financial-research` |
| 内容生成 / 排版 | v0.3+，独立 server | 见 `xhs-formatter` |
| 数据可视化 / 图表生成 | 永不做 | 交给上层 |

## 4. 验收标准（DoD - Definition of Done）

MVP 完成的硬指标：

### 4.1 功能验收

- 8 个 tool 全部实现并通过单元测试
- 每个 tool 至少 3 个真实数据集成测试用例
- 在 Claude Desktop 中实测：用户用自然语言调用每个 tool 都能成功
- 错误处理覆盖所有标准错误码（INVALID_PARAM / NOT_TRADING_DAY 等）

### 4.2 工程验收

- 测试覆盖率 ≥ 80%
- ruff lint 0 warning
- mypy strict mode 通过
- CI 全绿
- 包大小 < 50MB
- 冷启动 < 2 秒

### 4.3 文档验收

- README.md 完整（含中英双语介绍、安装、配置、3 个 quick start 示例）
- docs/TOOLS.md 列出所有 8 个 tool 的完整签名 + 示例
- docs/EXAMPLES.md 包含 5 个端到端使用场景
- CHANGELOG.md v0.1.0 条目完整

### 4.4 发布验收

- GitHub Release v0.1.0 发布
- PyPI 上 `finmcp-a-stock-data` 可 `pip install`
- 提交到 MCP Registry（如已开放）
- 至少 1 篇社交媒体公告（即刻 / Twitter / Xhs）

## 5. 时间规划

**MVP 总工期：3 周（21 天）**

| 阶段 | 时长 | 任务 |
|------|------|------|
| **Week 1** | 7 天 | 仓库脚手架 + shared 包 + 8 个 tool 的接口骨架（无实现） |
| **Week 2** | 7 天 | 8 个 tool 的实现 + 缓存 + 错误处理 |
| **Week 3** | 7 天 | 测试补齐 + 文档 + 打包发布 + 内测 |

具体到天的拆分由 Claude Code 在 Handoff 阶段安排。

## 6. 验证用例（Test Cases）

以下 10 个真实场景，**必须在 Claude Desktop 中实测通过**：

| # | 用户问题 | 期望 Claude 调用 |
|---|----------|------------------|
| 1 | 茅台最近五年 ROE 怎么样？ | `search_stocks_by_name("茅台")` + `get_financial_indicator("600519", ["roe"], 5)` |
| 2 | 半导体板块有哪些龙头股？ | `list_industry_constituents(industry_name="半导体", level=1)` |
| 3 | 宁德时代今天涨了多少？ | `search_stocks_by_name("宁德时代")` + `get_latest_quote("300750")` |
| 4 | 上证指数最近一个月走势 | `get_index_price("000001.SH", ...)` |
| 5 | 比亚迪 2024 年报营收多少？ | `get_financial_report_summary("002594", "2024-12-31")` |
| 6 | 隆基绿能上市以来走势 | `get_stock_price("601012", start_date="2012-04-11", ...)` |
| 7 | 五粮液和茅台 ROE 对比 | 两次 `get_financial_indicator` |
| 8 | 中证 500 最近三年走势 | `get_index_price("000905.SH", ...)` |
| 9 | 招商银行的所属行业 | `get_stock_basic_info("600036")` |
| 10 | 600519 这家公司是做什么的 | `get_stock_basic_info("600519")` |

## 7. MVP 反例（不要做的事）

为了避免 Claude Code 过度发挥，明确**不要做**：

- 不要做命令行 entry point（除了 `python -m finmcp_a_stock_data`）
- 不要做配置文件加载（环境变量足够）
- 不要做插件机制
- 不要做异步并发优化（同步阻塞 OK，akshare 本身是同步的）
- 不要做 i18n
- 不要做"漂亮"的 logging（标准 logging 足够）
- 不要在 tool 中做任何数据可视化（不返回图表）
- 不要在文档中堆 emoji / 营销话术

---

## 8. 给 Claude Code 的提示

MVP 阶段，**所有不确定的地方按以下顺序决策**：

1. 优先看本文档（`4_MVP_SCOPE.md`）
2. 再看 `3_TECH_ARCHITECTURE.md`
3. 再看 `2_MCP_TOOLKIT_SPEC.md`
4. 都没说的，看 `5_CLAUDE_CODE_HANDOFF.md`
5. 还没有，**停下来问用户，不要自己发挥**

文档之间冲突时，**MVP_SCOPE 优先级最高**（更具体）。
