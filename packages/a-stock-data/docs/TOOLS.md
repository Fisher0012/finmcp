# finmcp-a-stock-data Tools

## 基础信息类

### 1. `search_stocks_by_name`

按公司名称模糊搜索 A 股股票。

```python
search_stocks_by_name(query: str, limit: int = 10) -> dict
```

### 2. `get_stock_basic_info`

获取个股基础信息。

```python
get_stock_basic_info(stock_code: str) -> dict
```

### 3. `list_industry_constituents`

列出申万行业分类下的所有成份股。

```python
list_industry_constituents(
    industry_code: str | None = None,
    industry_name: str | None = None,
    level: int = 1
) -> dict
```

## 行情数据类

### 4. `get_stock_price`

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

### 5. `get_latest_quote`

获取个股实时报价快照。

```python
get_latest_quote(stock_code: str) -> dict
```

### 6. `get_index_price`

获取指数历史行情。

```python
get_index_price(
    index_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "daily"
) -> dict
```

## 财务数据类

### 7. `get_financial_indicator`

获取个股核心财务指标。

```python
get_financial_indicator(
    stock_code: str,
    indicators: list[str] | None = None,
    years: int = 5
) -> dict
```

### 8. `get_financial_report_summary`

获取财报关键科目摘要。

```python
get_financial_report_summary(
    stock_code: str,
    report_period: str | None = None
) -> dict
```

---

> 详细参数说明和返回示例将在 Stage 3 补充。
