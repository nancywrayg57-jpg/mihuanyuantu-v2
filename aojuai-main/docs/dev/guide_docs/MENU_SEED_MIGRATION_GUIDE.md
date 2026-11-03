---
title: 菜单/权限三写指南（seed + Alembic 数据迁移 + 建租户 reconciler）
---

# 菜单/权限三写指南（seed + Alembic 数据迁移 + 建租户 reconciler）

> 本指南用于解决 nextjs-base 最容易“上线后才发现”的问题：**菜单/权限在不同环境不一致**（新装有、老租户没有；或迁移有、新租户没有）。

## 1. 背景：为什么必须“三写”

菜单/权限属于“运行时数据”，它涉及**三类**环境——旧版本这份指南只写了两类，
于是第三类长期是空的：`create_tenant_with_admin()` 曾经**一条 `role_menus` 都不写**，
新建租户开箱没有任何菜单授权，只能靠事后补跑全库 seed。

| 链路 | 场景 | 实现 |
|---|---|---|
| A | 全新部署 / 全库对账 | `backend/scripts/seed_*.py` → 调用 reconciler |
| B | 已有租户升级 | Alembic **数据迁移**，内嵌不可变快照，遍历所有租户幂等补齐 |
| C | 运行时新建租户 | 建租户成功后调用同一个 reconciler |

缺任意一条就会出现「只在某类环境缺菜单」：

- 只写 A → 老租户看不到新菜单
- 只写 B → 全新部署缺菜单
- 漏掉 C → 新建的租户开箱没有授权

**三条链路必须共用同一个 reconciler**（`backend/app/domain/menus/reconciler.py`），
不许出现三套写入实现——一旦分叉就会出现只在某类环境复现的问题。

### seed 是对账语义，不是“有就跳过”

踩过的坑：CMS seed 拿**根菜单**当哨兵，根节点在就整段跳过，
于是子菜单/按钮/授权被删掉后重跑 seed 也修不回来。正确语义是缺的补、
变的改、重复的合、授权补齐（含**父级闭包**：授权子菜单必须补齐它到根的父级，
否则前端菜单树断层）。

对账与修复命令：`python scripts/check_seed_state.py` / `python scripts/repair_menu_state.py`。

## 2. 核心事实（以当前主分支为准）

- 权限码承载在 `menus.perms`，没有独立 `permissions` 表
- 角色授权通过 `role_menus`
- 前端按钮权限通过 `hasAnyPermission(session, [...])` / `RequirePermission` 与后端 `PermissionChecker` 的 perms 保持一致（`v-perms` 是 Vue 时代写法，当前 Next.js 前端没有）

## 3. 菜单结构规范（必须）

### 3.1 菜单信息架构（IA）分类（先分类再落地）

> 这是分支治理中最容易“误删/误挪”的部分：建议把每个菜单先归类，再决定路径、权限与赋权角色。

1. **业务菜单（下游扩展）**
   - 位置：`/<module>`（例如 `/module`）
   - 权限：页面/按钮 perms + `PermissionChecker`（对齐 `menus.perms`）
2. **个人设置菜单（用户自助）**
   - 位置：`/personal/*`
   - 默认策略：`user` 角色应至少拥有个人中心菜单（避免登录后“无菜单可用”）
3. **租户设置菜单（租户级配置）**
   - 位置：`/system/<module>-settings`（强制）
   - 权限：仅租户管理员（默认 `admin` 角色）
   - 数据：写入 `tenants.config.<namespace>` 或租户配置表（带 `tenant_id`）
4. **平台级菜单（超级管理员）**
   - 位置：平台运维入口（例如“租户管理/菜单管理”）
   - 权限：仅 `CurrentSuperuser`；建议菜单 meta 标记 `requireSuperuser=true`

```
Level 1: 目录（menu_type=0）
  └── Level 2: 页面（menu_type=1, path=/xxx, component=views/...）
        └── Level 3: 按钮/权限（menu_type=2, perms=resource:action）
```

当模块存在租户级配置（开关、扣费、AI BaseURL/APIKey/提示词等）：

- 模块设置入口必须挂在：`/system/<module>-settings`
- 且只授权给租户管理员（默认 `admin` 角色）

## 4. seed（新装/新租户）推荐模式

目标：**重复执行不报错、不重复插入**。

建议：

- 初始化脚本：修改 `backend/scripts/seed_data.py`
- 增量脚本：新增 `backend/scripts/seed_<module>.py`（推荐，幂等）

创建顺序（必需）：

1. 父菜单存在（如 `/system`）
2. 插入页面菜单（menu_type=1）
3. 插入按钮 perms（menu_type=2）
4. 写 `role_menus`（确保 role 与 menu 属于同一租户）

## 5. Alembic 数据迁移（已有租户升级）推荐模式

目标：

- **幂等**：重复升级不会插入重复数据
- **安全 no-op**：新装环境迁移执行时可能没有任何租户，迁移应允许“无租户时直接返回”

迁移建议只做“补齐缺失”的插入：

1. 遍历租户：`SELECT id FROM tenants WHERE deleted_at IS NULL`
2. 确保父菜单存在（否则跳过）
3. 插入菜单（查存在性或 `ON CONFLICT DO NOTHING`）
4. 给 `admin` 角色补授权（同样幂等）

### 5.1 迁移文件的演进方式（后续分支）

> seed 只解决“新装/新租户初始化”；**老租户升级只能靠新增 Alembic 迁移**。

- 不要修改已发布的迁移（尤其是 0→1 基线迁移）；后续变更一律新增 revision
- 当新增菜单/按钮 perms：
  - seed 负责新租户初始化（`seed_data.py` / `seed_<module>.py`）
  - Alembic 数据迁移负责老租户补齐（遍历租户 + 幂等插入）
- 可复制模板：`docs/dev/templates/ALEMBIC_MIGRATION_TEMPLATE.md`

## 6. 检查清单（落地前必过）

- [ ] 权限码命名统一：`resource:action`
- [ ] 页面菜单 + 按钮 perms 都已创建
- [ ] `seed_data.py` 或 `seed_<module>.py` 已更新（新装/新租户）
- [ ] Alembic 数据迁移已补齐（老租户升级）
- [ ] 父→子→按钮→赋权顺序正确
- [ ] `role_menus` 插入幂等，且 `role_menus.tenant_id` 与 role 的 tenant 一致（菜单为系统级配置，menu 的 `tenant_id` 可能为固定值如 `1`）

## 7. 关联文档

- `docs/dev/checklists/DEV_CHECKLIST.md`（“菜单权限同步”章节）
- `docs/dev/issues/DEVBASE_PITFALLS.md`（“迁移 vs seed 时序”章节）
- `docs/dev/guide_docs/PERMISSION_CHECKER_GUIDE.md`（perms 约定与鉴权）


## 终态对齐规则（2026-06 跨分支回流）

- **seed 必须复刻迁移链的"终态"**：菜单经历多个迁移（创建→改 path→改 meta）后，seed 的 spec 必须等于最后一个迁移执行后的状态，否则"已迁移租户 + 重跑 seed"会把菜单回退（注意 upsert 是整列覆盖，包括 meta 与 always_show）。
- **三写覆盖矩阵自检**：每个模块过一遍"seed 有？迁移有？建租户有？"三列；菜单在 seed 里但授权列表漏了、或子菜单只在迁移里，分别打挂"新装"和"新租户"路径。
- **trgm/扩展类索引必须加可用性守卫**：先查 `pg_available_extensions`，不可用安全跳过；宝塔编译的 PostgreSQL 默认无 contrib，无守卫会让 `upgrade head` 在新环境硬失败。
