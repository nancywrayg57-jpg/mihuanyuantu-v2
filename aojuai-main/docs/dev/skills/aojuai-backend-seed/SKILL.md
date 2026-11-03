---
name: aojuai-backend-seed
description: Add AOJUAI backend seed data for new modules (menus, button permissions, default role grants, demo data) using safe, idempotent patterns and JSONB casting.
---

# AOJUAI 后端种子数据（菜单/权限/演示数据）

用于：新模块需要默认菜单、按钮权限、角色赋权、或演示数据。

## 先判断：你在给谁 seed

### 1) 内置能力（core）

- 改 `backend/scripts/seed_data.py`
- **它不会在已有库上退出**：检测到 `tenants` 非空时会跑
  `_backfill_existing_installation()` 做幂等的角色/菜单对账回填
  （旧文档说"直接退出、只适合首次建库"是错的）
- 菜单/权限不要手写 SQL，交给 `backend/app/domain/menus/reconciler.py` 的声明式对账

### 2) 可选能力包（app/capabilities/<code>）

- 不要新建 `scripts/seed_<module>.py`，包**自带** `seed.py`，
  提供 `provision`（新租户）与 `sync`（全库对账），内部同样调用那个 reconciler
- 统一入口：`python -m scripts.capability sync`（只对**已安装**的包生效）
- 可运行样例：`backend/app/capabilities/sample_items/seed.py`

> 手写增量脚本只保留给 core / 历史数据修复；新模块默认走声明式对账。

## 菜单/权限的关键规则

- 菜单类型：目录 `menu_type="0"` / 菜单 `menu_type="1"` / 按钮 `menu_type="2"`
- 权限码：建议 `resource:action`（例如 `project:create`）
- JSONB：raw SQL 时使用 `cast(:meta as jsonb)` / `cast('{}' as jsonb)`

## 推荐增量脚本模板（思路）

1. 查询目标菜单/权限是否存在（按 `perms` 或 `path`）
2. 不存在才插入；插入后保存 `id` 供子菜单/按钮使用
3. 给默认角色补授权（如 `admin` 角色）

参考（可直接复用思路）：`docs/dev/skills/aojuai-backend-seed/references/SEED_PATTERNS.md`

## 参考文件

- 初始化脚本：`backend/scripts/seed_data.py`
- asyncpg JSONB 注意事项：`docs/dev/skills/aojuai-sqlalchemy-async/references/JSONB_ASYNCPG.md`
- 权限码命名：`guide_docs/PERMISSION_CHECKER_GUIDE.md`

## 脚手架（可选）

生成增量 seed 脚本（dry-run 默认）：

```bash
python docs/dev/skills/aojuai-backend-seed/scripts/scaffold_seed_incremental.py --module projects
```
