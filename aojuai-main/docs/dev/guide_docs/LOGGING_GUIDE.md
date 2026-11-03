# 日志系统使用指南

## 概述

本项目使用 `structlog` 实现结构化日志，支持 JSON 格式输出、请求追踪和分级日志文件。

**位置：** `backend/app/core/logger.py`

## 快速开始

### 1. 导入和使用

```python
from app.core.logger import get_logger

logger = get_logger(__name__)  # 使用模块名作为 logger 名称

# 记录日志
logger.info("user_login", user_id=123, username="john")
logger.warning("high_memory_usage", usage_percent=85)
logger.error("database_error", error=str(e), exc_info=True)
```

### 2. 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 详细调试信息 | 变量值、函数调用 |
| INFO | 一般信息 | 用户登录、操作成功 |
| WARNING | 警告信息 | 资源使用高、配置问题 |
| ERROR | 错误信息 | 异常、失败操作 |

## 使用场景

### 场景 1：用户操作日志

```python
from app.core.logger import get_logger

logger = get_logger(__name__)

@router.post("/login")
async def login(request: LoginRequest, http_request: Request, db: DBSession):
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    # 记录登录尝试
    logger.info(
        "login_attempt",
        username=request.username,
        ip=client_ip,
    )
    
    # 登录失败
    if not user:
        logger.warning(
            "login_failed_user_not_found",
            username=request.username,
            ip=client_ip,
        )
        raise UnauthorizedError(message="Invalid credentials")
    
    # 登录成功
    logger.info(
        "login_success",
        user_id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        ip=client_ip,
    )
    
    return SuccessResponse(data=token_data)
```

**日志输出（JSON 格式）：**
```json
{
  "event": "login_success",
  "user_id": 123,
  "username": "john",
  "tenant_id": 1,
  "ip": "192.168.1.100",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "level": "info"
}
```

### 场景 2：数据库操作日志

```python
from app.core.logger import get_logger

logger = get_logger(__name__)

class UserService:
    async def create_user(self, data: UserCreate, tenant_id: int) -> User:
        logger.info(
            "creating_user",
            username=data.username,
            tenant_id=tenant_id,
        )
        
        try:
            user = User(**data.model_dump())
            self.db.add(user)
            await self.db.flush()
            
            logger.info(
                "user_created",
                user_id=user.id,
                username=user.username,
            )
            
            return user
        except IntegrityError as e:
            logger.error(
                "user_creation_failed",
                username=data.username,
                error=str(e),
                exc_info=True,  # ⚠️ 包含完整的异常堆栈
            )
            raise ConflictError(message="Username already exists")
```

### 场景 3：异常日志

```python
from app.core.logger import get_logger

logger = get_logger(__name__)

async def risky_operation():
    try:
        result = await do_something_risky()
        return result
    except ValueError as e:
        logger.warning(
            "validation_error",
            error=str(e),
            error_type="ValueError",
        )
        raise BusinessError(message=str(e))
    except Exception as e:
        logger.error(
            "unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,  # ⚠️ 重要：包含完整堆栈信息
        )
        raise
```

## 日志命名规范

### 事件命名：使用 snake_case 和 动词_名词 格式

```python
# ✅ 好的命名
logger.info("user_created")
logger.info("password_reset_requested")
logger.warning("rate_limit_exceeded")
logger.error("database_connection_failed")

# ❌ 不好的命名
logger.info("User Created")  # 不要用空格和大写
logger.info("create")        # 太模糊
logger.info("error")         # 不够具体
```

### 字段命名：使用 snake_case

```python
# ✅ 好的字段名
logger.info("user_login", user_id=123, tenant_id=1, ip_address="192.168.1.1")

# ❌ 不好的字段名
logger.info("user_login", userId=123, TenantId=1, IPAddress="192.168.1.1")
```

## 最佳实践

### 1. 使用结构化字段

```python
# ✅ 好的做法
logger.info(
    "user_created",
    user_id=user.id,
    username=user.username,
    tenant_id=user.tenant_id,
)

# ❌ 不好的做法
logger.info(f"User {user.username} created with ID {user.id}")
```

### 2. 记录关键业务操作

```python
# 用户操作
logger.info("user_login", user_id=user.id)
logger.info("user_logout", user_id=user.id)
logger.info("password_changed", user_id=user.id)

# 数据修改
logger.info("record_created", record_id=record.id, type="user")
logger.info("record_updated", record_id=record.id)
logger.info("record_deleted", record_id=record.id)

# 权限操作
logger.info("permission_granted", user_id=user.id, permission="admin")
logger.warning("permission_denied", user_id=user.id, resource="users")
```

### 3. 不要记录敏感信息

```python
# ❌ 不要记录密码、token 等敏感信息
logger.info("user_login", password=password)  # 危险！
logger.info("api_call", api_key=api_key)      # 危险！

# ✅ 只记录非敏感信息
logger.info("user_login", username=username)
logger.info("api_call", endpoint="/api/users")
```

### 4. 使用 exc_info 记录异常

```python
try:
    result = await operation()
except Exception as e:
    logger.error(
        "operation_failed",
        error=str(e),
        exc_info=True,  # ⚠️ 重要：包含完整堆栈
    )
    raise
```

## 日志文件

```
backend/logs/
├── info.log      # INFO 及以上级别
└── error.log     # ERROR 及以上级别
```

## 配置

### 环境变量（.env）

```env
# 启用 SQL 日志
DB_ECHO=true
```

> ⚠️ **`LOG_LEVEL` 不是有效配置**：Settings 里没有这一项，写了也不生效。
> 当前日志级别由 `DEBUG` 决定（见 `backend/app/core/logger.py`）。
> 真要独立的日志级别开关，先在 `backend/app/core/config.py` 的 `Settings` 里加，再来改这段——
> 本仓硬规则是配置一律走 Settings，不读 `os.environ`。

## 日志查询（使用 jq）

```bash
# 查看所有 ERROR 级别日志
cat logs/error.log | jq 'select(.level == "error")'

# 查看特定用户的日志
cat logs/info.log | jq 'select(.user_id == 123)'

# 查看特定事件
cat logs/info.log | jq 'select(.event == "login_success")'

# 统计事件类型
cat logs/info.log | jq -r '.event' | sort | uniq -c
```

## 快速参考

### 常用日志模板

```python
from app.core.logger import get_logger

logger = get_logger(__name__)

# 操作开始
logger.info("operation_started", operation="create_user", user_id=123)

# 操作成功
logger.info("operation_completed", operation="create_user", user_id=123, duration=0.5)

# 操作失败
logger.error("operation_failed", operation="create_user", error=str(e), exc_info=True)

# 性能警告
logger.warning("slow_operation", operation="query", duration=5.2, threshold=5.0)

# 安全事件
logger.warning("security_event", event="failed_login", username="admin", attempts=5)
```

## 总结

**核心原则：**
1. 使用结构化日志（JSON 格式）
2. 记录关键业务操作
3. 不记录敏感信息
4. 使用合适的日志级别
5. 包含足够的上下文信息

**推荐日志内容：**
- ✅ 用户操作（登录、登出、修改）
- ✅ 数据变更（创建、更新、删除）
- ✅ 错误和异常
- ✅ 性能指标
- ✅ 安全事件

**不推荐日志内容：**
- ❌ 密码、token 等敏感信息
- ❌ 过于详细的调试信息（生产环境）
- ❌ 重复的日志
- ❌ 无意义的日志
