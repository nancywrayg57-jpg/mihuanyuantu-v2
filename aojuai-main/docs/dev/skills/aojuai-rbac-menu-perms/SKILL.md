---
name: aojuai-rbac-menu-perms
description: AOJUAI RBAC permissions based on Role⇄Menu associations and menu.perms (no permissions table). Use when adding permission codes, menu/button permissions, or troubleshooting PermissionChecker/login permissions.
---

# AOJUAI RBAC（Role⇄Menu + menu.perms）

用于：新增权限码、补齐按钮级权限、排查“接口 403 / 前端按钮不显示 / 登录 permissions 缺失”。

## 当前权限模型（本仓库事实）

- **没有独立的 permissions 表**（历史迁移已移除）
- 权限码来源：`menus.perms`
- 权限赋权关系：`roles ⇄ menus`（`role_menus` 关联表）
- 登录接口会汇总权限码并返回给前端：
  - `backend/app/api/v1/endpoints/auth.py`（`permissions` 字段）
  - 前端用 `frontend/src/lib/auth.ts` 的 `hasPerms()` 控制按钮显示
- 接口鉴权：`PermissionChecker(["resource:action", ...])`
  - 只要用户拥有**任意一个**所需权限码即可通过（OR 逻辑）

## 菜单类型与权限承载

- `menu_type="0"`：目录（组织层级，不建议承载 perms）
- `menu_type="1"`：页面菜单（可承载 perms，也可只承载路由信息）
- `menu_type="2"`：按钮权限（不参与动态路由，但会进入登录返回 `permissions`，最适合承载按钮级 perms）

## 新增一个权限码的标准步骤

1. 规划权限码：`resource:action`（如 `project:create`）
2. 为该权限创建一个按钮菜单（`menu_type="2"`，写入 `perms`）
3. 把该菜单分配给目标角色（通常是 `admin`）
4. 确认：
   - 重新登录后 `permissions` 包含新 code
   - 前端 `hasPerms("project:create")` 生效
   - 后端 `PermissionChecker(["project:create"])` 通过

## 参考

- 详细说明：`docs/dev/skills/aojuai-rbac-menu-perms/references/RBAC_MENU_PERMS.md`
- 快速生成菜单 JSON：`docs/dev/skills/aojuai-rbac-menu-perms/scripts/generate_menu_button_sql.py`

