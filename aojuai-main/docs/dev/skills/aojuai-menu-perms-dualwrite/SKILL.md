---
name: aojuai-menu-perms-dualwrite
description: Add/upgrade menus and permission codes in nextjs-base with the required dual-write (seed + Alembic data migration) and correct ordering. Use when adding module pages, module settings under /system, or button perms.
---

# 菜单/权限新增（双写闭环：seed + Alembic 数据迁移）

用于：新增页面菜单、按钮权限（`menus.perms`）、模块设置入口（`/system/<module>-settings`），并确保 **新装/新租户** 与 **老租户升级** 都生效。

> 规范来源：多次下游扩展踩坑复盘，尤其“模块设置入口”不要落到业务菜单内。

## 0) 先做决策（最常出错）

1. 是否是“模块设置”？
   - 如果是：入口必须在 `/system/<module>-settings`，且 **仅租户管理员** 可见
2. 权限码命名：
   - 统一 `resource:action`（例如 `module:settings`、`assistant:config`、`project:create`）
3. 菜单层级：
   - 目录(0) → 页面(1) → 按钮(2)

## 1) 最小闭环步骤（必须按顺序）

### Step A：定义菜单与 perms

输出一份清单（建议先写在需求里）：

- 页面菜单：
  - `path`
  - `component`（可选；本分支 Next.js 不依赖 `menus.component` 做动态路由映射）
  - `perms`（可选，但按钮 perms 必须有）
- 按钮 perms（menu_type=2）：
  - `perms`（必填）
  - `title`（例如“新增/编辑/删除/配置”）

### Step B：写 seed（新装/新租户）

两种做法二选一：

1) 初始化：更新 `backend/scripts/seed_data.py`  
2) 增量（推荐）：新增 `backend/scripts/seed_<module>.py`（可重复运行）

规则：

- 幂等：先查后插 或 `ON CONFLICT DO NOTHING`
- 顺序：父→子→按钮→赋权
- 赋权：默认给 `admin`（租户管理员）角色补齐 `role_menus`

### Step C：写 Alembic 数据迁移（老租户升级）

关键点：

- 必须遍历所有租户（不要假设只有一个租户）
- 迁移执行时可能没有租户：允许安全 no-op
- 同样按父→子→按钮→赋权顺序，并保持幂等

### Step D：验证（必须）

- 新装链路：
  - `alembic upgrade head` → `python -m scripts.seed_data` → 登录 → 菜单可见
- 老租户链路：
  - 仅 `alembic upgrade head`（不跑 seed）后，老租户也应出现新菜单
- 前端权限：
  - React 条件渲染（例如 `hasAnyPermission(session, [...])`）与后端 `PermissionChecker([...])` 权限码一致

## 2) 常见错误（Review 必查）

- [ ] 只改了 seed，没有 Alembic 数据迁移 → 老租户缺菜单
- [ ] 只写了迁移，没有 seed → 新租户缺菜单
- [ ] 迁移脚本假设一定有租户 → 新装迁移阶段直接报错
- [ ] 把模块设置入口放在业务菜单而不是 `/system/*`
- [ ] Next.js 页面路由文件不存在：`frontend/src/app/(app)/**/page.tsx` → 页面 404
- [ ] 只加了菜单/权限没更新导航入口：`frontend/src/components/layout/app-layout.tsx` → 菜单数据存在但前端无入口

## 3) 参考

- 菜单/权限双写指南：`docs/dev/guide_docs/MENU_SEED_MIGRATION_GUIDE.md`
- 开发自检（含示例）：`docs/dev/checklists/DEV_CHECKLIST.md`
- 常见坑复盘：`docs/dev/issues/DEVBASE_PITFALLS.md`
- RBAC 模型：`docs/dev/skills/aojuai-rbac-menu-perms/SKILL.md`
