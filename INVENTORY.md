# FinMCP (a-stock-data) 只读盘点 INVENTORY

盘点日期: 2026-09-02 · 盘点方式: 只读（未修改/删除任何既有文件，未执行 git 写操作）
盘点范围: 本仓库 `/Users/donnie/projects/finmcp`，以代码为准，不以文档为准。
标注约定: 【已验证】= 盘点中亲自读代码/跑命令确认；【未验证】= 推断或仅有文档声称。
发现的问题只记录，不修复。

---

## 0. 问题速览（按严重度）

1. **4 个已实现工具未注册进 MCP server**：`get_stock_news` / `get_market_signals` / `get_industry_overview` 未在 server.py 注册；`list_concept_stocks` 已注册但所有文档均未记载。这些函数被 workbench 以 Python 库方式直接 import 使用（`workbench/routers/finmcp.py:53-61`），所以"作为库可用，作为 MCP tool 不可用"。【已验证】
2. **CI 自 2026-05 起全红**：最近 5 次 run 全部 failure（最后一次 2026-05-23），卡在 Ruff check；本地复现 4 个 lint 错误（tushare_src.py:680 B905、:734 E501、test_realtime.py:3 I001 在已提交代码中；concept.py:8 F401 来自未提交改动）。【已验证；GitHub 原始日志已过期(410)，失败根因由本地 ruff 复现推断，该推断部分未验证】
3. **新闻/概念/异动三类存在系统性静默降级**：上游全挂时返回 `ok:true` + 空列表，与"确实没有数据"不可区分（详见 § 4）。【已验证】
4. **news/signals/overview 三方法只存在于 TushareSource**，未进 base.py 抽象基类，AkshareSource 未实现；若运行时落到 akshare 源（无 TUSHARE_TOKEN 的默认），调用将 AttributeError → INTERNAL_ERROR。【代码层已验证；运行时行为未实际触发，未验证】
5. **AkshareSource 全部 8 个方法 `raise NotImplementedError`**（akshare_src.py:11-67），README 宣称"默认 akshare"实际不可用，唯一可用数据源是 tushare。【已验证】
6. **工作区不干净**：`packages/a-stock-data/src/finmcp_a_stock_data/tools/concept.py` 有 +191/-43 未提交改动（同花顺概念爬取整层）。因包为 editable 安装，**这份未提交代码就是本机实际运行版本，丢失即功能回退**。【已验证】
7. **名实不符**：`_fetch_eastmoney_news`（tushare_src.py:803-843）docstring 称"东财 7x24 快讯"，实际调用东财**公告** API（np-anotice-stock），返回字段却叫 `market_news`；且该请求关闭了 SSL 验证（:820-821）。【已验证】
8. **新功能零测试**：concept 同花顺逻辑、news、signals、industry_overview 无任何测试（grep 无命中）。【已验证】

---

## 1. 工具完整清单（以代码为准）

MCP 注册处唯一：`packages/a-stock-data/src/finmcp_a_stock_data/server.py:24-32`，共注册 **9 个** tool。仓库根的 serve_mcp.py / serve_http.py 不存在（那是另一个仓 xiaocai-stock-ai 的文件）。【已验证】

| # | Tool | 参数 | 功能 | 定义位置 |
|---|---|---|---|---|
| 1 | `search_stocks_by_name` | query, limit=10 | 按名称/拼音/同音字/中英混合搜股票 | tools/search.py:23 |
| 2 | `get_stock_basic_info` | stock_code | 个股基础信息（行业/上市日/股本） | tools/basic.py:24 |
| 3 | `list_industry_constituents` | industry_code, industry_name, level=1 | 申万行业成份股 | tools/industry.py:72 |
| 4 | `list_concept_stocks` | concept_name, limit=20 | 概念/题材板块成份股 | tools/concept.py:168 |
| 5 | `get_stock_price` | stock_code, start_date, end_date, period, adjust | 历史行情（日/周/月，复权） | tools/price.py:25 |
| 6 | `get_latest_quote` | stock_code | 实时快照（新浪优先） | tools/quote.py:58 |
| 7 | `get_index_price` | index_code, start_date, end_date, period | 指数历史行情 | tools/index.py:24 |
| 8 | `get_financial_indicator` | stock_code, indicators, years=5 | 核心财务指标（ROE 等 16 项） | tools/financial.py:35 |
| 9 | `get_financial_report_summary` | stock_code, report_period | 三大表关键科目摘要 | tools/financial.py:92 |

**代码有、MCP 未注册**（server.py 未 import）：【已验证】
- `get_stock_news(stock_code, days=30)` — tools/news.py:27
- `get_market_signals(stock_code, days=5)` — tools/news.py:55
- `get_industry_overview(industry_name, level=2, sort_by, limit=50)` — tools/industry.py:23

**文档 vs 代码偏差**：【已验证】
- docs/TOOLS.md 与 README.md:54-71 均只列 8 个（缺 list_concept_stocks）。
- 代码有文档无：`list_concept_stocks`、`get_stock_news`、`get_market_signals`、`get_industry_overview`（4 个，全部文档零命中）。
- 文档有代码无：无。
- workbench 侧注释掉的 `get_dividend_history` / `get_northbound_flow` 在本仓不存在，属计划未实现。

---

## 2. 每个 tool 的数据源

数据源选择：`utils.py:12 get_data_source()` — 有 `TUSHARE_TOKEN` 环境变量即 TushareSource，否则 AkshareSource（后者全部方法 NotImplementedError，实际唯一可用源是 tushare）。【已验证】

| Tool | 数据源（模块+函数） |
|---|---|
| search_stocks_by_name | tushare `pro.stock_basic` + 本地 pypinyin 过滤（tushare_src.py:46-131） |
| get_stock_basic_info | tushare `stock_basic` + `daily_basic` 补股本（:133-185） |
| list_industry_constituents | tushare `index_classify(src="SW2021")` + `index_member`（:355-428） |
| list_concept_stocks | 三级瀑布：① 同花顺网页爬取 `q.10jqka.com.cn/gn/`（concept.py:43-165，urllib 直连+正则解析 GBK HTML）→ ② tushare `concept`/`concept_detail`（:216-235）→ ③ `search_stocks` 关键词兜底（:238-258） |
| get_stock_price | tushare `ts.pro_bar`（tushare_src.py:187-241） |
| get_latest_quote | 新浪 `hq.sinajs.cn`（realtime.py:52）优先 → tushare `pro_bar` 回退（:243）；PE/PB/市值由 `daily_basic` 补充（quote.py:32-55） |
| get_index_price | tushare `index_daily`（:316） |
| get_financial_indicator | tushare `fina_indicator` + `daily_basic` 估值（:430-533） |
| get_financial_report_summary | tushare `income`/`balancesheet`/`cashflow`（:535-644） |
| get_stock_news（未注册） | tushare `anns_d`（:777）+ 东财公告 API（:803，docstring 误称快讯，SSL 验证关闭） |
| get_market_signals（未注册） | tushare `limit_list_d` 逐日轮询（:863）+ `top_list` 龙虎榜（:895） |
| get_industry_overview（未注册） | `index_classify/index_member` + `daily_basic` 批量 join（:648-756） |

---

## 3. 缓存策略【已验证】

- 实现：`cache.py` — diskcache（sqlite 落盘），目录 `~/.finmcp/cache`（FINMCP_CACHE_DIR 可覆盖），懒初始化。
- TTL（cache.py:14-19）：realtime **60 秒**（env 可覆盖）/ daily **7 天** / basic_info **30 天** / financial **1 天**。
- 走缓存：9 个注册 tool 全部 + get_industry_overview + 同花顺概念中间结果。
- **不走缓存**：get_stock_news、get_market_signals（news.py 无 CacheManager）。
- 防坏缓存：concept.py:262-263 结果 <3 条不缓存。
- 实测缓存库 763 条记录（sqlite3 只读查询）。

---

## 4. 失败时的返回行为（逐 tool）

通用模式【已验证】：tool 层统一 `except FinMCPError → error_response(code)`、`except Exception → INTERNAL_ERROR`（errors.py:12-36），响应恒为 `{ok, data/error, meta}`，不向 MCP 层抛异常。数据源层对"取不到"大多显式 `raise DataNotFoundError/UpstreamError`。

**显式失败（行为良好）**：get_stock_basic_info、get_stock_price、get_latest_quote（tushare 回退路径）、get_index_price、get_financial_indicator、get_financial_report_summary（三表全失败 raise DataNotFoundError, tushare_src.py:622）、get_industry_overview（成份股无 → DataNotFoundError :665；daily_basic 5 日全失败 → UpstreamError :703）。【已验证】

**静默降级点名**（事故模式：上游挂了返回 ok+空，与"无数据"不可区分）：【已验证】

| 位置 | 行为 | 严重度 |
|---|---|---|
| concept.py:77-79, 129-131, 212-213, 234-235, 257-258 | 三级数据源逐级 `except → warning → return []/继续`；三级全挂返回 `ok:true, data:[]` | 高 |
| tushare_src.py:799-801, 840-841（get_stock_news） | 双源各自 `except → warning → return []`；全挂返回 ok + 空 announcements/market_news | 高 |
| tushare_src.py:887-888, 919-920（get_market_signals） | 逐日循环内裸 `except Exception: pass`；外层 :891-893/:923-925 再 return []；API 全挂时 `has_signals:false`，语义等同"无异动" | 高 |
| tushare_src.py:285-286, 296-297（quote 回退路径） | 估值失败 debug 跳过；名称失败 `except: pass`，name 静默为 "" | 中 |
| quote.py:54-55 `_enrich_valuation` | 失败仅 debug log，PE/PB/市值静默 None，无"未取到"标注 | 中 |
| tushare_src.py:169-170, :487-488, :681-683 | 附属字段失败静默 None/fallback | 低 |
| tushare_src.py:61（search 空表）、:413（index_member 空） | 空数据 return []（搜索空合理，index_member 空偏可疑） | 低 |

---

## 5. 能力覆盖判定【已验证】

| 能力 | 判定 | 依据 |
|---|---|---|
| 新闻 | **半有**（未注册 MCP） | get_stock_news；"market_news" 字段实为东财公告非快讯 |
| 公告 | **半有**（未注册 MCP） | get_stock_news：tushare anns_d + 东财公告 |
| 政策 | **无** | 无任何相关代码 |
| 宏观经济 | **无** | 无 GDP/CPI/PMI/利率等任何接口 |
| 行业链/产业链 | **无** | 只有申万行业分类和概念板块，无上下游产业链数据 |
| 板块归属 | **部分** | 正向查询有（行业→成份股、概念→成份股）；反向"个股属于哪些板块"只有 basic_info 的 industry_l1（l2/l3 硬编码空字符串, tushare_src.py:154-155,178-179），无个股→概念查询 |
| 资金流向 | **基本无** | 无 moneyflow/北向工具；仅 get_market_signals 龙虎榜含 net_amount/buy/sell（:914-916），且未注册 MCP |

commit 729f37a（新闻公告/异动）与 b402f07（industry_overview）验证结论：代码真实存在且近期跑通过（见 § 7 缓存证据），但从未接线进 MCP server，仅被 workbench 当库用。【已验证】

---

## 6. 测试覆盖【已验证，含实跑】

- 单测：`packages/a-stock-data/tests/unit/` 58 个，全 mock（patch tushare/requests），不需网络。
- 共享库：`shared/tests/` 48 个，纯逻辑。
- 集成：`tests/integration/test_tushare_integration.py` 20 个，整文件 `skipif(not TUSHARE_TOKEN)`，依赖真实网络+token。
- **本次实跑**：unit + shared → **106 passed (0.44s)**；integration → 20 skipped（盘点 shell 无 token）。跑测使用 `-p no:cacheprovider` + `PYTHONDONTWRITEBYTECODE=1` 保证零写盘。
- 覆盖缺口：concept 同花顺逻辑、news、signals、industry_overview 零测试。
- CI：`.github/workflows/ci.yml`（ruff + format + mypy + pytest, py3.10-3.13）；`gh run list` 最近 5 次全 failure（最后 2026-05-23），卡在 Ruff。

---

## 7. 最近一次确认正常运行的记录

- 代码最后 commit：b402f07，2026-05-23 13:32。【已验证】
- **确认运行的磁盘证据**（强于提交记录）：`~/.finmcp/cache/cache.db` mtime **2026-09-01 17:21**，763 条缓存；最新键含 `realtime:quote:300750.SZ`（17:19）、`tushare:industry_overview:计算机设备…`（17:16）、`ths+ts:concept:AI服务器`（17:08）。这些键只在上游成功返回后写入 → 证明 tushare + 同花顺 + 新浪三条链路在 **2026-09-01 下午真实跑通**（含未注册的 get_industry_overview，走 workbench 库调用路径）。【已验证】
- MCP 侧：`~/.claude.json` 在 finmcp 项目下注册了 `finmcp-a-stock-data`（stdio，`python3 -m finmcp_a_stock_data.server`，env 带 TUSHARE_TOKEN）；包为 editable 安装，import 直接解析到仓库 src。【已验证】
- pytest 历史缓存：lastfailed（2026-05-22）残留 1 条 test_stub_tools 失败记录，当前已修复（本次实跑全绿）。【已验证】

---

## 8. 工作区状态【已验证】

- 分支 main，与 origin/main 同步。
- 未提交改动 1 处：`tools/concept.py`（+191/-43，同花顺概念爬取层）。无 untracked 文件。
- 因 editable 安装，该未提交代码即实际运行版本。

## 附: 本次盘点未验证项汇总

- akshare 路径的 AttributeError 为代码推断，未实际无 token 触发。
- CI 失败根因由本地 ruff 复现推断，GitHub 原始日志已过期（410）无法拉取。
- MCP server 以 stdio 实际拉起的端到端连通性本次未测（仅确认注册配置与 editable 安装解析）。
