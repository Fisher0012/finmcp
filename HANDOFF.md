# HANDOFF — FinMCP 底座

规格: 本仓 `SPEC.md` v1.0（2026-09-02 生效）。姊妹规格与 P0 阶段 HANDOFF 见 workbench 仓。

## 🎯 阶段 F0 · 仓库健康 — 已完成, 停在 F0→F1 人工闸门 (2026-09-02)

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
