# 数据权限控制指南（团队版）

本文档介绍 AOJUAI nextjs-base 中基于「团队（team）」的数据权限控制机制。

## 概述

- 数据权限由角色字段 `data_range`（范围）与 `data_permissions`（操作权限位）共同决定。
- 在 API 层通过依赖 `DataScopeCtx` 注入 `DataScope`，用于列表过滤与对象级权限校验。
- 超级管理员（`is_superuser=True`）默认拥有全范围与全部操作权限。

## 数据范围（DataRange）

对应 `backend/app/core/data_permission.py` 中的 `DataRange`：

```python
class DataRange(IntEnum):
    SELF_ONLY = 0       # 仅本人数据
    OWN_TEAM = 1        # 本团队数据
    TEAM_AND_BELOW = 2  # 本团队及以下
    CUSTOM_TEAMS = 3    # 自定义团队
    ALL = 4             # 全部数据
```

## 数据操作权限（DataPermission）

`data_permissions` 使用位运算：

```python
class DataPermission(IntEnum):
    READ = 1
    EDIT = 2
    DELETE = 4
```

常见组合：

- `1`：只读
- `3`：读取 + 编辑
- `7`：读取 + 编辑 + 删除

## DataScope

`DataScope` 代表当前用户在「团队维度」的可操作范围。

### 属性

| 属性 | 类型 | 说明 |
|---|---|---|
| `read_team_ids` | `list[int \| str]` | 可读取的团队ID列表，包含 `"*"` 表示全部 |
| `edit_team_ids` | `list[int \| str]` | 可编辑的团队ID列表，包含 `"*"` 表示全部 |
| `delete_team_ids` | `list[int \| str]` | 可删除的团队ID列表，包含 `"*"` 表示全部 |
| `team_and_below_ids` | `list[int]` | 拥有“本团队及以下 + 编辑”时，可创建子团队的团队ID集合 |
| `user_id` | `int \| None` | 当前用户ID |

### 常用方法

- `can_read(team_id)`
- `can_edit(team_id)`
- `can_delete(team_id)`
- `can_create_child_team(parent_team_id)`
- `check_read_permission(user_id, db)`
- `check_edit_permission(user_id, db)`
- `check_delete_permission(user_id, db)`

## 在 API 中使用

### 1）注入 DataScopeCtx

```python
from app.api.deps import DataScopeCtx, DBSession

@router.get("/{user_id}")
async def get_user(user_id: int, data_scope: DataScopeCtx, db: DBSession):
    await data_scope.check_read_permission(user_id, db)
    ...
```

### 2）列表查询按团队过滤

```python
read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids
users, total = await service.list_users(team_ids=read_team_ids, ...)
```

### 3）创建/更新用户时验证 teamIds

当接口允许传入用户所属团队（`teamIds`）时，非全量编辑权限用户需要校验：

- `data_scope.can_edit(team_id)` 是否为 True

## 权限计算逻辑（get_user_data_scope）

`get_user_data_scope` 会：

1. 读取用户的角色与所属团队（`user.teams`）
2. 按角色的 `data_range` 合并出 `team_permissions_map`
3. 生成 `read_team_ids / edit_team_ids / delete_team_ids`

其中：

- `OWN_TEAM`：以用户当前所属团队为范围
- `TEAM_AND_BELOW`：通过递归 CTE 获取团队及所有子团队（`get_team_children_ids`）
- `CUSTOM_TEAMS`：读取 `role_teams` 表（`team_id + permissions`）
- `ALL`：直接返回 `"*"`

## 团队管理与用户管理的差异

- 用户管理：权限检查基于“目标用户所属团队是否在 DataScope 允许范围内”（通过 `user_teams` 关联）。
- 团队管理：直接对“团队ID本身”做权限过滤/校验（`team_ids` 过滤）。

## 相关文件

- `backend/app/core/data_permission.py`
- `backend/app/api/deps.py`
- `backend/app/api/v1/endpoints/users.py`
- `backend/app/api/v1/endpoints/teams.py`
- `backend/app/domain/roles/models.py`（`RoleTeam` / `data_range` / `data_permissions`）
