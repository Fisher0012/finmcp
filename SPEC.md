# FinMCP 底座规格 SPEC v1.0-draft

状态: **v1.0 已生效**——2026-09-02 Donnie 对 F-R1–F-R5（及姊妹规格 R1–R7）全部按建议裁定通过。
建立日期: 2026-09-02 · 作者: Claude（规划会话，未改任何业务代码）
适用范围: `/Users/donnie/projects/finmcp`
姊妹规格: `/Users/donnie/projects/workbench/SPEC.md`（小财看涨跌产品规格）。数据契约两侧视图必须一致：本文 § 2 ↔ 姊妹规格 § 6。已知不一致处全部收敛到 § 7 待裁定项，无隐藏冲突。

标注约定: 【已验证】/【推断】/【未验证】/【待裁定】，同姊妹规格。
事实基础: 本仓 `INVENTORY.md`（2026-09-02 只读盘点，106 项单测实跑）+ workbench 消费面调查。

---

## 1. 定位与边界

FinMCP 是**两个产品（小财看涨跌 / 小财机器人）的共用底座**，只做两件事：

1. **数据接入**: 行情 / 财报 / 公告 / 新闻 / 政策 / 宏观的获取与缓存。
2. **事实计算**: 指标、比率、估值、检索等确定性计算。

**硬边界（不做）**:
- **不含观点**: 不输出任何判断、评级结论、建议、方向词。第三方事实中天然含观点的字段（如券商评级、目标价）原样透传并在 schema 中标注 `third_party_opinion: true`，过滤责任归各产品合规层。
- **不做渲染**: 输出恒为结构化 JSON，不产出面向用户的文案。
- **不做合规过滤**: 股票代码、涨跌幅等原始事实完整返回；删不删是产品层的事。
- **不感知调用方**: 同一契约同时服务小程序（无代码/无建议产品）与机器人（操作建议产品），不为任一方定制语义。

消费形态：MCP server（stdio）+ **Python 库直接 import**（workbench 走后者，editable 安装【已验证】）。两种形态必须暴露同一套工具与同一封套。

---

## 2. 统一失败返回规范（最高优先级改造）

> 与姊妹规格 § 6.1 逐字一致。此节是决策 4（数据失败必须显式）在底座侧的落地，也是消灭 2026-08 "静默降级连环事故"模式的结构性方案。

### 2.1 三态封套

```json
{
  "ok": true,
  "data": "<工具各自 schema> | null",
  "error": "null | {code, message, upstream}",
  "meta": {
    "source": "tushare|sina|eastmoney|cninfo|akshare|local_db",
    "as_of": "<数据时点 ISO8601>",
    "cache_hit": false,
    "empty_reason": "null | confirmed_absent | unknown",
    "contract_version": "<语义化版本>"
  }
}
```

- `ok:true` + data 非空 = 取到。
- `ok:true` + data 空 + `empty_reason="confirmed_absent"` = 上游正常响应且明确无记录（**否定性断言必须有正面数据支撑**：HTTP 200 + 明确空结果集才算，超时/异常/解析失败都不算）。
- `ok:false` + error = 失败。错误码: `UPSTREAM_ERROR | DATA_NOT_FOUND | TIMEOUT | RATE_LIMITED | INVALID_PARAM | NOT_SUPPORTED | INTERNAL_ERROR`。
- **禁止形态**: `except → warning → return []`、`except: pass`、任何把上游异常折叠为 `ok:true + 空` 的路径。
- 多级数据源瀑布（如概念三级）：每级尝试结果记入 `meta.attempts[{source, outcome}]`；全挂 = `ok:false, code=UPSTREAM_ERROR`。
- 附属字段富化失败（如 quote 的 PE/PB）：主数据照常返回，失败字段值为 `null` 且 `meta.partial_fields=["pe","pb"]` 显式列出，不得无标注静默 None。

### 2.2 现有静默降级点改造清单（源自 INVENTORY § 4，全部【已验证】）

| 位置 | 现行为 | 目标行为 |
|---|---|---|
| concept.py:77-79,129-131,212-213,234-235,257-258 | 三级逐级吞异常，全挂返回 ok:true+[] | meta.attempts 留痕；全挂 ok:false |
| tushare_src.py:799-801,840-841（get_stock_news） | 双源各自吞异常返回 [] | 每源结果留痕；双源全挂 ok:false |
| tushare_src.py:887-888,919-920（get_market_signals） | 逐日循环裸 except pass；全挂时 `has_signals:false` 语义等同"无异动" | 失败日计数入 meta；全部失败 ok:false，`has_signals:false` 仅在成功查询后无记录时返回 + confirmed_absent |
| tushare_src.py:285-286,296-297 + quote.py:54-55 | 估值/名称失败静默 None/"" | partial_fields 显式标注 |
| tushare_src.py:413（index_member 空） | 空 return [] | 区分"行业无成份（confirmed_absent）"与拉取失败 |

### 2.3 验收（可证伪）

- 对每个改造点建 mock 测试：模拟上游异常 → 断言 `ok:false`；模拟上游 200+空 → 断言 `ok:true + confirmed_absent`。任一用例把异常判成 confirmed_absent = 验收失败。
- 全仓 grep `except Exception: pass` 与 `except.*return \[\]` 模式命中 0（白名单需逐条注释说明为何安全）。
- 版本化：封套带 `contract_version`；旧行为消费方（workbench/stockbot/公众号线共用 TOOL_REGISTRY【已验证】）在联动闸门前不受影响——改造在新 minor 版本落地，消费侧按姊妹规格 P3 同批切换。

---

## 3. 工具清单：改造与新增

### 3.1 现有 9 个已注册工具

search_stocks_by_name / get_stock_basic_info / list_industry_constituents / list_concept_stocks / get_stock_price / get_latest_quote / get_index_price / get_financial_indicator / get_financial_report_summary——功能保持，统一接入 § 2 封套。

### 3.2 已实现未注册的 3 个工具

get_stock_news / get_market_signals / get_industry_overview 注册进 server.py，并补 docs/TOOLS.md、README（现 4 工具文档零记载【已验证】）。get_stock_news 同时修正名实不符：`_fetch_eastmoney_news` 实为东财**公告** API，字段改名 `announcements_em` 或接真正快讯源；恢复 SSL 验证（现 :820-821 关闭【已验证】）。

### 3.3 从 workbench 下沉的 11 个工具（对应姊妹规格 § 6.2-B）

| 工具 | 现位置（workbench） | 上游 | 备注 |
|---|---|---|---|
| get_company_profile | routers/finmcp.py:181-200 | tushare | |
| get_annual_report_mdna | routers/finmcp.py:583-647 | 巨潮 PDF + pdfplumber | 引入 pdfplumber 依赖，放 optional extras |
| get_earnings_forecast | routers/finmcp.py:205-232 | tushare | 单位换算口径下沉时对 Tushare 原始数据独立核实（workbench 侧修复的对外正确性【未验证】） |
| get_investor_qa | routers/finmcp.py:235-266 | akshare（互动易/e互动） | 上证接口不稳，失败必须 ok:false 而非现在的 `ok:true + note`【已验证 finmcp.py:249】 |
| get_money_flow | stockbot/tools_rt.py | 东财 push2 | 盘中实时；下沉后解除小程序对 stockbot 的跨层依赖 |
| get_market_snapshot | stockbot/tools_rt.py | 东财 push2 | 同上 |
| get_major_shareholder_change | routers/finmcp.py:323-357 | tushare stk_holdertrade | |
| get_pledge_status | routers/finmcp.py:360-380 | tushare | |
| get_broker_ratings | routers/finmcp.py:383-404 | akshare | schema 标注 `third_party_opinion: true`（目标价等） |
| get_buyback | routers/finmcp.py:407-432 | akshare | |
| get_industry_operating_evidence | lib/fin_industry_evidence.py | tushare 财报聚合 | 纯标准库，直接迁 |
| get_sector_ranking | stockbot/tools_rt.py（板块排行） | 东财 push2 | v2.1 增补（姊妹规格 9.2）：小程序 Q4a 大盘归因管线的板块结构数据；下沉清单 11→12 |

原则：下沉 = 代码归属迁移 + 封套化 + 补测试；函数签名保持兼容以便 workbench 平滑切换 import 路径。落位：`packages/a-stock-data` 内新增 tools 模块；akshare/pdfplumber 依赖走 optional extras，不装时对应工具返回 `NOT_SUPPORTED` 而非 ImportError。【待裁定 F-R2：是否单独开 package】

### 3.4 板块反查补全（姊妹规格 G-7）

- get_stock_basic_info 的 industry_l2/l3 补真实值（现硬编码空字符串，tushare_src.py:154-155,178-179【已验证】）。
- 新增 `list_stock_concepts(stock_code)`：个股→概念反查。

---

## 4. 新闻库迁入方案（姊妹规格 G-3）

### 4.1 现状（全部【已验证】）

- 采集器: workbench `lib/fin_news/collector.py`——5 源（新浪 7x24 / 华尔街见闻 / 东财快讯 / 巨潮公告 / 同花顺要闻），30 分钟循环，由 workbench app startup 拉起后台线程。
- 库: workbench `data/fin_news.db`，单表 `news(id, source, title, content, url, published_at, fetched_at)` + fetched_at 索引。
- 消费方 4 个: 小程序线（相关新闻检索 + 巨潮一手来源索引）、stockbot（板块消息面）、公众号线（多源均匀采样）、fin_content researcher（Tavily 本地降级）。
- 事实修正: 库在 workbench 而非机器人仓库；xiaocai-stock-ai 是只读消费端（姊妹规格待裁定 R3）。

### 4.2 目标形态

- **代码归属**: finmcp 仓库新 package `packages/fin-news`——collector（采集）+ query API（`search_news` / `search_announcements` / `get_recent_diverse`，签名与姊妹规格 § 6.2-C 一致）+ schema 迁移脚本。
- **数据库**: 路径由 env `FIN_NEWS_DB` 约定，默认服务器现路径不动（迁代码不迁数据，db 文件零拷贝切换）。
- **运行归属（待裁定 R6，两方案）**:
  - 方案 A（建议）: collector 作为独立常驻进程（PM2 独立进程），与 workbench app 解耦——app 重启/崩溃不中断采集，采集异常不影响 app；
  - 方案 B: workbench startup 继续拉起，仅代码 import 自 fin-news 包——部署零变更，但保留耦合。
- **查询封套**: 同 § 2；新增 `staleness_warning`：最后采集时间距今 > 2 个刷新周期（60 分钟）时必须在 meta 携带。
- **迁移期兼容**: workbench `lib/fin_news` 保留为薄代理（re-export fin-news 包）一个阶段，四个消费方逐个切换后删除。

### 4.3 验收（可证伪）

- 迁移后四个消费方功能等价：小程序事件流一手来源命中数、stockbot 板块消息检索、公众号采样在同一 db 上新旧实现输出一致（抽样对比 ≥3 组）。
- 停止 collector 90 分钟后查询响应必须携带 staleness_warning；恢复后消失。
- workbench 仓库 grep 采集逻辑残留命中 0（薄代理除外，末阶段清零）。

---

## 5. 新数据域（待裁定 F-R4 / 姊妹规格 R5）

| 域 | 方案 | 状态 |
|---|---|---|
| 宏观指标 | GDP/CPI/PMI/LPR 等 tushare 宏观接口封装为 `get_macro_indicator(indicator, periods)` | tushare 对应接口存在性与积分门槛【未验证】，执行前按协议 § 13 用结构化工具核实 |
| 政策文本 | 不单独建政策库；`search_news` 增加政策源过滤（现 5 源已含政策类新闻），后续视命中率评估是否增采官方政策源（如政府网） | 起步方案，成本低 |
| 分红历史 | `get_dividend_history`（tushare 分红接口） | workbench 有预留 import【已验证】 |
| 北向资金 | `get_northbound_flow` | 交易所披露口径 2024 年调整后逐日数据可得性【未验证】，先调研后决定做不做 |
| 事件-行情对齐 | `get_event_market_alignment(event_date, target, window)`：事件日前窗口对象相对基准超额表现、事件日及后短窗反应、同主题新闻时间线节点。纯事实计算，形态判定归产品层（姊妹规格 9.3） | v2.1 新增，小程序预期-兑现机制的数据基础；依赖行情工具 + fin-news 主题回溯检索 |
| 新闻主题回溯 | `search_news` 支持长时间范围 + 同主题聚合（政策脉络时间线用） | v2.1 新增；受 fin_news.db 历史存量深度约束【未验证】，实现前先盘存量 |
| 专业快讯源增补（L1） | 财联社电报类快讯源纳入 collector 采集面 | 【R8 已裁定：做】采集可行性调研后落地（F5） |
| 热度/情绪数据（L2） | 股吧关注度/雪球讨论量等热度排名类事实指标 | 【R8 已裁定：做】随 F5 落地，注意采集频率与反爬风险评估 |

---

## 6. 仓库健康（前置于一切功能改造）

| 项 | 现状【已验证】 | 目标 |
|---|---|---|
| 未提交改动 | concept.py +191/-43（同花顺概念层）未提交；editable 安装使它就是运行版本，丢失即回退 | 立即 commit 获得 git 锚点（注意 workbench 侧对 concept 的东财覆写关系，commit 前核对两处实现的分工） |
| CI | 自 2026-05 全红（Ruff 4 处 lint，本地已复现 3 处在已提交代码） | 修绿并保持；CI 红 = 后续任何阶段不可验收 |
| AkshareSource | 8 方法全 NotImplementedError，README 宣称"默认 akshare"名实不符 | 显式化：无 TUSHARE_TOKEN 时 get_data_source 直接报可读错误；README 改为"当前仅支持 tushare"。不假装双源（诚实优先于好看） |
| 测试缺口 | concept 同花顺逻辑 / news / signals / industry_overview 零测试 | 随 § 2/§ 3 改造补齐，改造工具无测试不验收 |

---

## 7. 阶段划分

每阶段独立可验收，阶段间人工闸门，完成产出本仓 `HANDOFF.md`（指针式、逐项验证状态）。只写目标与验收，不写执行步骤。

| 阶段 | 目标 | 验收判据（可证伪） | 依赖 |
|---|---|---|---|
| **F0 仓库健康** | § 6 四项：concept.py commit、CI 修绿、akshare 显式化、盘点问题清单归档 | CI 最新 run 绿；`git status` 干净；无 token 启动报显式错误 | 裁定 A/B |
| **F1 失败语义统一** | § 2 封套 + 静默降级点全改造 + contract_version 版本化 | § 2.3 全部 mock 用例通过；grep 禁止形态命中 0；旧版本消费方回归不破（联动闸门前不切换） | F0 |
| **F2 注册与文档** | § 3.2 三工具注册 + 名实修正 + SSL；文档与代码零偏差 | MCP server 实际拉起并调用注册工具各 1 次成功；TOOLS.md 与 server.py 注册表 diff 为空 | F0 |
| **F3 工具下沉** | § 3.3 十一工具 + § 3.4 反查补全 | 每工具：封套合规 + mock 测试 + 与 workbench 原实现输出对比一致（≥2 样本/工具）；earnings_forecast 单位口径对 tushare 原始数据核实记录落盘 | F1 |
| **F4 新闻库迁入** | § 4 | § 4.3 三条全过 | F1；运行归属裁定 R6 |
| **F5 新数据域** | § 5（裁定通过的子集，含 v2.1 新增的事件-行情对齐、新闻主题回溯；L1/L2 信息源受 R8 裁定约束） | 每新工具：接口存在性验证记录 + 封套合规 + 测试；get_event_market_alignment 另需 ≥3 个历史真实事件的对齐输出与手工核算一致 | F1；裁定 R5/F-R4/R8 |

与姊妹规格的**联动闸门**: workbench P3（契约切换）必须在 F1+F3 完成后、由 Donnie 单独确认切换窗口——因 TOOL_REGISTRY 同时服务 stockbot 与公众号线，切换影响面超出小程序【已验证】。

---

## 8. 裁定记录（原待裁定项，2026-09-02 Donnie 全部按建议裁定通过）

| # | 事项 | 裁定结果（=建议） |
|---|---|---|
| F-R1 | concept.py 未提交改动的 commit 时点（等裁定 A 一并处理，还是 F0 立即处理） | F0 立即 commit——该仓与 workbench 裁定无耦合，晚 commit 只增加丢失风险 |
| F-R2 | 下沉工具落位：并入 `packages/a-stock-data` vs 新开 package（如 a-stock-disclosure） | 并入 a-stock-data + optional extras——11 个工具与现有工具同域（A 股事实数据），拆包增加维护面无收益 |
| F-R3 | akshare 处置：显式 tushare-only vs 补实现 AkshareSource | 显式 tushare-only；补实现 8 个方法工作量大且无消费方需要 |
| F-R4 | 新数据域范围（同姊妹规格 R5，一次裁定两侧生效） | 本期做宏观指标 + 分红；政策走新闻源过滤；北向先调研可得性再定 |
| F-R5 | MCP server 是否继续对外（非本机）暴露 | 维持现状（本机 stdio + 库调用），不在本期扩 HTTP 服务面 |

## 9. 契约一致性对照（与姊妹规格）

| 契约点 | 本文 | 姊妹规格 | 一致性 |
|---|---|---|---|
| 三态封套与错误码 | § 2.1 | § 6.1 | 一致（逐字对齐） |
| 下沉 11 工具清单 | § 3.3 | § 6.2-B | 一致 |
| 新闻检索 API 签名 + staleness | § 4.2 | § 6.2-C | 一致 |
| 新数据域范围 | § 5 | § 6.2-D | 一致，共同挂起于 R5/F-R4 |
| 切换时序 | § 7 联动闸门 | § 7 P3 | 一致 |
| 目标价等观点字段处理 | § 1（透传+标注） | § 5.3 + R4（产品层过滤） | 一致，分工明确；R4 待裁定的是小程序是否展示，不影响底座行为 |

无未标注冲突。
