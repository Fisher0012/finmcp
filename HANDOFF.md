# HANDOFF — FinMCP 底座

规格: 本仓 `SPEC.md` v1.0（2026-09-02 生效）。姊妹规格与 P0/P1 阶段 HANDOFF 见 workbench 仓。

## 🎯 阶段 F5 · 新数据域 — 已完成, 停在 F5 闸门 (2026-09-02)

**验收判据逐项状态（SPEC §7 F5 行 + R8）**:

| 判据 | 状态 | 证据指针 |
|---|---|---|
| 每新工具接口存在性验证记录 + 封套 + 测试 | ✅ 已验证 | 6 新工具(macro/dividend/northbound/alignment/attention + 主题回溯复用 search_news); 接口存在性全部 2026-09-02 带 token 实调; 测试 +24 项, 全仓 209 项全过; ruff/mypy strict 零错误 |
| get_event_market_alignment ≥3 历史真实事件与手工核算一致 | ✅ 已验证 | 茅台半年报0815 / 温氏预亏0711 / 旭创预增0131: 独立算式核算超额 4.09/10.41/4.74% 逐位一致; 非交易日顺延正确; 数据自证真实形态(旭创预增公告日 -8.94% 即 sell-the-news) |
| 北向可得性调研(F-R4) | ✅ 已验证 | moneyflow_hsgt 实调有数据(日度收盘口径) → 做; 单位百万元双源核实 |
| 新闻主题回溯前置盘点(9.3) | ✅ 已验证 | 生产库 2026-05-31 起 95 天连续 25.5 万条 → 支持约 3 个月回溯, alignment 的 news_timeline 自带覆盖边界注明 |
| L1 快讯源(R8) | ⛔ 调研结论=不做, 待 Donnie 认可 | 财联社接口需签名逆向(实测 404/errno 10012), 反爬对抗+时效军备竞赛不可赢; 既有新浪 7x24/东财快讯已覆盖快讯面 |
| L2 热度数据(R8) | ✅ 已验证 | get_stock_attention 东财人气榜(当前排名+历史序列)真实调用验证; 仅排名事实不含讨论内容(合规定位) |
| 宏观字段口径 | ✅ 已验证 | PMI 60 字段表自官方文档镜像; dividend cash_div=税后/cash_div_tax=税前(执行代理按官方文档纠正了主会话任务指令中的口径标注错误——反迎合正例) |

**MCP server 现 30 工具**, TOOLS.md/README 同步, 注册表 diff=EMPTY。

**⛔ 闸门问题**:
1. F5 验收是否通过? L1 财联社"不做"的调研结论是否认可?
2. 生产部署: F5 六工具是否随下次窗口部署(无消费方变更, 部署零风险)?
3. 下一步 P4(六类问题框架+预期-兑现形态分类器+信息缺口形态): 数据基础已齐, 是否开工? 其中 9.3 五形态与 9.4 缺口的用户可见文案模板将先以 plain text 预审。

---

## 🎯 阶段 F4 · 新闻库迁入 — 代码完成, 生产切换停闸门 (2026-09-02)

**R6 运行归属（Donnie 委托裁定）**: 选**方案 A**（独立 collector 进程）——采集与 app 生命周期解耦, app 重启/崩溃不中断采集, 采集异常不拖垮 app。

**验收判据逐项状态（SPEC §4.3）**:

| 判据 | 状态 | 证据指针 |
|---|---|---|
| 四消费方功能等价（抽样对比 ≥3 组） | ✅ 已验证 | 同一真实库(34k 条)新旧实现 **7 组逐条相等**(get_recent×3 + diverse×3 + count; 含真实采集 140 条后的有数据窗口复验); 消费方 import 路径零改动(薄代理) |
| 停采 90 分钟 staleness_warning | ✅ 已验证 | 包测试 mock 时间断言(90 分钟→警告, 新鲜→无, 空库→警告); 真实查询实测刚采集后无警告 |
| workbench 采集逻辑残留 grep 0 | ✅ 已验证 | fetch_* 函数与源 API 引用清零(薄代理除外; routers/fin_content.py:38 为公众号线自带 Tavily 降级兜底, 非采集器残留) |
| 5 源真实可用 | ✅ 已验证 | 迁移后实跑一轮: 新浪/华尔街见闻/东财/巨潮/同花顺全 ok, 140 条入库 |
| 质量门 | ✅ 已验证 | fin-news 8 测试 + 全仓 185 项全过; ruff/mypy 零错误; CI 已接入 fin-news |

**落位**: `packages/fin-news`（db.py / collector.py / query.py / __main__.py）; workbench `lib/fin_news/collector.py` 改薄代理(292→63 行), 默认行为不变, `FIN_NEWS_EXTERNAL_COLLECTOR=1` 停内嵌采集。
**环境变更记录**: 本机系统 python 与 /tmp venv 各 editable 安装 fin-news（workbench 实际运行解释器的项目级依赖, 生产侧安装归部署闸门）。

**⛔ 生产切换闸门（与 P3 合并, 等 Donnie 一次确认）**: ① 部署本批两仓代码 + 服务器 pip install -e fin-news; ② PM2 新进程 `fin-news-collector`(python -m fin_news, env FIN_NEWS_DB=/opt/workbench/data/fin_news.db); ③ workbench env 加 FIN_NEWS_EXTERNAL_COLLECTOR=1 + FINMCP_CONTRACT=v2(P3) 并 restart。三步一批做完即 P3+F4 生产生效。

---

## 🎯 阶段 F3 · 工具下沉 — 已完成, 停在 F3→F4 人工闸门 (2026-09-02)

**验收判据逐项状态（SPEC §7 F3 行）**:

| 判据 | 状态 | 证据指针 |
|---|---|---|
| 每工具封套合规 + mock 测试 | ✅ 已验证 | 12 工具下沉(7 新模块) + 55 项新测试; 全仓 177 项全过; ruff/mypy strict 零错误 |
| 与 workbench 原实现输出对比 ≥2 样本/工具 | ✅ 已验证 | 21 组真实调用对比全 OK(11 工具×2 样本, 收盘后静态时段; ok 状态/data 键集/数据量一致, broker_ratings 超集键=third_party_opinion 预期标注)。mdna 未做双样本实调对比(PDF 下载成本), 以逻辑照抄+mock 覆盖【该项未验证】 |
| earnings_forecast 单位口径核实记录落盘 | ✅ 已验证 | `docs/EARNINGS_FORECAST_UNIT_VERIFICATION.md`(温氏股份原始值与公告原文逐位一致, 万元实锤) |
| B 方案换源(Donnie 裁定) | ✅ 已验证 | 公告→巨潮(实调 30 天 6 条真实公告, attempts 双 ok); 涨跌停→pro_bar 阈值计算(open_times/first_time 置 None+fields_unavailable 显式标注, ST 5% 局限注明) |
| §3.4 反查 | ✅(L2/L3) / ⛔ NOT_SUPPORTED(个股→概念) | L2/L3 用 index_member_all 实调验证(茅台→白酒Ⅱ/Ⅲ, 中际旭创→通信设备链); list_stock_concepts 实调确认 tushare concept_detail 已下线+ths 系无权限, 显式 NOT_SUPPORTED 列入 F5 |
| MCP server 25 工具 | ✅ 已验证 | stdio tools/list=25 + 抽调 3 工具; TOOLS.md 与注册表 diff=EMPTY |

**复验中抓出并修复的代理初版问题（独立复验的价值）**:
1. **L2/L3 错数据 bug**: `index_member(con_code=)` 参数不被 tushare 支持, 返回无关默认页(茅台被判"元件/多业态零售")——比空值更危险的静默错数据, 已换 `index_member_all` 并实调验证。
2. list_stock_concepts 的 concept_detail 依据不成立(接口已下线), 改显式 NOT_SUPPORTED。
3. 巨潮 15 天空窗虚惊一场: 逐参数正交实验证实为真实无公告(茅台最近公告 8-14), 30 天窗口 6 条正常。

**附带发现（只记录）**: 线上生产的 list_concept_stocks 三级瀑布中 tushare 二级源(concept→concept_detail)因接口下线实际长期不可用, F1 的 attempts 现在会将其显式记为 error; tushare `concept` 接口限频 1 次/小时。

**未验证项**: mdna 双样本实调对比; 巨潮北交所 column/plate 参数(bse/bj 按前端惯例, 无北交样本实调); 涨跌停阈值判定的固有假阳性(新股无涨跌幅限制日等)已在 docstring 标注。

**⛔ 闸门问题（等 Donnie 裁定）**:
1. F3 验收是否通过？
2. 下一步三选: F4(新闻库迁入, 依赖 R6 运行归属方案 A/B 确认) / P3(数据契约切换, F1+F3 已齐, 需你单独确认切换窗口——TOOL_REGISTRY 同时服务 stockbot/公众号线) / F5(新数据域)。建议顺序: P3 切换窗口评估先行(下沉成果落地见效), F4 并行。

---

## 🎯 阶段 F2 · 注册与文档 — 已完成, 停在 F2→F3 人工闸门 (2026-09-02)

**验收判据逐项状态（SPEC §7 F2 行）**:

| 判据 | 状态 | 证据指针 |
|---|---|---|
| MCP server 实际拉起并调用注册工具各 1 次成功 | ✅ 已验证 | stdio 端到端实测: tools/list 返回 12 工具, **12/12 真实调用全部 ok**（含 tushare/新浪/同花顺/东财真实上游; 首轮 2 个失败为测试脚本日期传参格式错, 更正 YYYY-MM-DD 后全过） |
| TOOLS.md 与 server.py 注册表 diff 为空 | ✅ 已验证 | 脚本核对注册集合==文档集合==12, 双向差集空 |
| 三工具注册 | ✅ 已验证 | get_stock_news / get_market_signals / get_industry_overview 入 server.py |
| 名实修正 | ✅ 已验证 | 东财源正名 announcements_em(公告), market_news 保留过渡别名; docstring 不再自称"快讯"; workbench stockbot/engine.py 已切新键带回退(commit 390a7e4) |
| SSL 恢复 | ✅ 已验证 | 东财 API 完整证书验证实测通过(3 条真实公告), CERT_NONE 已移除 |

**实测中的 F1 效果确认（真实环境）**: get_stock_news 返回 `attempts=[tushare_anns_d:error(无接口权限), eastmoney_ann:ok]`; get_market_signals 返回 `attempts=[limit_list_d:error(无权限), top_list:empty]` + empty_reason=unknown——线上长期静默失败的 anns_d/limit_list_d 权限问题首次显式可见。**tushare 账号缺 anns_d 与 limit_list_d 接口权限为既成事实**, F3 公告下沉选型(巨潮)与异动信号数据源需绕开或升级积分（列入 F3 闸门问题）。

**未验证项**: 过渡别名 market_news 的移除时点未定(消费方全部切换后, 归 F3)。

**⛔ 闸门问题（等 Donnie 裁定后才进 F3）**:
1. F2 验收是否通过？
2. tushare 无 anns_d/limit_list_d 权限: 升级 tushare 积分 还是 F3 换源(公告→巨潮, 涨跌停→行情计算)? 涉及可能付费, 需你拍板。

---

## 🎯 阶段 F1 · 失败语义统一 — 已完成, 停在 F1→F2 人工闸门 (2026-09-02)

**验收判据逐项状态（SPEC §2.3）**:

| 判据 | 状态 | 证据指针 |
|---|---|---|
| 每改造点 mock 测试（异常→ok:false / 200+空→confirmed_absent） | ✅ 已验证 | `tests/unit/test_contract_semantics.py` 16 项全过, 覆盖 news 双源/signals 逐日/concept 三级/quote partial/industry 空表 五个改造点 + 默认模式断言 |
| grep 禁止形态命中 0 | ✅ 已验证 | `except→pass` 与 `except→return []` 全仓 0 命中, 无需白名单; 附属字段 basic_info 股本(:169)不在 SPEC §2.2 清单内, 保持 debug 级(备注) |
| 旧版本消费方回归不破 | ✅ 已验证 | 默认 v1 模式: 本仓 122 项测试全过 + workbench(editable 立即生效) 296 项全过 + workbench import 实测拿到新代码且 contract_mode()=v1 |
| contract_version 版本化 | ✅ 已验证 | meta 无条件携带 contract_version(v1=1.1/v2=2.0); v1=旧行为+诊断元数据(纯加法), v2=严格三态 |
| CI 绿 | ⏳ push 后待确认 | 本地 CI 等价四步(ruff check/format/mypy/pytest)全过 |

**关键设计决策（超出 SPEC 字面, 需 Donnie 知晓）**: SPEC §2.3 设想"新 minor 版本落地"隔离消费方, 但 workbench 走 editable 安装, 版本号无隔离作用——改用 **env 开关 FINMCP_CONTRACT**（默认 v1 旧行为, P3 联动闸门时置 v2 启用严格三态）。v1 模式下静默降级已在 meta.attempts/empty_reason 层面完全可见, 行为切换只差翻开关。

**改造中发现并修复的真 bug**: concept.py 内层 `_ths_fetch_concept_list/_stocks` 吞异常返回空, 会把"同花顺网络挂"伪装成"无此概念"(上层记 empty 而非 error), 已改为向上抛由 attempts 记 error。

**行为语义变化点（v1 模式下也生效, 均为信息增量）**: ① signals 全挂时 data.has_signals 从 False 变 **None**（未知≠无异动, 唯一 v1 下的 data 变化, workbench 296 回归无破)；② 所有 ok_response 的 meta 新增 contract_version/empty_reason 字段。

**未验证项**: 真实上游全挂场景未实测(仅 mock); 线上 anns_d 无权限的实际留痕效果待部署后观察(调查已证实该源长期失败, 改造后将显式可见)。

**⛔ 闸门问题（等 Donnie 裁定后才进 F2）**:
1. F1 验收是否通过？env 开关替代 minor 版本隔离的设计是否接受？
2. F2（三工具注册+名实修正+SSL 恢复+文档对齐）确认开工？

---

## 阶段 F0 · 仓库健康 — 已完成, 闸门已过 (2026-09-02)


**验收判据逐项状态**:

| 判据 | 状态 | 证据指针 |
|---|---|---|
| concept.py 未提交改动 commit（F-R1） | ✅ 已验证 | commit `5bf1853`; commit 前已核对 workbench 侧分工（workbench `routers/finmcp.py:923` 用自有东财版覆写 TOOL_REGISTRY, 两实现并存无冲突, 本仓同花顺版服务 MCP/库调用路径） |
| CI 最新 run 绿 | ✅ 已验证 | run 33605079820 success（52s, 2026-09-02）——2026-05 以来首次全绿; 本地 venv 复现 CI 四步全过（ruff check / format / mypy strict 0 错 / pytest unit 106 过 + integration 20 skip） |
| `git status` 干净 | ✅ 已验证 | push 后独立复查无输出 |
| 无 token 启动报显式错误（F-R3 akshare 显式化） | ✅ 已验证 | `env -u TUSHARE_TOKEN` 下 `get_data_source()` 抛 `AuthRequiredError("当前仅支持 tushare…")`; README 两处已改 tushare-only 事实描述 |
| 盘点问题清单归档 | ✅ 已验证 | `INVENTORY.md` commit `bd2a354` |

**本阶段实际改动**（9 个 commit, `5bf1853..3554535`）:
- lint/类型修绿: ruff 4 处 + ruff format 19 文件 + mypy strict 51→0（含 4 处基类缺口显式 `type: ignore` 指向 SPEC F1, 不假装已实现）
- **CI 三处真实缺陷修复**（此前 CI 从未走到 pytest 步骤, 首次暴露）: ① `requests` 漏声明为核心依赖（realtime.py 顶层 import, 干净环境必挂）; ② `mcp` 未 pin, 2.x 移除 `mcp.server.fastmcp.FastMCP`, 新装环境 import 失败, 已 pin `<2`; ③ CI integration 步骤 `--timeout` 缺 pytest-timeout, CI 安装清单与 tushare extra 已补
- akshare 显式化: `utils.get_data_source` 无 token 直接报可读错误, 不再返回全方法 NotImplementedError 的空壳
- SPEC v1.0 入库

**行为变化影响面**: `get_data_source` 无 token 场景从"返回空壳（调用时才 NotImplementedError）"变为"启动即 AuthRequiredError"。现有消费方（workbench/MCP server）均带 TUSHARE_TOKEN, 走 tushare 分支不受影响。106 项单测全过（含首次在干净 venv 隔离环境验证）。

**未验证项**: CI 仅验证了 push 触发的 ubuntu 矩阵（4 个 Python 版本全绿）; MCP server stdio 端到端拉起属 F2 验收项, 本阶段未测。

**⛔ 闸门问题（等 Donnie 裁定后才进 F1）**:
1. F0 验收是否通过？
2. F1（失败语义统一/三态封套）为 breaking change 前置, 确认按 SPEC § 2 契约开工？
