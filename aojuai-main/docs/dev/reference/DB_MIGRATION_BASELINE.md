---
title: 数据库迁移基线（0→1）
---

# 数据库迁移基线（0→1）

> 目的：为“全新部署（from scratch）”提供一个清晰、可复用、可持续演进的数据库基线，避免历史迁移文件叠加导致的冗余与不一致。

## 1) 基线结论（以当前主分支为准）

- Alembic 基线迁移：`backend/alembic/versions/0001_initial_schema.py`
- 模块增量迁移：在 `backend/alembic/versions/` 里 **持续新增 revision**（通常包含 schema migration + 必要的数据迁移）
- 初始化种子数据：`backend/scripts/seed_data.py`
- 菜单/权限必须三写（seed / 迁移 / 建租户，共用 reconciler）：`docs/dev/flows/MENUS_PERMS_DUALWRITE.md` + `docs/dev/guide_docs/MENU_SEED_MIGRATION_GUIDE.md`

## 2) 关键约束（必须遵守）

### 2.1 迁移 vs seed 的职责边界

- **Alembic**：负责表结构/字段/索引/约束（schema）
- **Seed**：负责新装/新租户初始化数据（menus/role_menus/default tenant/admin 等）
- **新增菜单/权限**：必须同时覆盖
  - 新装/新租户（seed）
  - 老租户升级（Alembic 数据迁移）

### 2.2 关联表（Association Tables）规范

当前主分支对“多对多关联表”使用 `AssociationBaseModel`：

- 无 `id`、无 `created_at/updated_at/deleted_at`
- 使用复合主键避免重复数据

对应表：`user_roles`、`user_teams`、`role_menus`、`role_teams`、`user_group_members`

## 3) 为什么要做基线重建（从 0 构建）

在历史演进中，迁移文件可能出现：

- 文件命名与实际内容不一致
- 关联表字段冗余（如额外 id/timestamps）导致重复数据风险
- Alembic/ORM 元数据注册不完整导致 autogenerate 不可用

本基线把“可运行的最终结构”收敛到一个 0→1 迁移，方便后续分支在此基础上增量演进。

## 4) 最小执行顺序（新装）

1. `alembic upgrade head`
2. `python -m scripts.seed_data`

> `AUTO_INIT_DB=true` 仅用于本地快速启动（dev bootstrap），生产/严肃环境建议只使用 Alembic。

## 5) 后续分支如何“增量更新”迁移（必须）

> 关键点：**seed 只负责初始化**；后续演进全部靠 **新增 Alembic 迁移文件**（schema + 必要的数据迁移）。

### 5.1 不要修改已发布的基线迁移

- `0001_initial_schema.py` 作为 0→1 基线，一旦进入主分支并被环境使用，原则上不再修改。
- 后续变更一律 **新增 revision**（例如 `alembic revision -m "add_xxx"`），让旧环境能沿迁移链升级。

> 若确实需要重写基线，只能以“破坏性升级/重建库”为前提，并在发布说明中明确。

### 5.2 新增功能时的推荐动作

- **表结构/字段/索引/约束**：新增 Alembic revision（schema migration）
- **需要补齐已有租户的数据**（如新增菜单、默认配置、权限授权）：在同一个 revision 或独立 revision 里写 **数据迁移**，并保证：
  - 幂等（可重复执行不重复插入）
  - 无租户时 no-op（新装可能尚未 seed 租户）
- 可复制模板：`docs/dev/templates/ALEMBIC_MIGRATION_TEMPLATE.md`

### 5.3 菜单/权限的“数据迁移”是三条链路之一

当后续分支新增页面菜单/按钮 perms 时：

- `seed_data.py`（或 `seed_<module>.py`）：覆盖新装/新租户
- Alembic 数据迁移：覆盖老租户升级（见 `docs/dev/flows/MENUS_PERMS_DUALWRITE.md`）
