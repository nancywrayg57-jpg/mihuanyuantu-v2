# Service 层编码规范

## 概述

Service 层负责业务逻辑处理，是连接 API 层和数据库层的桥梁。

**位置：** `backend/app/domain/*/service.py`（内置能力）、`backend/app/capabilities/<code>/service.py`（可选能力包）

**核心特点：** 所有 Service 类都必须继承 [`RepositoryBase`](../app/infrastructure/repository/base.py)，复用通用的 CRUD 方法。

## 核心原则

1. **继承 RepositoryBase**：所有 Service 必须继承 `RepositoryBase[ModelType]`
2. **复用基类方法**：优先使用基类提供的 CRUD 方法
3. **只用 flush()**：不使用 `commit()`，由 API 层的 [`get_db()`](../app/infrastructure/database/session.py:15) 管理事务
4. **返回 ORM 对象**：返回数据库模型对象，由 API 层转换为响应格式
5. **租户隔离**：多租户场景下，**每个查询都必须自己带上租户过滤条件**。
   这一条不要指望基类：`RepositoryBase` 不知道"当前租户是谁"，
   交给它会让越权变成隐式行为。软删除过滤在基类里，租户过滤在本层——这是分工。

可运行的完整样例：`backend/app/capabilities/sample_items/service.py`；
`backend/scripts/new_module.py` 生成的 service 也按这套约定出厂，并自带一条契约测试
（断言继承了 `RepositoryBase`、且源码里有 `tenant_id`）。

## Service 类结构

### 标准模板

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ConflictError, BusinessError
from app.domain.users.models import User
from app.domain.users.schemas import UserCreate, UserUpdate
from app.infrastructure.repository import RepositoryBase


class UserService(RepositoryBase[User]):
    """
    用户业务逻辑层
    
    继承 RepositoryBase 获得通用的 CRUD 方法，
    同时提供用户相关的业务逻辑处理。
    """
    
    def __init__(self, db: AsyncSession):
        # ✅ 调用父类构造函数，传入 db 和模型类
        super().__init__(db, User)
        
        # ✅ 定义默认加载选项（预加载关联）
        self._default_options = [
            selectinload(User.roles),
            selectinload(User.organization),
        ]
    
    # ==================== 查询方法 ====================
    
    async def get_user_by_id(self, user_id: int, tenant_id: int) -> User | None:
        """根据 ID 获取用户（限定租户）"""
        # ✅ 使用基类的 get_one 方法
        return await self.get_one(
            where=[User.id == user_id, User.tenant_id == tenant_id],
            options=self._default_options,
        )
    
    async def get_by_username(self, username: str, tenant_id: int) -> User | None:
        """根据用户名获取用户（限定租户）"""
        # ✅ 使用基类的 get_one 方法，支持 where 和 kwargs 混合
        return await self.get_one(
            where=[User.tenant_id == tenant_id],
            username=username,  # kwargs 会被转换为相等条件
        )
    
    async def list_users(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 10,
        username: str | None = None,
        status: int | None = None,
    ) -> tuple[list[User], int]:
        """获取用户列表（带分页）"""
        where = [User.tenant_id == tenant_id]
        filters = {}
        
        # ✅ 使用 filters 字典构建复杂查询条件
        if username:
            filters["username"] = ("like", username)  # LIKE 查询
        if status is not None:
            filters["status"] = status  # 相等查询
        
        # ✅ 使用基类的 get_list 方法
        users, total = await self.get_list(
            page=page,
            page_size=page_size,
            where=where,
            options=self._default_options,
            order_by="created_at",
            order_desc=True,
            return_total=True,
            **filters,
        )
        
        return users, total
    
    # ==================== 创建方法 ====================
    
    async def create_user(
        self,
        data: UserCreate,
        tenant_id: int,
    ) -> User:
        """创建用户"""
        # 业务验证
        existing = await self.get_by_username(data.username, tenant_id)
        if existing:
            raise ConflictError(message=f"Username '{data.username}' already exists")
        
        # ✅ 使用基类的 create 方法
        user = await self.create({
            "tenant_id": tenant_id,
            "username": data.username,
            "password_hash": hash_password(data.password),
            "nickname": data.nickname,
            "email": data.email,
        })
        
        # 关联数据处理
        if data.role_ids:
            await self._assign_roles(user, data.role_ids, tenant_id)
        
        # ✅ 刷新对象以获取最新数据
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    # ==================== 更新方法 ====================
    
    async def update_user(
        self,
        user_id: int,
        data: UserUpdate,
        tenant_id: int,
    ) -> User:
        """更新用户"""
        user = await self.get_user_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundError(message="User not found")
        
        # ✅ 使用基类的 update 方法
        update_data = data.model_dump(exclude_unset=True, exclude={"role_ids"})
        await self.update(user, update_data)
        
        # 处理关联数据
        if data.role_ids is not None:
            await self._clear_roles(user)
            await self._assign_roles(user, data.role_ids, tenant_id)
        
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    # ==================== 删除方法 ====================
    
    async def delete_user(self, user_id: int, tenant_id: int) -> None:
        """删除用户（软删除）"""
        user = await self.get_user_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundError(message="User not found")
        
        # ✅ 使用基类的 delete 方法（自动软删除）
        await self.delete(user)
    
    # ==================== 辅助方法 ====================
    
    async def _assign_roles(
        self,
        user: User,
        role_ids: list[int],
        tenant_id: int,
    ) -> None:
        """分配角色给用户"""
        for role_id in role_ids:
            user_role = UserRole(
                user_id=user.id,
                role_id=role_id,
                tenant_id=tenant_id,
            )
            self.db.add(user_role)
        await self.db.flush()
    
    # ==================== 数据转换方法 ====================
    
    @staticmethod
    def to_response(user: User) -> dict:
        """转换为响应格式"""
        return {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "email": user.email,
            "roles": [
                {"id": role.id, "name": role.name, "code": role.code}
                for role in user.roles
            ] if user.roles else [],
            "createdAt": user.created_at.isoformat() if user.created_at else None,
        }
```

## RepositoryBase 提供的方法

### 查询方法

```python
# 根据 ID 查询
user = await self.get_by_id(
    id=1,
    options=[selectinload(User.roles)],  # 预加载关联
    raise_not_found=True,  # 未找到时抛出异常
    include_deleted=False,  # 是否包含已删除数据
)

# 根据条件查询单条
user = await self.get_one(
    where=[User.tenant_id == 1],  # 原始 WHERE 条件
    username="admin",  # kwargs 相等查询
    options=[selectinload(User.roles)],
)

# 列表查询（带分页）
users, total = await self.get_list(
    page=1,
    page_size=10,
    where=[User.tenant_id == 1],
    username=("like", "admin"),  # LIKE 查询
    status=1,  # 相等查询
    order_by="created_at",
    order_desc=True,
    return_total=True,
)

# 计数
count = await self.get_count(
    where=[User.tenant_id == 1],
    status=1,
)
```

### 创建方法

```python
# 创建单条
user = await self.create({
    "username": "admin",
    "email": "admin@example.com",
})

# 批量创建
await self.create_batch([
    {"username": "user1", "email": "user1@example.com"},
    {"username": "user2", "email": "user2@example.com"},
])
```

### 更新方法

```python
# 更新对象
user = await self.get_by_id(1)
await self.update(user, {
    "email": "new@example.com",
    "nickname": "New Name",
})
```

### 删除方法

```python
# 软删除
user = await self.get_by_id(1)
await self.delete(user)  # 自动设置 deleted_at

# 根据 ID 软删除
await self.delete_by_id(1)

# 批量软删除
await self.delete_batch([1, 2, 3])

# 永久删除（慎用）
await self.delete_permanently(user)
```

## 过滤条件语法

[`RepositoryBase._build_filter_conditions()`](../app/infrastructure/repository/base.py:452) 支持以下过滤语法：

```python
# 简单相等
await self.get_list(status=1)

# LIKE 查询
await self.get_list(username=("like", "admin"))

# IN 查询
await self.get_list(status=("in", [1, 2, 3]))

# 范围查询
await self.get_list(created_at=("between", [start_date, end_date]))

# 不等于
await self.get_list(status=("!=", 0))

# 大于/小于
await self.get_list(age=(">", 18))
await self.get_list(age=(">=", 18))
await self.get_list(age=("<=", 60))

# IS NULL / IS NOT NULL
await self.get_list(deleted_at=("is", None))
await self.get_list(email=("is_not", None))
```

## 最佳实践

### 1. 必须继承 RepositoryBase

```python
# ✅ 好的做法
class UserService(RepositoryBase[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

# ❌ 不好的做法 - 不继承 RepositoryBase
class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
```

### 2. 定义默认加载选项

```python
# ✅ 好的做法 - 避免 N+1 查询
class UserService(RepositoryBase[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)
        self._default_options = [
            selectinload(User.roles),
            selectinload(User.organization),
        ]
    
    async def get_user_by_id(self, user_id: int) -> User | None:
        return await self.get_one(
            where=[User.id == user_id],
            options=self._default_options,  # 使用默认选项
        )

# ❌ 不好的做法 - 每次都重复定义
async def get_user_by_id(self, user_id: int) -> User | None:
    return await self.get_one(
        where=[User.id == user_id],
        options=[selectinload(User.roles), selectinload(User.organization)],
    )
```

### 3. 租户隔离

```python
# ✅ 好的做法 - 始终加上租户过滤
async def get_user_by_id(self, user_id: int, tenant_id: int) -> User | None:
    return await self.get_one(
        where=[User.id == user_id, User.tenant_id == tenant_id],
    )

# ❌ 不好的做法 - 忘记租户隔离
async def get_user_by_id(self, user_id: int) -> User | None:
    return await self.get_one(where=[User.id == user_id])
```

### 4. 使用静态方法进行数据转换

```python
# ✅ 好的做法
class UserService(RepositoryBase[User]):
    @staticmethod
    def to_response(user: User) -> dict:
        return {
            "id": user.id,
            "username": user.username,
        }
    
    @staticmethod
    def to_list_item(user: User) -> dict:
        return {
            "id": user.id,
            "username": user.username,
        }

# API 层使用
return SuccessResponse(data=UserService.to_response(user))
```

### 5. 业务逻辑验证

```python
# ✅ 好的做法 - 先验证，再操作
async def create_user(self, data: UserCreate, tenant_id: int) -> User:
    # 业务验证
    existing = await self.get_by_username(data.username, tenant_id)
    if existing:
        raise ConflictError(message="Username already exists")
    
    # 创建对象
    return await self.create({
        "tenant_id": tenant_id,
        "username": data.username,
    })

# ❌ 不好的做法 - 依赖数据库约束
async def create_user(self, data: UserCreate, tenant_id: int) -> User:
    try:
        return await self.create({
            "tenant_id": tenant_id,
            "username": data.username,
        })
    except IntegrityError:
        raise ConflictError(message="Username already exists")
```

### 6. 分离公共逻辑和租户特定逻辑

```python
# ✅ 好的做法 - 提供两个版本
async def update_user(self, user_id: int, data: UserUpdate, tenant_id: int) -> User:
    """更新用户（限定租户）"""
    user = await self.get_user_by_id(user_id, tenant_id)
    if not user:
        raise NotFoundError(message="User not found")
    return await self._do_update(user, data)

async def update_user_any_tenant(self, user_id: int, data: UserUpdate) -> User:
    """更新用户（跨租户，系统管理员用）"""
    user = await self.get_by_id(user_id)
    if not user:
        raise NotFoundError(message="User not found")
    return await self._do_update(user, data)

async def _do_update(self, user: User, data: UserUpdate) -> User:
    """执行更新操作（内部方法）"""
    await self.update(user, data.model_dump(exclude_unset=True))
    await self.db.flush()
    await self.db.refresh(user)
    return user
```

## 常见模式

### 模式 1：带租户隔离的查询

```python
async def get_user_by_id(self, user_id: int, tenant_id: int) -> User | None:
    """租户隔离查询"""
    return await self.get_one(
        where=[
            User.id == user_id,
            User.tenant_id == tenant_id,  # 租户隔离
        ],
        options=self._default_options,
    )
```

### 模式 2：复杂过滤的列表查询

```python
async def list_users(
    self,
    tenant_id: int,
    page: int = 1,
    page_size: int = 10,
    username: str | None = None,
    status: int | None = None,
    organization_id: int | None = None,
) -> tuple[list[User], int]:
    """复杂过滤查询"""
    where = [User.tenant_id == tenant_id]
    filters = {}
    
    if username:
        filters["username"] = ("like", username)
    if status is not None:
        filters["status"] = status
    if organization_id:
        filters["organization_id"] = organization_id
    
    return await self.get_list(
        page=page,
        page_size=page_size,
        where=where,
        options=self._default_options,
        order_by="created_at",
        order_desc=True,
        return_total=True,
        **filters,
    )
```

### 模式 3：关联数据处理

```python
async def create_user_with_roles(
    self,
    data: UserCreate,
    tenant_id: int,
) -> User:
    """创建用户并分配角色"""
    # 创建用户
    user = await self.create({
        "tenant_id": tenant_id,
        "username": data.username,
    })
    
    # 分配角色
    if data.role_ids:
        await self._assign_roles(user, data.role_ids, tenant_id)
    
    # 刷新并返回
    await self.db.flush()
    await self.db.refresh(user)
    return user

async def _assign_roles(
    self,
    user: User,
    role_ids: list[int],
    tenant_id: int,
) -> None:
    """分配角色（辅助方法）"""
    for role_id in role_ids:
        user_role = UserRole(
            user_id=user.id,
            role_id=role_id,
            tenant_id=tenant_id,
        )
        self.db.add(user_role)
    await self.db.flush()
```

### 模式 4：跨 Repository 查询

```python
async def list_users_with_tenant_info(
    self,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[User], int]:
    """查询用户并附加租户信息"""
    # 查询用户
    users, total = await self.get_list(
        page=page,
        page_size=page_size,
        return_total=True,
    )
    
    if users:
        # 获取租户信息
        tenant_ids = list(set(u.tenant_id for u in users))
        tenant_repo = RepositoryBase(self.db, Tenant)
        tenants = await tenant_repo.get_list(
            page_size=0,  # 不分页
            where=[Tenant.id.in_(tenant_ids)],
        )
        
        # 附加租户信息
        tenant_map = {t.id: t for t in tenants}
        for user in users:
            user._tenant_info = tenant_map.get(user.tenant_id)
    
    return users, total
```

## 错误处理

### 使用自定义异常

```python
from app.core.exceptions import NotFoundError, ConflictError, BusinessError

# 资源不存在
if not user:
    raise NotFoundError(message="User not found")

# 资源冲突
if existing:
    raise ConflictError(message="Username already exists")

# 业务逻辑错误
if user.status != UserStatus.ACTIVE:
    raise BusinessError(message="User is not active")
```

## 事务管理

Service 层**不应该**调用 `commit()`，所有事务由 API 层的 [`get_db()`](../app/infrastructure/database/session.py:15) 统一管理。

详见：[数据库事务管理指南](./DATABASE_TRANSACTION_GUIDE.md)

```python
# ✅ 好的做法 - 只使用 flush()
async def create_user(self, data: UserCreate) -> User:
    user = await self.create(data.model_dump())
    await self.db.flush()  # ✅ 发送到数据库但不提交
    await self.db.refresh(user)
    return user

# ❌ 不好的做法 - 不要在 Service 层 commit
async def create_user(self, data: UserCreate) -> User:
    user = await self.create(data.model_dump())
    await self.db.commit()  # ❌ 错误！
    return user
```

## 总结

**Service 层核心要点：**

1. ✅ **必须继承** [`RepositoryBase[ModelType]`](../app/infrastructure/repository/base.py:25)
2. ✅ **复用基类方法**：`get_one()`, `get_list()`, `create()`, `update()`, `delete()`
3. ✅ **定义默认加载选项**：避免 N+1 查询
4. ✅ **只使用 `flush()`**，不使用 `commit()`
5. ✅ **租户隔离**：多租户场景下必须加租户过滤
6. ✅ **返回 ORM 对象**，不返回字典
7. ✅ **提供静态方法**进行数据转换
8. ✅ **业务逻辑验证**在数据库操作之前
9. ✅ **使用自定义异常**进行错误处理
