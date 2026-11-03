# 接口权限控制使用指南

## 概述

Backend 项目提供了基于权限码（Permission Code）的接口级别访问控制功能，通过 [`PermissionChecker`](../app/api/deps.py:102) 依赖项实现。

## 核心组件

### 1. PermissionChecker 依赖项

位置：[`backend/app/api/deps.py`](../app/api/deps.py:102)

```python
class PermissionChecker:
    """
    权限检查器依赖项
    
    验证当前用户是否拥有所需权限（至少一个）
    超级管理员自动通过所有权限检查
    """
    
    def __init__(self, required_permissions: list[str]):
        """
        Args:
            required_permissions: 权限码列表，用户需要拥有其中至少一个
        """
        self.required_permissions = set(required_permissions)
```

### 2. UserService.get_user_permissions()

位置：[`backend/app/domain/users/service.py`](../app/domain/users/service.py:373)

```python
async def get_user_permissions(self, user_id: int, tenant_id: int | None = None) -> set[str]:
    """
    获取用户的所有权限码
    
    从用户的所有活跃角色中收集权限
    
    Returns:
        权限码集合，例如 {"user:create", "role:read"}
    """
```

## 使用方法

### 基础用法

在 API endpoint 中添加 `PermissionChecker` 依赖项：

```python
from fastapi import APIRouter, Depends
from app.api.deps import CurrentUser, DBSession, PermissionChecker

router = APIRouter()

@router.post("/users", summary="创建用户")
async def create_user(
    data: UserCreate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:create"])),
):
    """
    创建新用户
    
    需要权限：user:create
    """
    # 只有拥有 user:create 权限的用户才能访问此接口
    user_service = UserService(db)
    return await user_service.create_user(data, current_user.tenant_id)
```

### 多权限选择（OR 逻辑）

用户只需拥有**其中一个**权限即可访问：

```python
@router.put("/users/{user_id}", summary="更新用户")
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:update", "user:manage"])),
):
    """
    更新用户信息
    
    需要权限：user:update 或 user:manage（满足其一即可）
    """
    user_service = UserService(db)
    return await user_service.update_user(user_id, data, current_user.tenant_id)
```

### 完整示例

```python
# backend/app/api/v1/endpoints/users.py

from fastapi import APIRouter, Depends
from app.api.deps import CurrentUser, DBSession, PermissionChecker
from app.domain.users.service import UserService
from app.domain.users.schemas import UserCreate, UserUpdate, UserResponse

router = APIRouter()  # 注意：endpoint 模块不带自己的 prefix，prefix 由 app/api/v1/__init__.py 挂载时给
                      # （可选/内置能力都走条件挂载，未安装则整个模块不 import）

@router.get("/", summary="用户列表")
async def list_users(
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:read", "user:list"])),
    page: int = 1,
    page_size: int = 10,
):
    """
    获取用户列表
    
    需要权限：user:read 或 user:list
    """
    user_service = UserService(db)
    users, total = await user_service.list_users(
        tenant_id=current_user.tenant_id,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [UserService.to_list_item(u) for u in users],
        "total": total,
    }

@router.post("/", summary="创建用户")
async def create_user(
    data: UserCreate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:create"])),
):
    """
    创建新用户
    
    需要权限：user:create
    """
    user_service = UserService(db)
    user = await user_service.create_user(
        data=data,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
    )
    return UserService.to_response(user)

@router.get("/{user_id}", summary="用户详情")
async def get_user(
    user_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:read"])),
):
    """
    获取用户详情
    
    需要权限：user:read
    """
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id, current_user.tenant_id)
    if not user:
        raise NotFoundError(message="用户不存在")
    return UserService.to_response(user)

@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:update"])),
):
    """
    更新用户信息
    
    需要权限：user:update
    """
    user_service = UserService(db)
    user = await user_service.update_user(user_id, data, current_user.tenant_id)
    return UserService.to_response(user)

@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:delete"])),
):
    """
    删除用户（软删除）
    
    需要权限：user:delete
    """
    user_service = UserService(db)
    await user_service.delete_user(user_id, current_user.tenant_id)
    return {"message": "用户已删除"}
```

## 权限码命名规范

### 标准格式

```
资源:操作[:范围]
```

### 常见示例

#### 用户管理
- `user:create` - 创建用户
- `user:read` - 查看用户
- `user:update` - 更新用户
- `user:delete` - 删除用户
- `user:list` - 查看用户列表
- `user:manage` - 管理用户（包含所有操作）

#### 角色管理
- `role:create` - 创建角色
- `role:read` - 查看角色
- `role:update` - 更新角色
- `role:delete` - 删除角色
- `role:assign` - 分配角色

#### 权限管理
- `permission:create` - 创建权限
- `permission:read` - 查看权限
- `permission:update` - 更新权限
- `permission:delete` - 删除权限

#### 菜单管理
- `menu:create` - 创建菜单
- `menu:read` - 查看菜单
- `menu:update` - 更新菜单
- `menu:delete` - 删除菜单

#### 租户管理
- `tenant:create` - 创建租户
- `tenant:read` - 查看租户
- `tenant:update` - 更新租户
- `tenant:config` - 配置租户

#### 特殊权限
- `*:*:*` 或 `*.*.*` - 超级权限（所有权限）

## 权限验证逻辑

### 1. 超级管理员

超级管理员（`is_superuser=True`）自动拥有所有权限，无需检查：

```python
if current_user.is_superuser:
    return  # 直接通过
```

### 2. 通配符权限

拥有通配符权限的用户拥有所有权限：

```python
if "*:*:*" in user_permissions or "*.*.*" in user_permissions:
    return  # 直接通过
```

### 3. 权限匹配

用户需要拥有**至少一个**所需权限（OR 逻辑）：

```python
if not (self.required_permissions & user_permissions):
    raise ForbiddenError(message="需要以下权限之一: user:create, user:manage")
```

## 权限数据初始化

> ⚠️ 本仓**没有** `permissions` / `role_permissions` 表，也没有 `Permission`、
> `RolePermission`、`PermissionType` 这些模型。旧版本这一节教的是它们，照抄 import 会直接失败。

真实机制只有三样东西：

| 承载物 | 说明 |
|---|---|
| `menus.perms` | 权限码本身（`menu_type="2"` 的按钮菜单承载） |
| `role_menus` | 角色 → 菜单 的授权（`tenant_id` 跟随 role 的 tenant） |
| `PermissionChecker` | 接口侧校验，见 `backend/app/api/deps.py` |

用户的权限集合由「角色 → role_menus → menus.perms」推导，
见 `app/domain/users/service.py::get_user_permissions(user_id, tenant_id=None)`
（注意有 `tenant_id` 参数，调用时必须传当前租户）。

### 怎么新增权限码

不要手写 SQL，用声明式规格交给 reconciler：

```python
# 模块自己的 access.py（内置能力放 domain/<module>/access.py，
# 可选能力包放 app/capabilities/<code>/access.py）
from app.domain.menus.reconciler import MenuDeclaration, MenuNodeSpec, RoleGrantSpec

ACCESS = MenuDeclaration(
    roots=(
        MenuNodeSpec(
            key="sample-items",
            title="样例条目",
            path="/sample-items",
            menu_type="1",
            perms="sample_items:read",
            children=(
                MenuNodeSpec(key="sample-items-create", title="新建",
                             menu_type="2", perms="sample_items:create",
                             is_visible=False),
            ),
        ),
    ),
    roles=...,          # 角色默认值
    grants=(RoleGrantSpec(...),),
)
```

然后由**三条链路**共用同一个 reconciler 落库（seed / Alembic 数据迁移 / 建租户），
详见 `docs/dev/flows/MENUS_PERMS_DUALWRITE.md`。
可运行的完整样例：`backend/app/capabilities/sample_items/access.py`。

对账与修复：`python scripts/check_seed_state.py`、`python scripts/repair_menu_state.py`。


## 错误处理

### ForbiddenError (403)

当用户没有所需权限时，会抛出 `ForbiddenError`：

```python
{
  "success": false,
  "code": "FORBIDDEN",
  "message": "需要以下权限之一: user:read",
  "details": null
}
```

### UnauthorizedError (401)

当用户未登录或 token 无效时，会抛出 `UnauthorizedError`：

```python
{
    "code": 401,
    "message": "Not authenticated",
}
```

## 最佳实践

### 1. 权限粒度

- ✅ **推荐**：细粒度权限，如 `user:create`, `user:update`
- ❌ **不推荐**：粗粒度权限，如 `user:*`（除非确实需要）

### 2. 权限命名

- ✅ **推荐**：使用清晰的动词，如 `create`, `read`, `update`, `delete`
- ❌ **不推荐**：使用模糊的动词，如 `do`, `handle`

### 3. 权限组合

- ✅ **推荐**：在 `PermissionChecker` 中列出多个相关权限
- ✅ **推荐**：创建 `manage` 权限作为所有操作的快捷方式

```python
# 好的做法
Depends(PermissionChecker(["user:update", "user:manage"]))

# 不好的做法（权限过于宽泛）
Depends(PermissionChecker(["*:*:*"]))
```

### 4. 文档说明

在 API endpoint 的 docstring 中明确说明所需权限：

```python
@router.post("/users")
async def create_user(
    ...
    _: None = Depends(PermissionChecker(["user:create"])),
):
    """
    创建新用户
    
    需要权限：user:create
    """
```

### 5. 超级管理员例外

对于系统级操作，使用 `CurrentSuperuser` 而不是 `PermissionChecker`：

```python
@router.post("/tenants", summary="创建租户")
async def create_tenant(
    data: TenantCreate,
    current_user: CurrentSuperuser,  # 只有超级管理员可以创建租户
    db: DBSession,
):
    """创建新租户（仅超级管理员）"""
    ...
```

## 与现有依赖项的关系

### 依赖项层级

```
1. get_current_user()           # 基础认证
   ├─ get_current_active_superuser()  # 超级管理员
   ├─ get_current_tenant_admin()      # 租户管理员
   └─ PermissionChecker()             # 细粒度权限控制
```

### 使用场景

| 依赖项 | 使用场景 | 示例 |
|--------|---------|------|
| `CurrentUser` | 需要登录即可访问 | 查看个人信息 |
| `CurrentSuperuser` | 仅超级管理员 | 创建租户、系统配置 |
| `CurrentTenantAdmin` | 租户管理员 | 审核用户注册 |
| `PermissionChecker` | 细粒度权限控制 | 创建用户、分配角色 |

### 组合使用

可以同时使用多个依赖项：

```python
@router.post("/users/{user_id}/roles")
async def assign_roles(
    user_id: int,
    role_ids: list[int],
    current_user: CurrentTenantAdmin,  # 必须是租户管理员
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:assign"])),  # 且需要 role:assign 权限
):
    """
    分配角色给用户
    
    需要：租户管理员 + role:assign 权限
    """
    ...
```

## 性能优化

### 1. 权限缓存

对于高频访问的接口，可以考虑缓存用户权限：

```python
# 使用 Redis 缓存用户权限（示例）
from app.infrastructure.cache import get_json, set_json

async def get_user_permissions_cached(user_id: int, db: AsyncSession) -> set[str]:
    cache_key = f"user_permissions:{user_id}"
    
    # 尝试从缓存获取
    cached = await get_json(cache_key)
    if cached:
        return set(cached)
    
    # 从数据库获取
    user_service = UserService(db)
    permissions = await user_service.get_user_permissions(user_id)
    
    # 缓存 5 分钟
    await set_json(cache_key, list(permissions), expire=300)
    
    return permissions
```

### 2. 预加载关系

在 [`UserService.get_user_permissions()`](../app/domain/users/service.py:373) 中已经使用了 `selectinload` 预加载关系，避免 N+1 查询问题。

## 测试

### 单元测试示例

```python
# tests/test_permission_checker.py

import pytest
from app.api.deps import PermissionChecker
from app.core.exceptions import ForbiddenError

@pytest.mark.asyncio
async def test_permission_checker_with_permission(db, test_user):
    """测试拥有权限的用户可以通过检查"""
    # 给用户分配 user:create 权限
    await assign_permission(test_user, "user:create")
    
    checker = PermissionChecker(["user:create"])
    # 不应抛出异常
    await checker(test_user, db)

@pytest.mark.asyncio
async def test_permission_checker_without_permission(db, test_user):
    """测试没有权限的用户无法通过检查"""
    checker = PermissionChecker(["user:create"])
    
    with pytest.raises(ForbiddenError):
        await checker(test_user, db)

@pytest.mark.asyncio
async def test_superuser_bypass(db, superuser):
    """测试超级管理员自动通过所有权限检查"""
    checker = PermissionChecker(["any:permission"])
    # 不应抛出异常
    await checker(superuser, db)
```

## 相关文件

- [`backend/app/api/deps.py`](../app/api/deps.py) - PermissionChecker 实现
- [`backend/app/domain/users/service.py`](../app/domain/users/service.py) - UserService.get_user_permissions()
- 本仓**没有** `permissions` 表/模型：权限码承载在 `menus.perms`，角色授权走 `role_menus`
  （见 `backend/app/domain/menus/models.py` 与 `backend/app/domain/roles/models.py`）
- [`backend/app/domain/roles/models.py`](../app/domain/roles/models.py) - Role 模型
- [`backend/app/core/exceptions.py`](../app/core/exceptions.py) - ForbiddenError 异常

## 总结

`PermissionChecker` 提供了灵活、细粒度的接口权限控制：

✅ **优点**：
- 基于 FastAPI 依赖注入，易于使用
- 支持多权限选择（OR 逻辑）
- 超级管理员自动通过
- 通过 UserService 获取权限，符合分层架构
- 类型安全，IDE 支持良好

✅ **适用场景**：
- 需要细粒度权限控制的业务接口
- 多角色、多权限的复杂系统
- 需要灵活权限组合的场景

✅ **与其他依赖项配合**：
- `CurrentUser` - 基础认证
- `CurrentSuperuser` - 超级管理员
- `CurrentTenantAdmin` - 租户管理员
- `PermissionChecker` - 细粒度权限


## 附录：审计强制规则（2026-06 跨分支回流）

1. **种了权限码就必须有人执行它**：凡 seed/迁移写入 `menus.perms` 的权限码，对应模块端点必须以 `PermissionChecker([...])` 强制执行同一权限码。自检：迁移/seed 里的 perms 码应能在 endpoints 里 grep 到，反向亦然。
2. **decorator 依赖写法**：路由很多时可用 `@router.get(..., dependencies=[Depends(PermissionChecker(["..."]))])`，避免改动函数签名参数顺序。
3. **公开（无登录）端点必须校验资源归属**：token 验证通过 ≠ 可操作任意资源；凡接受客户端传入的资源 id，必须校验其属于被分享对象，**校验字段为空时按不匹配处理（禁止 fail-open）**。
4. **代提交/代操作类接口**：payload 中的"归属用户"字段只有持审核/管理权限的调用者可指定，否则强制为当前用户。
