# 枚举类型使用规范

## 概述

本项目使用 Python 枚举类型来替代硬编码的状态值、类型值等常量，以提高代码的可维护性、类型安全性和可读性。

## 枚举类型选择

### IntEnum - 整数枚举

用于数据库中存储为整数的字段（如状态码）。

**使用场景：**
- 用户状态 (status)
- 性别 (sex)
- 布尔型状态的数值表示

**示例：**
```python
from enum import IntEnum

class UserStatus(IntEnum):
    """User status enumeration"""
    DISABLED = 0      # 禁用
    ENABLED = 1       # 正常
    PENDING = 2       # 待审核
    REJECTED = 3      # 审核拒绝

class UserSex(IntEnum):
    """User sex enumeration"""
    UNKNOWN = 0       # 未知
    MALE = 1          # 男性
    FEMALE = 2        # 女性
```

### StrEnum - 字符串枚举

用于数据库中存储为字符串的字段（如类型、来源等）。

**使用场景：**
- 权限类型 (permission_type)
- 菜单类型 (menu_type)
- 注册来源 (register_source)

**示例：**
```python
from enum import IntEnum

class UserStatus(IntEnum):
    """User status enumeration"""
    DISABLED = 0      # 禁用
    ENABLED = 1       # 正常
    PENDING = 2       # 待审核（注册待审核）
    REJECTED = 3      # 审核拒绝
```

> 上面是仓里真实存在的枚举（`backend/app/domain/users/models.py`）。
> 旧版本这里举的是 `PermissionType`——**本仓没有 permissions 域**，
> 菜单类型是字符串 `"0"/"1"/"2"`（见 `backend/app/domain/menus/models.py`），
> 照抄那个例子会 import 失败。

### 字符串常量类

对于不需要枚举特性但需要常量定义的场景，可以使用普通类。

**使用场景：**
- 简单的字符串常量集合
- 不需要迭代或验证的常量

**示例：**
```python
class RegisterSource(str):
    """User registration source constants"""
    ADMIN = "admin"   # 管理员创建
    SELF = "self"     # 自助注册
    INVITE = "invite" # 邀请注册
```

## 定义位置

### 原则
枚举应该定义在与其相关的模型文件中，保持就近原则。

**示例：**
```python
# backend/app/domain/users/models.py
from enum import IntEnum

class UserStatus(IntEnum):
    """User status enumeration"""
    DISABLED = 0
    ENABLED = 1
    PENDING = 2
    REJECTED = 3

class User(TenantBaseModel):
    """User Model"""
    __tablename__ = "users"
    
    status: Mapped[int] = mapped_column(
        Integer,
        default=UserStatus.ENABLED,  # 使用枚举作为默认值
        nullable=False,
        comment="Status: 0=disabled, 1=enabled, 2=pending, 3=rejected",
    )
```

## 使用规范

### 1. 在模型中使用

```python
# 定义默认值
status: Mapped[int] = mapped_column(
    Integer,
    default=UserStatus.ENABLED,
    nullable=False,
)

# 在属性方法中使用
@property
def is_active(self) -> bool:
    """Check if user is active"""
    return self.status == UserStatus.ENABLED

@property
def is_pending(self) -> bool:
    """Check if user is pending approval"""
    return self.status == UserStatus.PENDING
```

### 2. 在服务层使用

```python
from app.domain.users.models import User, UserStatus

class UserService:
    async def list_pending_users(self, tenant_id: int):
        """Get pending users"""
        users = await self.get_list(
            tenant_id=tenant_id,
            status=UserStatus.PENDING,  # 使用枚举
        )
        return users
    
    async def audit_user(self, user: User, approved: bool):
        """Audit user registration"""
        if user.status != UserStatus.PENDING:
            raise BusinessError(message="User is not in pending status")
        
        await self.update(user, {
            "status": UserStatus.ENABLED if approved else UserStatus.REJECTED,
        })
```

### 3. 在视图层使用

```python
from app.domain.users.models import UserStatus

@router.post("/login")
async def login(request: LoginRequest, db: DBSession):
    user = await user_service.get_by_username(request.username)
    
    # 使用枚举进行状态检查
    if user.status == UserStatus.PENDING:
        raise UnauthorizedError(message="Your registration is pending approval")
    
    if user.status == UserStatus.REJECTED:
        raise UnauthorizedError(message="Your registration was rejected")
    
    if user.status != UserStatus.ENABLED:
        raise UnauthorizedError(message="User account is disabled")
```

### 4. 枚举验证

对于 StrEnum，在服务层进行验证：

```python
from app.domain.users.models import UserStatus

class PermissionService:
    async def create_permission(
        self,
        permission_type: str,
        **kwargs
    ) -> Permission:
        """Create new permission with type validation"""
        # 验证枚举值
        try:
            status = UserStatus(status_value)
        except ValueError:
            valid_values = [item.value for item in UserStatus]
            raise BusinessError(
                message=f"Invalid permission type: {permission_type}. "
                        f"Must be one of {valid_types}"
            )
        
        # 使用验证后的枚举值
        permission = await self.create({
            "type": perm_type.value,
            **kwargs
        })
        return permission
```

## 命名规范

### 枚举类命名
- 使用 PascalCase（大驼峰）
- 名称应该清晰表达枚举的用途
- 通常以类型、状态等结尾

**示例：**
```python
UserStatus      # ✓ 好
UserSex         # ✓ 好
UserStatus  # ✓ 好
RegisterSource  # ✓ 好

Status          # ✗ 不好 - 太泛化
Type            # ✗ 不好 - 太泛化
```

### 枚举成员命名
- 使用 UPPER_CASE（全大写下划线）
- 名称应该清晰表达含义
- 添加中文注释说明

**示例：**
```python
class UserStatus(IntEnum):
    DISABLED = 0      # ✓ 好 - 清晰的语义
    ENABLED = 1       # ✓ 好
    PENDING = 2       # ✓ 好
    REJECTED = 3      # ✓ 好
    
    # ✗ 不好的命名
    # STATUS_0 = 0    # 没有语义
    # STAT1 = 1       # 缩写不清晰
```

## 文档注释

每个枚举类和成员都应该有清晰的文档注释：

```python
class UserStatus(IntEnum):
    """
    User status enumeration
    
    用户状态枚举，用于标识用户账号的当前状态。
    """
    DISABLED = 0      # 禁用 - 账号被管理员禁用
    ENABLED = 1       # 正常 - 账号正常可用
    PENDING = 2       # 待审核 - 注册后等待管理员审核
    REJECTED = 3      # 审核拒绝 - 注册被管理员拒绝
```

## 迁移指南

### 从硬编码值迁移到枚举

**步骤：**

1. **定义枚举**
```python
# 在 models.py 中定义
class UserStatus(IntEnum):
    DISABLED = 0
    ENABLED = 1
    PENDING = 2
    REJECTED = 3
```

2. **更新模型默认值**
```python
# 修改前
status: Mapped[int] = mapped_column(Integer, default=1)

# 修改后
status: Mapped[int] = mapped_column(Integer, default=UserStatus.ENABLED)
```

3. **更新服务层**
```python
# 修改前
if user.status == 2:
    raise BusinessError(message="User is pending")

# 修改后
if user.status == UserStatus.PENDING:
    raise BusinessError(message="User is pending")
```

4. **更新视图层**
```python
# 修改前
users = await service.get_list(status=1)

# 修改后
users = await service.get_list(status=UserStatus.ENABLED)
```

## 最佳实践

### ✓ 推荐做法

1. **使用枚举成员而不是原始值**
```python
# ✓ 好
if user.status == UserStatus.ENABLED:
    pass

# ✗ 不好
if user.status == 1:
    pass
```

2. **在比较和赋值时使用枚举**
```python
# ✓ 好
user.status = UserStatus.PENDING

# ✗ 不好
user.status = 2
```

3. **提供枚举值列表用于验证**
```python
# ✓ 好
valid_values = [item.value for item in UserStatus]
if permission_type not in valid_types:
    raise ValueError(f"Invalid type. Must be one of {valid_types}")
```

4. **在 Schema 中使用 Literal 类型提示**
```python
from typing import Literal
from pydantic import BaseModel

class UserCreate(BaseModel):
    status: Literal[0, 1, 2, 3] = 1  # 对应 UserStatus 的值
```

### ✗ 避免的做法

1. **不要在多处重复定义相同的枚举**
```python
# ✗ 不好 - 重复定义
class UserStatus(IntEnum):
    ENABLED = 1
    
class AnotherUserStatus(IntEnum):
    ENABLED = 1
```

2. **不要混用枚举和硬编码值**
```python
# ✗ 不好 - 混用
if user.status == UserStatus.ENABLED or user.status == 1:
    pass
```

3. **不要使用魔法数字**
```python
# ✗ 不好
if user.status in [0, 2, 3]:
    pass

# ✓ 好
if user.status in [UserStatus.DISABLED, UserStatus.PENDING, UserStatus.REJECTED]:
    pass
```

## 常见枚举类型

### 项目中已定义的枚举

1. **UserStatus** - 用户状态
   - 位置: `app.domain.users.models`
   - 类型: IntEnum
   - 值: DISABLED(0), ENABLED(1), PENDING(2), REJECTED(3)

2. **UserSex** - 用户性别
   - 位置: `app.domain.users.models`
   - 类型: IntEnum
   - 值: UNKNOWN(0), MALE(1), FEMALE(2)

3. **RegisterSource** - 注册来源
   - 位置: `app.domain.users.models`
   - 类型: str 常量类
   - 值: ADMIN, SELF, INVITE

> 注意：本仓**没有** `PermissionType` / `app.domain.permissions.models`。
> 菜单类型用的是字符串 `"0"`（目录）/ `"1"`（页面）/ `"2"`（按钮），
> 见 `backend/app/domain/menus/models.py`；权限码本身承载在 `menus.perms`。

## 总结

使用枚举类型的核心原则：

1. **类型安全** - 利用 Python 类型系统避免错误
2. **语义化** - 使用有意义的名称而不是魔法数字
3. **集中管理** - 在模型文件中定义，避免重复
4. **一致性** - 在整个项目中统一使用枚举
5. **文档化** - 为每个枚举添加清晰的注释

遵循这些规范可以显著提高代码质量和可维护性。
