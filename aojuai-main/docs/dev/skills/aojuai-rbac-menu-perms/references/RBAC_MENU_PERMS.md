# RBAC 设计与排错（基于 menu.perms）

## 关键事实（排错用）

1. 登录返回的 `permissions` 来自用户角色所绑定的菜单 `menu.perms`
2. `PermissionChecker` 校验的就是这些 code（超级管理员跳过）
3. “按钮不显示”通常是：
   - 后端登录返回缺失该 code（没赋权/菜单未绑定/菜单不 active）
   - 或前端用的是错误 code（拼写不一致）

## 代码定位

- 登录生成权限列表：`backend/app/api/v1/endpoints/auth.py`
- Service 侧权限汇总：`backend/app/domain/users/service.py`（`get_user_permissions`）
- 菜单字段：`backend/app/domain/menus/models.py`（`perms` / `menu_type`）
- API 权限依赖：`backend/app/api/deps.py`（`PermissionChecker`）
- 前端按钮权限：`frontend/src/lib/auth.ts`（`hasPerms`）

## 最小赋权 SQL 思路（仅示例）

1) 插入按钮菜单（`menu_type="2"` + `perms`）  
2) 插入 `role_menus` 关联（给 `admin` 角色）

> 实操更推荐通过“菜单管理页 + 角色管理页”完成，避免手写 SQL。

