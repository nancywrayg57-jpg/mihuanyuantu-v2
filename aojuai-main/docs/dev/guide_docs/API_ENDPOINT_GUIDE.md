# API 端点层（View 层）编码规范

## 概述

API 端点层负责处理 HTTP 请求和响应，是前端和后端业务逻辑的桥梁。

**位置：** `backend/app/api/v1/endpoints/*.py`

**核心职责：**
- 接收和验证请求参数
- 调用 Service 层处理业务逻辑
- 处理权限检查和数据权限控制
- 转换和返回响应数据
- 记录操作日志

## 核心原则

1. **薄控制器**：API 层只负责请求/响应处理，业务逻辑在 Service 层
2. **统一响应格式**：使用 [`SuccessResponse()`](../app/core/response.py:11) 和 [`ErrorResponse()`](../app/core/response.py:23)
3. **依赖注入**：使用 FastAPI 的依赖注入获取数据库会话、当前用户、租户上下文、数据权限
4. **权限检查**：使用 [`PermissionChecker`](../app/api/deps.py:188) 进行细粒度权限控制
5. **租户隔离**：使用 [`TenantCtx`](../app/api/deps.py:298) 确定目标租户
6. **数据权限**：使用 [`DataScopeCtx`](../app/api/deps.py:299) 进行团队级数据隔离
7. **操作日志**：使用 [`logger`](../app/core/logger.py) 记录关键操作

## 文件结构模板

```python
"""
AOJU Backend - User Management Endpoints

权限设计:
- 系统管理员 (is_superuser=True): 可以通过 X-Tenant-Id 或 tenant_id 参数管理任意租户的用户
- 租户管理员 (roles 包含 admin): 只能管理本租户的用户
- 细粒度权限控制: 基于权限码（如 user:create, user:update）
- 数据权限控制: 基于团队的数据隔离（只能查看/编辑/删除有权限团队下的用户）
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import AliasChoices, BaseModel, Field

from app.api.deps import (
    CurrentUser,
    DataScopeCtx,
    DBSession,
    PermissionChecker,
    TenantCtx,
)
from app.core.exceptions import BusinessError, ForbiddenError
from app.core.logger import get_logger
from app.core.response import ErrorResponse, SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.users.schemas import UserCreate, UserUpdate, UserResponse, UserListItem
from app.domain.users.service import UserService

logger = get_logger(__name__)

router = APIRouter()


# ============== Schemas ==============

class UserListQuery(BaseModel):
    """User list query parameters"""
    
    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    username: str | None = None
    
    class Config:
        populate_by_name = True


# ============== Endpoints ==============

@router.post("", response_model=ResponseBase[PageResponse[UserListItem]])
async def get_user_list(
    query: UserListQuery,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:read", "user:list"])),
) -> dict[str, Any]:
    """
    Get user list with pagination.

    需要权限: user:read 或 user:list（PermissionChecker 是 OR 语义）
    数据权限: 只能查看有读取权限团队下的用户

    超级管理员可以通过以下方式指定目标租户:
    - 请求头: X-Tenant-Id: {tenant_id}
    - 查询参数: ?tenant_id={tenant_id}
    """
    service = UserService(db)
    
    # 根据数据权限过滤团队
    read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids
    
    users, total = await service.list_users(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        team_ids=read_team_ids,  # 数据权限过滤
    )
    
    logger.info(
        "user_list_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(users),
        total=total
    )
    
    return SuccessResponse(
        data={
            "list": [UserService.to_list_item(u) for u in users],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )
```

## 依赖注入

### 数据库会话

```python
from app.api.deps import DBSession

@router.get("/users")
async def get_users(db: DBSession) -> dict:
    service = UserService(db)
    users = await service.list_users()
    return SuccessResponse(data=users)
```

### 当前用户

```python
from app.api.deps import CurrentUser, CurrentTenantAdmin, CurrentSuperuser

# 任何已登录用户
@router.get("/profile")
async def get_profile(current_user: CurrentUser) -> dict:
    return SuccessResponse(data={"id": current_user.id})

# 租户管理员或系统管理员
@router.post("/users")
async def create_user(current_user: CurrentTenantAdmin, db: DBSession) -> dict:
    # current_user.is_superuser 判断是否为系统管理员
    pass

# 仅系统管理员
@router.post("/tenants")
async def create_tenant(current_user: CurrentSuperuser, db: DBSession) -> dict:
    pass
```

### 租户上下文（TenantCtx）

[`TenantCtx`](../app/api/deps.py:298) 是租户上下文依赖项，用于确定当前操作的目标租户。它支持超级管理员跨租户操作，同时确保普通用户只能操作自己的租户。

**核心属性：**
- `tenant_id`: 目标租户ID（操作将在此租户下执行）
- `is_superuser`: 当前用户是否为超级管理员
- `user_tenant_id`: 用户原始租户ID
- `is_cross_tenant`: 是否跨租户操作（只读属性）

**租户切换规则：**

对于**超级管理员**，目标租户优先级：
1. `X-Tenant-Id` 请求头
2. `tenant_id` 查询参数
3. 用户自身的租户ID

对于**普通用户**：
- 始终使用用户自身的租户ID
- 忽略 `X-Tenant-Id` 和 `tenant_id` 参数

#### 基本使用

```python
from app.api.deps import TenantCtx

@router.get("/users")
async def get_users(
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict:
    """
    获取用户列表
    
    超级管理员可以通过以下方式指定目标租户：
    - 请求头: X-Tenant-Id: 2
    - 查询参数: ?tenant_id=2
    """
    service = UserService(db)
    
    # 使用 tenant_ctx.tenant_id 作为目标租户
    users = await service.list_users(tenant_id=tenant_ctx.tenant_id)
    
    return SuccessResponse(data=users)
```

#### 检查跨租户操作

```python
@router.post("/users/create")
async def create_user(
    data: UserCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict:
    """创建用户"""
    service = UserService(db)
    user = await service.create_user(data, tenant_id=tenant_ctx.tenant_id)
    
    # 记录跨租户操作
    if tenant_ctx.is_cross_tenant:
        logger.warning(
            "cross_tenant_operation",
            user_id=current_user.id,
            user_tenant=tenant_ctx.user_tenant_id,
            target_tenant=tenant_ctx.tenant_id,
            operation="create_user"
        )
    
    return SuccessResponse(data=UserService.to_response(user))
```

#### 限制跨租户操作

某些敏感操作可能需要限制跨租户访问：

```python
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict:
    """删除用户 - 禁止跨租户操作"""
    
    # 即使是超级管理员，也不允许跨租户删除
    if tenant_ctx.is_cross_tenant:
        raise ForbiddenError(message="不允许跨租户删除用户")
    
    service = UserService(db)
    await service.delete_user(user_id, tenant_id=tenant_ctx.tenant_id)
    
    return SuccessResponse(message="User deleted")
```

#### 前端调用示例

**超级管理员跨租户操作：**

> 前端**没有装 axios**，统一用 `apiFetch()`（`frontend/src/lib/api.ts`）。
> 另外用户列表是 **POST** `/api/v1/users`（分页条件在 body），
> 照抄 `GET` 会得到 405。

```typescript
import { apiFetch } from '@/lib/api'

// 超级管理员跨租户：传 tenantId，apiFetch 会带上 X-Tenant-Id
const res = await apiFetch<PageResponse<UserListItem>>('/api/v1/users', {
  method: 'POST',
  session,
  tenantId: 2,
  body: { currentPage: 1, pageSize: 20 },
})
```

**普通用户：**

```typescript
// 普通用户传 tenantId 会被忽略，始终使用自己的租户
await apiFetch('/api/v1/users', { method: 'POST', session, tenantId: 999, body: {} })
```


### 数据权限上下文

```python
from app.api.deps import DataScopeCtx

@router.get("/users")
async def get_users(
    data_scope: DataScopeCtx,
    db: DBSession,
) -> dict:
    """
    DataScopeCtx 提供基于团队的数据权限控制:
    - read_team_ids: 可读取的团队ID列表
    - edit_team_ids: 可编辑的团队ID列表
    - delete_team_ids: 可删除的团队ID列表
    - has_all_read_access: 是否有全部读取权限
    - has_all_edit_access: 是否有全部编辑权限
    - has_all_delete_access: 是否有全部删除权限
    """
    service = UserService(db)
    
    # 列表查询：根据数据权限过滤
    read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids
    users = await service.list_users(team_ids=read_team_ids)
    
    return SuccessResponse(data=users)

@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    data_scope: DataScopeCtx,
    db: DBSession,
) -> dict:
    """单条查询：检查数据权限"""
    service = UserService(db)
    user = await service.get_user_by_id(user_id)
    
    # 检查是否有读取权限
    await data_scope.check_read_permission(user_id, db)
    
    return SuccessResponse(data=user)

@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    data_scope: DataScopeCtx,
    db: DBSession,
) -> dict:
    """更新操作：检查编辑权限"""
    # 检查是否有编辑权限
    await data_scope.check_edit_permission(user_id, db)
    
    # 验证新团队是否有编辑权限
    if data.team_ids is not None and not data_scope.has_all_edit_access:
        for team_id in data.team_ids:
            if not data_scope.can_edit(team_id):
                raise ForbiddenError(message=f"无权将用户分配到团队 {team_id}")
    
    service = UserService(db)
    user = await service.update_user(user_id, data)
    return SuccessResponse(data=user)

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    data_scope: DataScopeCtx,
    db: DBSession,
) -> dict:
    """删除操作：检查删除权限"""
    # 检查是否有删除权限
    await data_scope.check_delete_permission(user_id, db)
    
    service = UserService(db)
    await service.delete_user(user_id)
    return SuccessResponse(message="User deleted")
```

### 权限检查

```python
from app.api.deps import PermissionChecker

# 单个权限
@router.post("/users")
async def create_user(
    _: None = Depends(PermissionChecker(["user:create"])),
) -> dict:
    pass

# 多个权限（OR 关系）
@router.get("/users")
async def get_users(
    _: None = Depends(PermissionChecker(["user:read", "user:list"])),
) -> dict:
    pass
```

## 响应格式

### 使用 SuccessResponse

```python
from app.core.response import SuccessResponse

# 返回单个对象
return SuccessResponse(data=UserService.to_response(user))

# 返回分页数据
return SuccessResponse(
    data={
        "list": [UserService.to_list_item(u) for u in users],
        "total": total,
        "pageSize": query.page_size,
        "currentPage": query.page,
    }
)

# 仅返回消息
return SuccessResponse(message="Operation successful")
```

### 使用 ErrorResponse

```python
from app.core.response import ErrorResponse

if not user:
    return ErrorResponse(message="User not found", code="NOT_FOUND")
```

### 使用自定义异常（推荐）

```python
from app.core.exceptions import NotFoundError, BusinessError, ForbiddenError

if not user:
    raise NotFoundError(message="User not found")

if user.status != UserStatus.ACTIVE:
    raise BusinessError(message="User is not active")

if not data_scope.can_edit(team_id):
    raise ForbiddenError(message="无权操作该团队")
```

## 日志记录

```python
from app.core.logger import get_logger

logger = get_logger(__name__)

@router.post("/users/create")
async def create_user(
    data: UserCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict:
    service = UserService(db)
    user = await service.create_user(data, tenant_ctx.tenant_id)
    
    # 记录操作日志
    logger.info(
        "user_created",
        user_id=current_user.id,
        new_user_id=user.id,
        new_username=user.username,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )
    
    return SuccessResponse(data=UserService.to_response(user))
```

## 常见模式

### 列表查询（带分页和数据权限）

```python
@router.post("", response_model=ResponseBase[PageResponse[UserListItem]])
async def get_user_list(
    query: UserListQuery,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:read", "user:list"])),
) -> dict[str, Any]:
    """
    Get user list with pagination.

    需要权限: user:read 或 user:list（PermissionChecker 是 OR 语义）
    数据权限: 只能查看有读取权限团队下的用户

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = UserService(db)
    
    # 根据数据权限过滤团队
    read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids
    
    users, total = await service.list_users(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        team_ids=read_team_ids,  # 数据权限过滤
    )
    
    logger.info(
        "user_list_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(users),
        total=total
    )
    
    return SuccessResponse(
        data={
            "list": [UserService.to_list_item(u) for u in users],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )
```

### 获取单个资源（带数据权限检查）

```python
@router.get("/{user_id}", response_model=ResponseBase[UserResponse])
async def get_user(
    user_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:read"])),
) -> dict[str, Any]:
    """
    Get user by ID.

    需要权限: user:read
    数据权限: 只能查看有读取权限团队下的用户

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = UserService(db)
    
    user = await service.get_user_by_id(user_id, tenant_ctx.tenant_id)
    
    if not user:
        return ErrorResponse(message="User not found", code="NOT_FOUND")
    
    # 检查数据权限：用户是否属于有读取权限的团队
    await data_scope.check_read_permission(user_id, db)
    
    logger.info(
        "user_retrieved",
        user_id=current_user.id,
        target_user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )
    
    return SuccessResponse(data=UserService.to_response(user))
```

### 创建资源（带数据权限验证）

```python
@router.post("/create", response_model=ResponseBase[UserResponse])
async def create_user(
    data: UserCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:create"])),
) -> dict[str, Any]:
    """
    Create new user.

    需要权限: user:create
    数据权限: 只能将用户分配到有编辑权限的团队

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    # 验证所选团队是否有编辑权限
    if data.team_ids and not data_scope.has_all_edit_access:
        for team_id in data.team_ids:
            if not data_scope.can_edit(team_id):
                raise ForbiddenError(message=f"无权将用户分配到团队 {team_id}")
    
    service = UserService(db)
    
    user = await service.create_user(
        data=data,
        tenant_id=tenant_ctx.tenant_id,
        created_by=current_user.id,
    )
    
    logger.info(
        "user_created",
        user_id=current_user.id,
        new_user_id=user.id,
        new_username=user.username,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )
    
    return SuccessResponse(data=UserService.to_response(user))
```

### 更新资源（带数据权限检查）

```python
@router.put("/{user_id}", response_model=ResponseBase[UserResponse])
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:update"])),
) -> dict[str, Any]:
    """
    Update user.

    需要权限: user:update
    数据权限: 只能编辑有编辑权限团队下的用户，且只能将用户分配到有编辑权限的团队

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    # 检查数据权限：用户是否属于有编辑权限的团队
    await data_scope.check_edit_permission(user_id, db)
    
    # 验证新团队是否有编辑权限
    if data.team_ids is not None and not data_scope.has_all_edit_access:
        for team_id in data.team_ids:
            if not data_scope.can_edit(team_id):
                raise ForbiddenError(message=f"无权将用户分配到团队 {team_id}")
    
    service = UserService(db)
    
    user = await service.update_user(
        user_id=user_id,
        data=data,
        tenant_id=tenant_ctx.tenant_id,
    )
    
    if not user:
        return ErrorResponse(message="User not found", code="NOT_FOUND")
    
    logger.info(
        "user_updated",
        user_id=current_user.id,
        target_user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )
    
    return SuccessResponse(data=UserService.to_response(user))
```

### 删除资源（带数据权限检查）

```python
@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:delete"])),
) -> dict[str, Any]:
    """
    Delete user (soft delete).

    需要权限: user:delete
    数据权限: 只能删除有删除权限团队下的用户

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = UserService(db)
    
    # 检查数据权限：用户是否属于有删除权限的团队
    await data_scope.check_delete_permission(user_id, db)
    
    await service.delete_user(user_id, tenant_ctx.tenant_id)
    
    logger.info(
        "user_deleted",
        user_id=current_user.id,
        target_user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )
    
    return SuccessResponse(message="User deleted")
```

## 最佳实践

### 1. 薄控制器原则

```python
# ✅ 好的做法
@router.post("/users")
async def create_user(data: UserCreate, db: DBSession) -> dict:
    service = UserService(db)
    user = await service.create_user(data)
    return SuccessResponse(data=UserService.to_response(user))

# ❌ 不好的做法 - 业务逻辑在 API 层
@router.post("/users")
async def create_user(data: UserCreate, db: DBSession) -> dict:
    existing = await db.execute(select(User).where(...))
    user = User(**data.model_dump())
    db.add(user)
    await db.flush()
    return SuccessResponse(data={...})
```

### 2. 使用 Service 静态方法转换数据

```python
# ✅ 好的做法
return SuccessResponse(
    data={
        "list": [UserService.to_list_item(u) for u in users],
        "total": total,
    }
)

# ❌ 不好的做法 - 手动构建
return SuccessResponse(
    data={
        "list": [{"id": u.id, "username": u.username} for u in users],
        "total": total,
    }
)
```

### 3. 依赖注入顺序

```python
# ✅ 推荐的参数顺序
@router.post("/users")
async def create_user(
    data: UserCreate,                                    # 1. 请求体
    current_user: CurrentUser,                           # 2. 当前用户
    tenant_ctx: TenantCtx,                               # 3. 租户上下文
    data_scope: DataScopeCtx,                            # 4. 数据权限
    db: DBSession,                                       # 5. 数据库会话
    _: None = Depends(PermissionChecker(["user:create"])), # 6. 权限检查
) -> dict[str, Any]:
    pass
```

### 4. 文档字符串规范

```python
@router.post("/users/create")
async def create_user(...) -> dict[str, Any]:
    """
    Create new user.

    需要权限: user:create
    数据权限: 只能将用户分配到有编辑权限的团队

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    pass
```

## 总结

**API 端点层核心要点：**

1. ✅ **薄控制器**：业务逻辑在 Service 层
2. ✅ **依赖注入**：使用 [`DBSession`](../app/api/deps.py:297), [`CurrentUser`](../app/api/deps.py:294), [`TenantCtx`](../app/api/deps.py:298), [`DataScopeCtx`](../app/api/deps.py:299), [`PermissionChecker`](../app/api/deps.py:188)
3. ✅ **统一响应**：使用 [`SuccessResponse()`](../app/core/response.py:11) 和 [`ErrorResponse()`](../app/core/response.py:23)
4. ✅ **权限检查**：使用 [`PermissionChecker`](../app/api/deps.py:188) 依赖项
5. ✅ **租户隔离**：使用 [`TenantCtx`](../app/api/deps.py:298) 确定目标租户
6. ✅ **数据权限**：使用 [`DataScopeCtx`](../app/api/deps.py:299) 进行团队级数据隔离
7. ✅ **操作日志**：使用 [`logger`](../app/core/logger.py) 记录关键操作
8. ✅ **使用 Service 静态方法**：转换数据格式（`to_response()`, `to_list_item()`）
9. ✅ **优先使用异常**：使用 [`NotFoundError`](../app/core/exceptions.py), [`BusinessError`](../app/core/exceptions.py), [`ForbiddenError`](../app/core/exceptions.py) 等
10. ✅ **类型提示**：所有参数和返回值都有类型提示
11. ✅ **文档字符串**：每个端点都有清晰的文档说明（权限、数据权限、租户切换）
