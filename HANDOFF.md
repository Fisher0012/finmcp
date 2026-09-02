# HANDOFF — FinMCP 底座

规格: 本仓 `SPEC.md` v1.0（2026-09-02 生效）。姊妹规格与 P0/P1 阶段 HANDOFF 见 workbench 仓。

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
