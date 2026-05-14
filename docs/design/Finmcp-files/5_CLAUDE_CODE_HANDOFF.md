# FinMCP — Claude Code 交付简报

> 本文档是给 Claude Code 的工作指令。复制本文档（或链接到此文档）作为 CC 任务的初始 prompt。
> **CC 启动开发前，必须先阅读完 1-4 号文档。**

---

## 1. 你的角色和任务

你是 FinMCP 项目的核心开发者。本次任务：

**实现 `finmcp-a-stock-data` v0.1.0 MVP 版本**，从零开始，按照已有的 4 份设计文档执行。

## 2. 必读文档（按顺序）

在写任何代码前，**必须按顺序读完这 4 个文档**，并向用户确认你已经理解：

1. `1_PROJECT_OVERVIEW.md` — 理解项目定位和长期愿景
2. `2_MCP_TOOLKIT_SPEC.md` — 理解工具集规范（接口、命名、错误码）
3. `3_TECH_ARCHITECTURE.md` — 理解技术架构和硬约束
4. `4_MVP_SCOPE.md` — 理解本次 MVP 的精确范围

**确认方式**：读完后向用户回复一个 < 200 字的总结，包含：
- 我要实现的 8 个 tool 是哪 8 个
- 我打算用的技术栈
- 我看到的 3 个最大的技术风险或决策点

## 3. 工作模式

### 3.1 三阶段交付

按以下三阶段推进，**每个阶段交付完毕后必须等用户确认才能进下一阶段**：

| 阶段 | 时长 | 交付物 | 用户确认点 |
|------|------|--------|-----------|
| **Stage 1：脚手架** | 1-2 天 | 完整仓库结构 + 空 tool 接口 + CI 配置 | 跑通空的 MCP server，能在 Claude Desktop 注册 |
| **Stage 2：实现** | 5-7 天 | 8 个 tool 的真实实现 + 缓存 + 错误处理 | 10 个验收用例（见 `4_MVP_SCOPE.md` §6）全部通过 |
| **Stage 3：交付** | 3-5 天 | 测试补齐 + 文档 + 打包 + 发布预演 | PyPI 测试包可安装、文档完整 |

### 3.2 任务粒度

每完成一个"原子任务"立即 commit。原子任务包括：
- 实现一个 tool 的骨架
- 实现一个 tool 的真实数据获取
- 写一个 tool 的单元测试
- 写一个 tool 的集成测试
- 添加错误处理分支
- 完善某个文档章节

**commit 信息遵循 Conventional Commits**：
```
feat(a-stock-data): implement get_stock_price tool
test(a-stock-data): add integration tests for search_stocks_by_name
docs: add Claude Desktop integration example
fix(cache): handle missing cache directory gracefully
```

### 3.3 提问规则

你**必须停下来问用户**的情况：

- 文档之间出现冲突且优先级判断不清晰
- 发现 akshare 的某个接口和文档预期不符
- 需要引入新的依赖（即使是很轻量的）
- 测试在本地通过但你不确定边界情况
- 你想到一个文档没写但你觉得"应该有"的功能

你**不要问**的事情（自己决策即可）：

- 函数内部实现细节
- 变量命名
- 注释的措辞
- 测试用例的具体值
- 代码风格选择（ruff 决定）

## 4. 关键技术决策（已定，不要重新讨论）

以下决策已在 `3_TECH_ARCHITECTURE.md` 中确定，**不要重新提议替代方案**：

- 使用 FastMCP（不是手写 MCP SDK）
- 使用 Python 3.10+（不要降级支持）
- 使用 akshare 作为默认数据源（不要换 baostock/efinance）
- 使用 diskcache 做缓存（不要用 Redis / 文件 JSON）
- 使用 hatchling 打包（不要用 poetry/setuptools）
- 使用 ruff + mypy（不要加 black/isort/flake8）
- Monorepo 结构（不要拆多仓库）
- 不上报任何遥测（不要加 sentry/posthog）

## 5. 第一阶段（Stage 1）具体任务清单

### Stage 1 验收标准

完成后用户能在 Claude Desktop 看到一个**功能完整但全部返回 stub 数据**的 MCP server。

### Stage 1 任务列表

#### Task 1.1 - 仓库初始化

- 创建 git 仓库
- 创建 `pyproject.toml`（项目根）含 workspace 配置
- 创建 `README.md` 含项目占位简介（最终版本 Stage 3 完成）
- 创建 `.gitignore`（Python + macOS + IDE）
- 创建 `LICENSE`（MIT，作者待用户填）
- 创建 `.github/workflows/ci.yml`（lint + test，触发 PR/push）

#### Task 1.2 - shared 包

- 创建 `shared/finmcp_common/` 目录
- 实现 `responses.py`：`ok_response()` / `error_response()` 构造器
- 实现 `stock_code.py`：`normalize_stock_code()` / `parse_stock_code()`
- 实现 `date_utils.py`：交易日判断（先用占位逻辑，Stage 2 接入真实数据）
- 实现 `errors.py`：`FinMCPError` 基类 + 各错误类
- 实现 `logging.py`：标准 logger 配置（stderr 输出）
- 单元测试覆盖（最少 90%）

#### Task 1.3 - a-stock-data 包脚手架

- 创建 `packages/a-stock-data/` 目录结构（按 `3_TECH_ARCHITECTURE.md` §2）
- 创建 `pyproject.toml`（独立可发布）
- 创建 `src/finmcp_a_stock_data/__init__.py` 含 `__version__ = "0.1.0"`
- 创建 `server.py`：FastMCP 实例 + 注册所有 8 个 tool（全部返回 stub）
- 创建 8 个 tool 文件（每个文件含完整 docstring，函数体返回固定 stub data）
- 创建 `models.py`：所有 Pydantic models（即使 Stage 1 还不用）
- 创建 `data_sources/base.py`：`StockDataSource` 抽象基类
- 创建 `cache.py`：diskcache 包装（API 完整，Stage 1 可以不开启缓存）
- 创建 `errors.py`：本包专属错误类
- 创建 `utils.py`：占位

#### Task 1.4 - 本地启动验证

- `pip install -e packages/a-stock-data/` 可成功
- `uvx --from . finmcp-a-stock-data` 可启动 server
- 在 Claude Desktop 配置后能看到 8 个 tool
- 调用任一 tool 返回 stub 数据

#### Task 1.5 - 文档骨架

- `packages/a-stock-data/README.md` 含占位（最终 Stage 3 完成）
- `packages/a-stock-data/docs/TOOLS.md` 含 8 个 tool 的接口签名（无示例）
- `packages/a-stock-data/CHANGELOG.md` 含 v0.1.0 占位

### Stage 1 完成后的对话流

完成后向用户报告：

```
Stage 1 完成。当前状态：
- 仓库结构：✅
- 8 个 tool 接口已注册：✅
- 在 Claude Desktop 中可调用（返回 stub）：✅
- 测试覆盖：XX%
- CI：✅ 全绿

下一步：进入 Stage 2，开始 8 个 tool 的真实实现。
按以下顺序实现：[列出推荐顺序]

等待用户确认后进入 Stage 2。
```

## 6. 第二阶段（Stage 2）推荐顺序

按以下顺序实现 8 个 tool（从简单到复杂、从依赖少到依赖多）：

1. `get_stock_basic_info`（最简单，公司信息查询）
2. `search_stocks_by_name`（依赖 basic_info 的数据）
3. `get_latest_quote`（实时报价，单次调用）
4. `get_stock_price`（历史行情，最高频）
5. `get_index_price`（指数行情，akshare 接口略不同）
6. `list_industry_constituents`（行业数据）
7. `get_financial_indicator`（财务指标）
8. `get_financial_report_summary`（三大表，最复杂）

**每实现一个就跑通对应的验收用例**（`4_MVP_SCOPE.md` §6）后再进下一个。

## 7. 第三阶段（Stage 3）任务

### Task 3.1 - 测试补齐

- 全部 tool 单元测试覆盖率 ≥ 80%
- 全部 tool 至少 3 个集成测试用例
- 错误路径测试（非交易日、无效代码、上游错误）

### Task 3.2 - 文档完善

- `README.md`：完整版（中英双语 quick start）
- `docs/TOOLS.md`：每个 tool 的 3+ 真实示例输入输出
- `docs/EXAMPLES.md`：5 个端到端场景（按 `4_MVP_SCOPE.md` §6）
- `docs/INTEGRATION.md`：Claude Desktop / Cursor / Claude Code 接入指南
- `CHANGELOG.md`：v0.1.0 完整变更

### Task 3.3 - 发布准备

- 版本号确认为 `0.1.0`
- PyPI 测试发布（test.pypi.org）
- 验证 `pip install --index-url https://test.pypi.org/simple/ finmcp-a-stock-data` 成功
- 准备 GitHub Release 文案

### Task 3.4 - 不做的事

- 不要直接发布到 PyPI 正式仓库（最终发布由用户手动操作）
- 不要在公开渠道（Twitter/Xhs/即刻）发任何东西
- 不要为了赶进度跳过测试

## 8. 与用户的协作规则

### 8.1 信息同步

- 每个阶段开始前：列出本阶段计划 + 时间估算
- 每个 commit 后：在工作记录里追加（不必每次告知用户）
- 遇到阻塞：立即停下来问，不要"先做着看"
- 每天工作结束：一次总结（完成了什么、明天计划、有无 blocker）

### 8.2 文档维护

如果你在开发中发现 4 份文档之间冲突、或文档有明显错误：

- **不要**自己改了就当数事
- **必须**向用户报告："我发现 X 文档第 Y 节说 A，但 Z 文档第 W 节说 B，我建议改成 C，是否确认？"
- 用户确认后再改文档，并 commit 文档变更

### 8.3 范围控制

如果在开发中你觉得"这里加个 XX 功能更好"：

- **不要**直接加
- 在 issue 里记下来，标记 `enhancement`，未来版本考虑
- 如果你认为非加不可，停下来跟用户讨论

## 9. 性能与质量门槛

每次 commit 前自检：

- ruff check 0 warning
- mypy strict 通过
- 相关 unit test 通过
- 没有新增未在文档列出的依赖
- 没有硬编码 token / 路径
- commit message 符合 Conventional Commits

CI 配置应自动卡死不达标的 PR。

## 10. 应急流程

### 10.1 akshare 接口变更

如果某个 akshare 接口返回结构和你预期不符：

1. 先验证：在 Python REPL 里跑一次，确认是否真的变了
2. 看 akshare 文档 / GitHub 最近 issue
3. 如果确实变了，**不要**为了"兼容"写一堆 if-else
4. 写一个适配函数（在 `data_sources/akshare_src.py` 里），并加注释说明
5. 写一个 regression test 防止未来再变

### 10.2 数据源限流

如果开发中遇到 akshare 限流（被东财/新浪拒绝）：

- 立即降低测试频率
- 在 `cache.py` 中临时调大 TTL
- 不要为了绕过限流加代理或换 IP
- 在文档里说明限流的存在

### 10.3 你不确定的事

任何时候只要你心里想"这个我不太确定..."：

**停下来问用户**。

写错的代码可以删，但浪费用户时间和精力的损失更大。

## 11. 完成定义（Definition of Done）

整个 MVP 完成的最终验收：

- 用户在干净的环境（fresh macOS / Linux）按 README 指引能在 5 分钟内跑通
- 10 个验收用例（`4_MVP_SCOPE.md` §6）全部在 Claude Desktop 中通过
- 用户对代码质量、测试覆盖率、文档完整性都认可
- PyPI 测试发布成功
- GitHub 仓库可对外公开（用户授权后）

---

## 12. 启动语

如果你（Claude Code）已经读完所有文档，准备就绪，请向用户发送：

> 我已读完 FinMCP 5 份设计文档。
>
> **核心理解**：
> - MVP 目标是实现 `finmcp-a-stock-data` v0.1.0，包含 8 个 tool，让 Claude 能查询 A 股真实数据
> - 技术栈：Python 3.10+ / FastMCP / akshare / diskcache / hatchling
> - 工作模式：三阶段（脚手架 → 实现 → 交付），每阶段需用户确认
>
> **我看到的 3 个技术风险/决策点**：
> 1. [你识别的风险 1]
> 2. [你识别的风险 2]
> 3. [你识别的风险 3]
>
> 请确认这 3 个风险点的处理方式，确认后我开始 Stage 1。
