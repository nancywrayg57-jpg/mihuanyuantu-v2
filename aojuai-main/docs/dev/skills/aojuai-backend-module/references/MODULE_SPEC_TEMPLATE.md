# 新模块规格模板（后端优先）

> 建议：把本模板填写后直接发给 AI，并点名 `aojuai-backend-module`。

## 1) 基本信息

- 模块英文名（domain 目录名）：`__module__`（如 `projects`）
- Model 名（PascalCase）：`__ModelName__`（如 `Project`）
- 表名：`__table__`（如 `projects`）
- 资源前缀（API）：`/api/v1/__resource__`
- 业务说明（1-3 句）：

## 2) 字段清单（建议表格）

| 字段 | 类型 | 可空 | 默认值 | 索引 | 唯一 | 说明 |
|---|---|---|---|---|---|---|
| tenant_id | bigint | 否 | - | 是 | 否 | 多租户隔离 |
| name | varchar(100) | 否 | - | 可选 | 可选 | 名称 |
| ... | ... | ... | ... | ... | ... | ... |

说明：
- JSONB 字段：需要 `server_default="{}"`（见现有模型 `extra/meta`）
- 外键字段：通常需要 `index=True`

## 3) 列表查询（分页 + 筛选 + 排序）

- 分页参数：`currentPage` / `pageSize`
- 筛选项（字段 + 匹配方式 like/eq/in/between）：
- 默认排序：`created_at desc`（或其它）
- 是否需要 DataScope（团队数据权限过滤）：是/否

## 4) 权限码（PermissionChecker）

> 建议遵循 `资源:动作`。

- 列表：`__resource__:read`（或 `__resource__:list`）
- 创建：`__resource__:create`
- 更新：`__resource__:update`
- 删除：`__resource__:delete`
- 其它按钮：`__resource__:export` / `__resource__:import` / ...

## 5) 菜单与前端路由

- 顶级目录：`title/path/icon/menu_type=0`
- 页面菜单：`title/path/icon/menu_type=1`
- 按钮权限：`title/perms/menu_type=2`（不会出现在路由，但会进入登录返回的 `permissions`）

本分支前端（Next.js）说明：

- 路由以文件结构为准：`frontend/src/app/(app)/<path>/page.tsx`
- 菜单必须由后端输出并按权限过滤：`GET /api/v1/menus/routes`
- 不再依赖 `menus.component` 做动态路由映射（可留空或用于管理端展示）

## 6) 演示模式（只读）

- 本模块的“读语义 POST（分页查询）”接口路径：
- 是否需要加入 demo allowlist（否则演示模式下会被前端拦截）：

## 7) 种子数据（可选）

- 是否需要默认菜单：是/否
- 是否需要给 `admin` 角色默认授权：是/否
- 是否需要演示数据：是/否（说明体量与生成规则）
