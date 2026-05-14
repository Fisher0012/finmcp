# Contributing to FinMCP

感谢你对 FinMCP 的关注！

## 开发环境

- Python 3.10+
- 推荐使用 `uv` 或 `pip` 管理依赖

## 代码规范

- Lint & Format: `ruff`
- Type Check: `mypy --strict`
- Test: `pytest`
- Commit Message: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)

## 提交流程

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feat/your-feature`)
3. 提交改动（遵循 Conventional Commits）
4. 确保 `ruff check` 和 `mypy` 通过
5. 确保测试通过 (`pytest`)
6. 提交 Pull Request
