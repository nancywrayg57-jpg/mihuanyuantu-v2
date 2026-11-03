# 数据库事务管理指南

## 概述

本项目使用 SQLAlchemy 异步 ORM 进行数据库操作，采用统一的事务管理策略。

## 核心原则

**一句话总结：一个请求 = 一个事务，Service 层只用 `flush()`，特殊情况才手动 `commit()`**

## 事务管理架构

### 会话管理

**位置：** `backend/app/infrastructure/database/session.py`

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    数据库会话依赖项
    - 正常完成时自动 commit()
    - 异常时自动 rollback()
    - 支持特殊情况下的手动 commit()
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()  # 正常完成时提交
        except Exception:
            await session.rollback()  # 异常时回滚
            raise
        finally:
            await session.close()
```

## Service 层规范

### ✅ 正确做法：使用 flush()

```python
class UserService:
    async def create_user(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self.db.add(user)
        await self.db.flush()  # ✅ 使用 flush
        await self.db.refresh(user)
        return user
```

### ❌ 错误做法：使用 commit()

```python
async def create_user(self, data: UserCreate) -> User:
    user = User(**data.model_dump())
    self.db.add(user)
    await self.db.commit()  # ❌ 错误：Service 层不应该提交事务
    return user
```

## flush() vs commit()

| 操作 | 作用 | 事务状态 | 使用场景 |
|------|------|----------|----------|
| `flush()` | 将更改发送到数据库 | 事务继续 | Service 层 |
| `commit()` | 提交事务 | 事务结束 | 特殊情况 |

**flush() 的作用：**
1. 将 ORM 对象的更改发送到数据库
2. 生成 ID（如果是自增主键）
3. 触发数据库约束检查
4. **不提交事务**，允许后续操作

## 特殊情况：需要在异常前持久化数据

### 场景：登录失败记录

**位置：** `backend/app/api/v1/endpoints/auth.py`

```python
# 密码验证失败
if not verify_password(request.password, user.password_hash):
    # 更新失败次数
    user.failed_login_count += 1
    if user.failed_login_count >= 5:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
    
    # ⚠️ 必须在抛出异常前提交，否则事务回滚会导致数据丢失
    await db.commit()
    
    # 抛出异常
    raise UnauthorizedError(message="Invalid username or password")
```

**为什么需要手动 commit()？**
- 如果只用 `flush()`，抛出异常时 `get_db()` 会执行 `rollback()`
- 回滚会撤销所有未提交的更改，包括失败次数的更新
- 手动 `commit()` 后，事务已提交，抛出异常不会影响已提交的数据

## 常见错误

### 错误 1：忘记 flush() 就访问生成的 ID

```python
# ❌ 错误
async def create_user(self, data: UserCreate) -> User:
    user = User(**data.model_dump())
    self.db.add(user)
    print(user.id)  # None - 还没有 flush
    return user

# ✅ 正确
async def create_user(self, data: UserCreate) -> User:
    user = User(**data.model_dump())
    self.db.add(user)
    await self.db.flush()  # flush 后才能获取 ID
    print(user.id)  # 有值
    return user
```

### 错误 2：时区不一致

```python
# ❌ 错误
if self.locked_until and self.locked_until > datetime.now():
    # TypeError: can't compare offset-naive and offset-aware datetimes
    return False

# ✅ 正确
from datetime import datetime, timezone

if self.locked_until and self.locked_until > datetime.now(timezone.utc):
    return False
```

## 最佳实践

### 1. 事务边界清晰

```python
@router.post("/users")
async def create_user(data: UserCreate, db: DBSession):
    # 一个请求 = 一个事务
    service = UserService(db)
    user = await service.create_user(data)
    # 自动提交
    return SuccessResponse(data=user)
```

### 2. 使用 refresh() 获取最新数据

```python
async def update_user(self, user_id: int, data: UserUpdate) -> User:
    user = await self.get_by_id(user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    
    await self.db.flush()
    await self.db.refresh(user)  # ✅ 刷新以获取数据库生成的值
    return user
```

### 3. 异常处理

```python
async def risky_operation(self, data: Any) -> Result:
    try:
        result = await self.do_something(data)
        await self.db.flush()
        return result
    except IntegrityError as e:
        # 数据库约束错误
        raise ConflictError(message="数据冲突")
    except Exception as e:
        # 其他错误会自动回滚
        raise
```

## 调试技巧

### 启用 SQL 日志

在 `.env` 中设置：
```env
DB_ECHO=true
```

### 检查事务状态

```python
print(f"In transaction: {db.in_transaction()}")
print(f"Is active: {db.is_active}")
```

## 快速参考

**Service 层模板：**
```python
async def create_entity(self, data: CreateSchema) -> Entity:
    entity = Entity(**data.model_dump())
    self.db.add(entity)
    await self.db.flush()
    await self.db.refresh(entity)
    return entity

async def update_entity(self, entity_id: int, data: UpdateSchema) -> Entity:
    entity = await self.get_by_id(entity_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    await self.db.flush()
    await self.db.refresh(entity)
    return entity

async def delete_entity(self, entity_id: int) -> None:
    entity = await self.get_by_id(entity_id)
    entity.deleted_at = datetime.now(timezone.utc)
    await self.db.flush()
```

**API 层模板：**
```python
@router.post("/entities")
async def create_entity(data: CreateSchema, db: DBSession):
    service = EntityService(db)
    entity = await service.create_entity(data)
    # 不需要手动 commit，get_db() 会自动处理
    return SuccessResponse(data=EntityService.to_response(entity))
```

## 总结

1. **一个请求 = 一个事务**
2. **Service 层只用 `flush()`**
3. **API 层不手动操作事务**
4. **特殊情况才手动 `commit()`**
5. **始终使用带时区的 datetime**
