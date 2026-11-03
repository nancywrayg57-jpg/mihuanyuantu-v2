---
name: aojuai-backend-testing
description: Add/scale AOJUAI backend tests (pytest + pytest-asyncio) with safe fixtures and templates aligned to this repo (FastAPI + SQLAlchemy async + Postgres).
---

# AOJUAI 后端测试（pytest + pytest-asyncio）

用于：为新模块补齐测试、为重构保驾护航、在 AI 生成代码后快速做回归验证。

## 当前项目现状

- 测试依赖已在 `backend/pyproject.toml` 的 `optional-dependencies.dev` 中声明
- `pytest` 配置也已存在（`[tool.pytest.ini_options]`），默认 `testpaths = ["tests"]`
- 你可以选择：
  - 只在 Skill 内使用模板（不落到仓库代码），或
  - 通过脚手架脚本生成 `backend/tests/`（推荐在开始写大量新模块之前做）

## 推荐策略（先小后大）

1. **Service 单元测试**：优先覆盖“业务分支/校验/异常”
2. **API 集成测试**：覆盖关键路径（list/create/update/delete + 权限拦截）
3. **演示模式**：前端会拦截写操作，但后端仍应按权限/租户隔离正确工作

## 注意：测试数据库必须显式配置

为避免误用生产库，模板要求显式设置 `TEST_DATABASE_URL`。

## 生成脚手架（可选）

使用脚本把模板落到 `backend/tests/`：

```bash
python docs/dev/skills/aojuai-backend-testing/scripts/scaffold_backend_tests.py --write
```

模板位置：
- `docs/dev/skills/aojuai-backend-testing/templates/`

