# finmcp-a-stock-data Tools 参考

所有工具返回统一结构：`{ok, data, meta}` 或 `{ok, error, meta}`。

meta 通用字段（契约 v1.1+，SPEC F1）：`source` / `fetched_at` / `cache_hit` /
`contract_version` / `empty_reason`（空数据语义：`confirmed_absent`=上游确认无记录，
`unknown`=无法排除上游故障）；多级数据源工具另带 `attempts`（逐级留痕），
附属字段富化失败时带 `partial_fields`。
`FINMCP_CONTRACT=v2` 启用严格三态（上游全挂 → `ok:false`），默认 v1 保持历史行为。

## 1. `search_stocks_by_name`

按公司名称模糊搜索 A 股股票。

```python
search_stocks_by_name(query: str, limit: int = 10) -> dict
```

**参数**：
- `query`：搜索关键词，支持中文名、简称、拼音首字母（如 "mt"）
- `limit`：返回数量上限，默认 10，最大 100

**返回示例**：

```json
{
  "ok": true,
  "data": [
    {
      "stock_code": "600519.SH",
      "name": "贵州茅台",
      "industry": "白酒",
      "market_cap_yi": null
    }
  ],
  "meta": {"source": "tushare", "fetched_at": "2026-05-15T23:25:53+08:00", "cache_hit": false}
}
```

## 2. `get_stock_basic_info`

获取个股基础信息。

```python
get_stock_basic_info(stock_code: str) -> dict
```

**参数**：
- `stock_code`：股票代码，支持 `"600519"` 或 `"600519.SH"`

**返回示例**：

```json
{
  "ok": true,
  "data": {
    "stock_code": "600519.SH",
    "name": "贵州茅台",
    "full_name": "贵州茅台酒股份有限公司",
    "english_name": "Kweichow Moutai Co.,Ltd.",
    "industry_l1": "白酒",
    "list_date": "20010827",
    "total_share": 125227.02,
    "float_share": 125227.02,
    "area": "贵州"
  }
}
```

## 3. `list_industry_constituents`

列出申万行业分类下的所有成份股。

```python
list_industry_constituents(
    industry_code: str | None = None,
    industry_name: str | None = None,
    level: int = 1
) -> dict
```

**参数**：
- `industry_code`：申万行业代码（如 `"801120.SI"`）
- `industry_name`：行业名称关键词（如 `"白酒"`、`"半导体"`）
- `level`：1/2/3 对应一级/二级/三级分类

`industry_code` 和 `industry_name` 至少提供一个。如果指定级别找不到，自动搜索其他级别。

## 4. `get_stock_price`

获取个股历史行情。

```python
get_stock_price(
    stock_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily",
    adjust: str = "qfq"
) -> dict
```

**参数**：
- `stock_code`：股票代码
- `start_date` / `end_date`：YYYY-MM-DD 格式，默认最近 60 个交易日
- `period`：`daily` / `weekly` / `monthly`
- `adjust`：`qfq`（前复权） / `hfq`（后复权） / `none`

**返回字段**：date, open, high, low, close, volume, amount, pct_change, turnover_rate

## 5. `get_latest_quote`

获取个股实时报价快照。

```python
get_latest_quote(stock_code: str) -> dict
```

**返回示例**：

```json
{
  "ok": true,
  "data": {
    "stock_code": "600519.SH",
    "name": "贵州茅台",
    "current_price": 1332.95,
    "change": -9.22,
    "pct_change": -0.69,
    "open": 1335.15,
    "high": 1339.28,
    "low": 1327.11,
    "prev_close": 1342.17,
    "volume": 58183.65,
    "amount": 7749366.54,
    "market_cap_yi": 16692.14,
    "pe_ttm": 20.18,
    "pb": 6.16
  }
}
```

缓存 TTL 60 秒。

## 6. `get_index_price`

获取指数历史行情。

```python
get_index_price(
    index_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily"
) -> dict
```

**参数**：
- `index_code`：必须带交易所后缀（如 `000001.SH`）

常见指数代码：

| 代码 | 名称 |
|---|---|
| 000001.SH | 上证指数 |
| 399001.SZ | 深证成指 |
| 399006.SZ | 创业板指 |
| 000300.SH | 沪深300 |
| 000905.SH | 中证500 |
| 000852.SH | 中证1000 |

## 7. `get_financial_indicator`

获取个股核心财务指标。

```python
get_financial_indicator(
    stock_code: str,
    indicators: list[str] | None = None,
    years: int = 5
) -> dict
```

**支持的 indicators**：

| 分类 | 指标 |
|---|---|
| 盈利 | roe, roa, gross_margin, net_margin |
| 成长 | revenue_yoy, net_profit_yoy |
| 偿债 | debt_to_asset, current_ratio |
| 运营 | asset_turnover, inventory_turnover |
| 估值 | pe_ttm, pb, ps_ttm |
| 其他 | eps, bvps, ocf_per_share |

`indicators=None` 返回全部。

## 8. `get_financial_report_summary`

获取财报关键科目摘要。

```python
get_financial_report_summary(
    stock_code: str,
    report_period: str | None = None
) -> dict
```

**参数**：
- `report_period`：季度末日期（`2024-12-31` / `2024-09-30` / `2024-06-30` / `2024-03-31`），`None` 返回最新一期

**返回字段**：

- 利润表：revenue, gross_profit, operating_profit, net_profit, net_profit_deducted, rd_expense, selling_expense
- 资产负债表：total_assets, total_liabilities, equity, cash, accounts_receivable, inventory, goodwill
- 现金流量表：operating_cashflow, investing_cashflow, financing_cashflow, free_cashflow

金额单位：元（人民币）。

## 9. `list_concept_stocks`

按概念/题材名称搜索相关 A 股股票（同花顺概念 → tushare 概念 → 关键词搜索三级瀑布）。

```python
list_concept_stocks(concept_name: str, limit: int = 20) -> dict
```

**参数**：
- `concept_name`：概念名称（如"存储芯片""AI芯片""算力租赁"）
- `limit`：返回数量上限，默认 20，最大 50

**返回**：`data` 为 `[{stock_code, name, concept}]`；逐级尝试结果见 `meta.attempts`。

## 10. `get_industry_overview`

批量获取行业全景：成份股行情、估值分布与排名。

```python
get_industry_overview(industry_name: str, level: int = 2, sort_by: str = "market_cap", limit: int = 50) -> dict
```

**参数**：
- `industry_name`：申万行业名称（如"半导体""白酒"）
- `level`：申万层级 1/2/3，默认 2
- `sort_by`：排序字段（market_cap 等）
- `limit`：返回成份股数量上限

## 11. `get_stock_news`

获取个股公告（巨潮公告检索 + 东财公告 API 双源聚合）。**注意：数据为公告，非 7x24 新闻快讯。**

```python
get_stock_news(stock_code: str, days: int = 30) -> dict
```

**参数**：
- `stock_code`：股票代码（如 688256.SH）
- `days`：查询天数，默认 30，最大 90

**返回**：`data` 为 `{stock_code, period, announcements, announcements_em, market_news}`；
`market_news` 是 `announcements_em` 的过渡别名（历史字段名，内容为东财公告），后续版本移除。
各源成败见 `meta.attempts`（源名 `cninfo_ann` / `eastmoney_ann`）；
`announcements` 来自巨潮公告检索（原 tushare anns_d 无接口权限，F3 换源，字段 `{date, title, source}` 不变）。

## 12. `get_market_signals`

获取个股近期市场异动信号（涨跌停 + 龙虎榜）。

```python
get_market_signals(stock_code: str, days: int = 5) -> dict
```

**参数**：
- `stock_code`：股票代码
- `days`：查询天数，默认 5，最大 30

**返回**：`data` 为 `{stock_code, period, limit_events, toplist_events, has_signals, fields_unavailable, note}`。
`has_signals` 三值语义：`true`=有异动；`false`=查询成功且确认无记录；`null`=上游查询全部失败（未知，不等于无异动）。

涨跌停事件由 pro_bar 日线 `|pct_chg|` 阈值判定（limit_list_d 无接口权限，F3 换源）：
688/689/300/301=20%，北交 8xx/4xx=30%，其余=10%，判定线为阈值-0.15。
该源不含封板细节，`open_times`/`first_time` 恒为 `null` 且由 `fields_unavailable` 显式标注；
ST 股 5% 阈值无法从代码判定，可能漏检（见 `note`）。attempts 源名 `tushare_probar_limit` / `tushare_top_list`。

## 13. `get_company_profile`

获取公司主营业务/经营范围/公司介绍（tushare stock_company 直调）。
用于识别公司战略叙事（转型/新业务方向），避免被单条新闻误导。

```python
get_company_profile(stock_code: str) -> dict
```

**返回**：`data` 为 `{stock_code, main_business, business_scope, introduction}`
（introduction 截断至 500 字，business_scope 截断至 400 字）。

## 14. `get_annual_report_mdna`

年报 MD&A 战略抽取：巨潮定位最新年报 PDF → pdfplumber 解析 → 切"管理层讨论与分析"
→ 战略关键词段落抽取（约 2.5K 字），90 天缓存（CacheManager quarterly 档）。

```python
get_annual_report_mdna(stock_code: str) -> dict
```

**依赖**：optional extras `disclosure`（`pip install 'finmcp-a-stock-data[disclosure]'`），
未安装 pdfplumber 返回 `NOT_SUPPORTED`。

**返回**：`data` 为 `{report_year, report_date, mdna_excerpt, from_cache}`。

## 15. `get_earnings_forecast`

业绩预告（tushare forecast）：预增/预减/扭亏 + 净利润区间 + 变动原因。

```python
get_earnings_forecast(stock_code: str) -> dict
```

**返回**：`data.forecasts` 为
`[{ann_date, end_date, type, p_change_min, p_change_max, net_profit_min_yi, net_profit_max_yi, change_reason, summary}]`（最多 5 条）。

**单位口径**：tushare 原始 `net_profit_min/max` 单位为万元，`/10_000` 换算为亿元
（已对原始数据独立核实，见仓库 `docs/EARNINGS_FORECAST_UNIT_VERIFICATION.md`）。

## 16. `get_investor_qa`

投资者互动问答（akshare）：深市走互动易（stock_irm_cninfo），沪市走上证 e 互动（stock_sns_sseinfo）。

```python
get_investor_qa(stock_code: str, limit: int = 15) -> dict
```

**依赖**：optional extras `akshare`，未安装返回 `NOT_SUPPORTED`。

**返回**：`data.qa` 为问答记录列表（列名为 akshare 原始中文列）。
上证 e 互动失败为显式失败（v2 契约 `ok:false`；v1 `empty_reason=unknown`），不伪装成"无问答"。

## 17. `get_major_shareholder_change`

大股东增减持（tushare stk_holdertrade）：减持=利空信号、增持=偏多信号。

```python
get_major_shareholder_change(stock_code: str) -> dict
```

**返回**：`data` 为 `{changes: [{ann_date, holder, direction, change_vol_yi, change_ratio_pct, after_ratio_pct, avg_price}], net_change_yi_total, note}`（最多 20 条）。

## 18. `get_pledge_status`

股票质押状态（tushare pledge_stat）：高质押率=黑天鹅前兆。

```python
get_pledge_status(stock_code: str) -> dict
```

**返回**：`data` 为最新一期 `{end_date, pledge_count, unrest_pledge_yi, rest_pledge_yi, total_share_yi, pledge_ratio_pct, note}`；无质押数据时 `{latest: null, note}` + `confirmed_absent`。

## 19. `get_broker_ratings`

券商研报评级 + 目标价（akshare 东财研报）。

```python
get_broker_ratings(stock_code: str, limit: int = 10) -> dict
```

**依赖**：optional extras `akshare`，未安装返回 `NOT_SUPPORTED`。

**返回**：`data` 为 `{reports: [...], third_party_opinion: true}`。
评级/目标价为**第三方机构观点**（`third_party_opinion` 标注），底座原样透传，
是否向最终用户展示由各产品合规层过滤（SPEC §1 硬边界）。

## 20. `get_buyback`

公司回购（akshare 东财回购，全市场数据本地按代码过滤）。回购=偏多催化。

```python
get_buyback(stock_code: str) -> dict
```

**依赖**：optional extras `akshare`，未安装返回 `NOT_SUPPORTED`。

**返回**：`data.buybacks` 为回购记录列表（最多 5 条，列名为 akshare 原始中文列）。

## 21. `get_industry_operating_evidence`

行业市值前列样本的同期年报经营指标（有界样本证据层，不冒充全行业总量）。

```python
get_industry_operating_evidence(industry_name: str, level: int = 2, sample_limit: int = 5) -> dict
```

**返回**：`data` 为聚合证据
`{evidence_version, evidence_type, status, report_period, selection, metrics, sample_entities, unavailable_direct_series, boundary}`；
共同年报期样本 < 2 家时 `status=insufficient_evidence`，不输出样本中位数。

## 22. `get_money_flow`

主力资金流：东财实时（当日盘中 + 历史序列 + 连续吸筹/流出天数）优先，风控/异常回退 tushare EOD。

```python
get_money_flow(stock_code: str, days: int = 10) -> dict
```

**返回**（东财实时路径）：`data` 为 `{stock_code, today_realtime, daily_series, main_inflow_streak_days, note}`；
（tushare 回退路径）：`{flows_recent, total_main_net_yi_recent, note}`。
两级尝试见 `meta.attempts`（`eastmoney_realtime` / `tushare_moneyflow`），全挂 `ok:false`。金额单位亿元。

## 23. `get_market_snapshot`

大盘实时快照：四大指数涨跌 + 全市场涨跌家数（市场宽度）+ 两市成交额（东财实时）。

```python
get_market_snapshot() -> dict
```

**返回**：`data` 为 `{indices, market_breadth: {up, down, flat}, total_amount_yi, quote_time}`。
涨跌家数 = 上证（沪市）+ 深证综指（深市）口径。

## 24. `get_sector_ranking`

当日板块主力资金排行（流入榜 + 流出榜），或按板块名点查（东财实时）。

```python
get_sector_ranking(top_n: int = 10, board_type: str = "industry", board_names: str = "") -> dict
```

**参数**：
- `board_type`：`industry`（行业）/ `concept`（概念）
- `board_names`：逗号分隔的板块名点查（如 `"银行,电力"`），跨行业+概念模糊匹配；空 = 返回排行榜

**返回**（榜单）：`data` 为 `{board_type, top_inflow, top_outflow, note}`；
（点查）：`{queried, boards, note}`。盘前资金流未生成时显式 `DATA_NOT_FOUND`，不混入 None 排序。

## 25. `list_stock_concepts`

个股 → 概念反查。**当前状态: NOT_SUPPORTED**——2026-09-02 实调确认 tushare
concept_detail 接口已下线、ths_index/ths_member 无账号权限，暂无可靠反查源。
调用恒返回 `ok:false, code=NOT_SUPPORTED`（显式不可用，不返回伪造结果）；
数据源接通列入 F5。正向查询（概念→成份股）用 `list_concept_stocks`。

```python
list_stock_concepts(stock_code: str) -> dict
```

## 错误码

| Code | 含义 | 建议 |
|---|---|---|
| `INVALID_PARAM` | 参数格式错误 | 检查参数格式 |
| `DATA_NOT_FOUND` | 数据不存在 | 换参数或换日期 |
| `RATE_LIMITED` | 上游限流 | 等 30-60 秒重试 |
| `UPSTREAM_ERROR` | 上游故障 | 稍后重试 |
| `NOT_TRADING_DAY` | 非交易日 | 换最近交易日 |
| `AUTH_REQUIRED` | 需要 API key | 配置 TUSHARE_TOKEN |
| `NOT_SUPPORTED` | 缺 optional 依赖 | 安装对应 extras（akshare / disclosure） |
| `INTERNAL_ERROR` | 内部错误 | 提交 issue |
