# 种子数据（Seed）增量脚本模式

> 目标：让“加菜单/权限/演示数据”变得可重复、可审计、可回滚（至少可重复运行不出错）。

## 什么时候用哪个脚本

- **全新库初始化**：`backend/scripts/seed_data.py`
  - 特点：检测 `tenants` 非空会直接退出，只适合“第一次建库”
- **增量补齐（推荐）**：新增 `backend/scripts/seed_<module>.py`
  - 特点：可重复运行；先查存在性，再插入/回填

## 最小增量脚本套路（必须幂等）

1. 查是否存在（按 `path` / `perms` / `title` 等关键字段）
2. 不存在才插入；插入后拿 `RETURNING id`
3. 需要子菜单/按钮时，使用拿到的 `id` 作为 `parent_id`
4. 需要默认授权时，给 `admin` 角色补齐 `role_menus`

## asyncpg + JSONB（重要）

在 Python 脚本里使用 `sqlalchemy.text()` + asyncpg 时：

- ✅ `cast(:meta as jsonb)` / `cast('{}' as jsonb)`
- ❌ `:meta::jsonb`（asyncpg 不支持这种写法）

## 菜单/权限字段要点（当前实现）

- `menus.menu_type`：
  - `"0"`：目录（有 children，通常无 component）
  - `"1"`：页面菜单（有 path/component）
  - `"2"`：按钮权限（不参与动态路由，但会进入登录返回 `permissions`）
- 权限码来源：`menus.perms`
  - 登录时从 `role.menus[*].perms` 汇总到前端 `permissions`

## 参考

- 初始化脚本：`backend/scripts/seed_data.py`
- 菜单模型：`backend/app/domain/menus/models.py`
- 登录返回 permissions：`backend/app/api/v1/endpoints/auth.py`

