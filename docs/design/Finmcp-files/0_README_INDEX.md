# FinMCP 设计文档集

> 项目：FinMCP — 给 AI 财经/投研创作者的开源 MCP 工具集
> 文档版本：v1.0（2026-05-14）
> 状态：✅ 设计完成，等待 Claude Code 执行 MVP

---

## 文档清单

按阅读顺序排列：

| 序号 | 文档 | 长度 | 用途 |
|------|------|------|------|
| 0 | `0_README_INDEX.md` | ~3K 字 | 本文档（入口索引） |
| 1 | `1_PROJECT_OVERVIEW.md` | ~7K 字 | 项目定位、商业模式、Roadmap |
| 2 | `2_MCP_TOOLKIT_SPEC.md` | ~8K 字 | 工具集设计规范（接口、命名、错误） |
| 3 | `3_TECH_ARCHITECTURE.md` | ~14K 字 | 技术架构、仓库结构、ADR |
| 4 | `4_MVP_SCOPE.md` | ~10K 字 | MVP 精确范围（8 个 tool 详细规格） |
| 5 | `5_CLAUDE_CODE_HANDOFF.md` | ~11K 字 | 给 CC 的执行指令 |

**总计约 5 万字**，覆盖从战略到代码的全链路。

---

## 怎么用这些文档

### 你（创始人/PM）的使用方式

1. **快速 review 全貌**：先读 `1_PROJECT_OVERVIEW.md`，确认方向无误
2. **检查 MVP 范围**：读 `4_MVP_SCOPE.md`，确认 8 个 tool 是你想要的（不是少了/多了）
3. **细化技术决策**：读 `3_TECH_ARCHITECTURE.md` 的 ADR 部分，看是否有要调整的
4. **如有任何调整**：直接在文档里改，或告诉我，我帮你改
5. **OK 后启动 CC**：把整个 `finmcp-docs/` 目录上传给 Claude Code

### Claude Code 的使用方式

CC 拿到文档后会按 `5_CLAUDE_CODE_HANDOFF.md` 的指引：

1. 按顺序读完全部 4 份背景文档
2. 向你回报理解和 3 个识别出的风险点
3. 等你确认后进入 Stage 1（脚手架）
4. 三阶段交付，每阶段需你确认

---

## 启动 Claude Code 的方式

把文档目录放到项目下，例如 `~/projects/finmcp/docs/design/`，然后在 Claude Code 里用如下 prompt 启动：

```
我要开发一个名为 FinMCP 的开源项目，已经完成全部设计文档，存放在 docs/design/ 目录下。

请严格按以下步骤工作：

Step 1：按编号顺序阅读 docs/design/ 下的全部 6 份文档。

Step 2：读完后，严格按 5_CLAUDE_CODE_HANDOFF.md §12 的格式向我回报：
- MVP 目标的复述（一句话）
- 你要实现的 8 个 tool 名字列表
- 你打算用的技术栈
- 三个识别出的技术风险/决策点（每个 2-3 句话）

Step 3：回报后停下，不要开始编码。等我确认后再进入 Stage 1。

重要：在 Step 2 之前不要写任何代码或创建任何文件。
```

---

## 文档之间的关系

```
1_PROJECT_OVERVIEW   战略层：为什么做、做什么、目标用户、商业模式
        ↓
2_MCP_TOOLKIT_SPEC   规范层：所有 server 共同遵守的接口/命名/错误
        ↓
3_TECH_ARCHITECTURE  架构层：仓库结构、技术栈、ADR、性能/安全约束
        ↓
4_MVP_SCOPE          范围层：第一个 server 的 8 个 tool 详细规格
        ↓
5_CLAUDE_CODE_HANDOFF 执行层：CC 的工作流、三阶段任务、协作规则
```

**冲突时优先级**（具体覆盖抽象）：`5 > 4 > 3 > 2 > 1`

---

## 可调整项 Checklist

启动 CC 前你需要确认的事项：

### 项目层
- [ ] 项目名 `FinMCP` OK？还是改名（如 AlphaMCP / FinTools）
- [ ] LICENSE 选 MIT OK？还是 Apache 2.0 / GPL
- [ ] 主仓库托管在 GitHub OK？（默认）

### 商业层
- [ ] 商业模式"开源核心 + 付费高级版"OK？
- [ ] 12 个月目标（200-500 付费用户）OK？

### 范围层
- [ ] MVP 的 8 个 tool 选择 OK？是否有要加 / 减的？
- [ ] 数据源选 akshare + tushare OK？
- [ ] 暂不支持港股 / 美股 OK？

### 工程层
- [ ] Python 3.10+ OK？
- [ ] Monorepo 结构 OK？还是要每个 server 独立仓库
- [ ] 不上报任何遥测的承诺 OK？

---

**祝开发顺利。FinMCP 是个值得做的项目。**
