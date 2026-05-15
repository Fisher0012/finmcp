# Changelog

## [0.1.0] - 2026-05-15

### Added

- 8 个 MCP tool：search_stocks_by_name, get_stock_basic_info, list_industry_constituents,
  get_stock_price, get_latest_quote, get_index_price, get_financial_indicator, get_financial_report_summary
- Tushare Pro 数据源完整实现（需 TUSHARE_TOKEN）
- Akshare 数据源接口预留（待实现）
- diskcache 本地缓存（按数据类型区分 TTL）
- 股票代码自动归一化（600519 → 600519.SH）
- 拼音首字母搜索（pypinyin）
- 申万行业分类跨级别自动搜索
- 统一错误码（INVALID_PARAM / DATA_NOT_FOUND / RATE_LIMITED / UPSTREAM_ERROR 等）
- 90 个单元测试 + 20 个集成测试
