# finmcp-a-stock-data Tools 参考

所有工具返回统一结构：`{ok, data, meta}` 或 `{ok, error, meta}`。

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

## 错误码

| Code | 含义 | 建议 |
|---|---|---|
| `INVALID_PARAM` | 参数格式错误 | 检查参数格式 |
| `DATA_NOT_FOUND` | 数据不存在 | 换参数或换日期 |
| `RATE_LIMITED` | 上游限流 | 等 30-60 秒重试 |
| `UPSTREAM_ERROR` | 上游故障 | 稍后重试 |
| `NOT_TRADING_DAY` | 非交易日 | 换最近交易日 |
| `AUTH_REQUIRED` | 需要 API key | 配置 TUSHARE_TOKEN |
| `INTERNAL_ERROR` | 内部错误 | 提交 issue |
