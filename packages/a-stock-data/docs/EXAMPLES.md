# 使用场景示例

以下 5 个场景展示 finmcp-a-stock-data 在 Claude Desktop 中的典型使用方式。

## 场景 1：查询公司财务趋势

**用户**：茅台最近五年 ROE 怎么样？

**Claude 自动调用**：
1. `search_stocks_by_name(query="茅台")` → 得到 600519.SH
2. `get_financial_indicator(stock_code="600519", indicators=["roe"], years=5)` → 5 年 ROE 数据

**Claude 回答**（基于真实数据）：贵州茅台近五年 ROE 保持在 28%-31% 区间，远高于 A 股平均水平...

## 场景 2：了解板块成份

**用户**：半导体板块有哪些龙头股？

**Claude 自动调用**：
1. `list_industry_constituents(industry_name="半导体")` → 成份股列表

**Claude 回答**：申万半导体行业共 XX 只成份股，市值较大的包括...

## 场景 3：实时行情查询

**用户**：宁德时代今天涨了多少？

**Claude 自动调用**：
1. `search_stocks_by_name(query="宁德时代")` → 得到 300750.SZ
2. `get_latest_quote(stock_code="300750")` → 实时报价

**Claude 回答**：宁德时代（300750.SZ）当前价 XXX 元，今日涨跌 X.XX%...

## 场景 4：大盘走势分析

**用户**：上证指数最近一个月走势如何？

**Claude 自动调用**：
1. `get_index_price(index_code="000001.SH", start_date="2026-04-15", end_date="2026-05-15")` → 日线数据

**Claude 回答**：上证指数近一个月从 XXXX 点到 XXXX 点，期间振幅 X%...

## 场景 5：财报深度分析

**用户**：比亚迪 2024 年报营收多少？利润率怎么样？

**Claude 自动调用**：
1. `search_stocks_by_name(query="比亚迪")` → 得到 002594.SZ
2. `get_financial_report_summary(stock_code="002594", report_period="2024-12-31")` → 三大表数据
3. `get_financial_indicator(stock_code="002594", indicators=["net_margin", "gross_margin"], years=3)` → 利润率趋势

**Claude 回答**：比亚迪 2024 年报营收 XXXX 亿元，净利润 XXX 亿元，净利率 X.X%...
