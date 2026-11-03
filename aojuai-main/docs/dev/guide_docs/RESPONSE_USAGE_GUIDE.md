# API 响应封装使用指南

## 概述

项目已添加统一的响应封装类 `SuccessResponse` 和 `ErrorResponse`，用于替代手动构建字典的方式。

## 响应类

### SuccessResponse

成功响应类，基于 `ResponseBase` schema。

**导入方式：**
```python
from app.core.response import SuccessResponse
# 或
from app.core import SuccessResponse
```

**使用示例：**

```python
# 1. 返回单个对象
# 原来：return {"success": True, "data": user}
return SuccessResponse(data=user)

# 2. 返回分页数据
# 原来：return {"success": True, "data": {"list": items, "total": total, ...}}
return SuccessResponse(
    data={
        "list": items,
        "total": total,
        "pageSize": page_size,
        "currentPage": page,
    }
)

# 3. 返回消息
# 原来：return {"success": True, "message": "Operation successful"}
return SuccessResponse(message="Operation successful")

# 4. 返回数据和消息
# 原来：return {"success": True, "data": user, "message": "User created"}
return SuccessResponse(data=user, message="User created")

# 5. 自定义状态码
# 原来：return {"success": True, "data": user, "code": "CREATED"}
return SuccessResponse(data=user, code="CREATED")

# 6. 额外字段（如 count）
# 原来：return {"success": True, "data": items, "count": total}
return SuccessResponse(data=items, count=total)
```

### ErrorResponse

错误响应类，基于 `ErrorSchema`。

**导入方式：**
```python
from app.core.response import ErrorResponse
# 或
from app.core import ErrorResponse
```

**使用示例：**

```python
# 1. 返回错误消息
# 原来：return {"success": False, "message": "Not found", "code": "NOT_FOUND"}
return ErrorResponse(message="Not found", code="NOT_FOUND")

# 2. 返回错误详情
# 原来：return {"success": False, "message": "Validation failed", "details": errors}
return ErrorResponse(message="Validation failed", details=errors)
```

**注意：** 通常应该抛出异常而不是直接返回 `ErrorResponse`。`ErrorResponse` 主要用于不需要抛出异常的错误情况（如某些业务逻辑判断）。

## 迁移示例

### 示例 1：用户列表端点

**修改前：**
```python
@router.post("")
async def get_user_list(query: UserListQuery, db: DBSession) -> dict[str, Any]:
    users, total = await service.list_users(...)
    
    return {
        "success": True,
        "data": {
            "list": [UserService.to_list_item(u) for u in users],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        },
    }
```

**修改后：**
```python
from app.core.response import SuccessResponse

@router.post("")
async def get_user_list(query: UserListQuery, db: DBSession):
    users, total = await service.list_users(...)
    
    return SuccessResponse(
        data={
            "list": [UserService.to_list_item(u) for u in users],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )
```

### 示例 2：获取单个对象

**修改前：**
```python
@router.get("/{user_id}")
async def get_user(user_id: int, db: DBSession) -> dict[str, Any]:
    user = await service.get_by_id(user_id)
    
    if not user:
        return {"success": False, "message": "User not found", "code": "NOT_FOUND"}
    
    return {"success": True, "data": UserService.to_response(user)}
```

**修改后：**
```python
from app.core.response import SuccessResponse, ErrorResponse

@router.get("/{user_id}")
async def get_user(user_id: int, db: DBSession):
    user = await service.get_by_id(user_id)
    
    if not user:
        return ErrorResponse(message="User not found", code="NOT_FOUND")
    
    return SuccessResponse(data=UserService.to_response(user))
```

### 示例 3：删除操作

**修改前：**
```python
@router.delete("/{user_id}")
async def delete_user(user_id: int, db: DBSession) -> dict[str, Any]:
    await service.delete_user(user_id)
    return {"success": True, "message": "User deleted"}
```

**修改后：**
```python
from app.core.response import SuccessResponse

@router.delete("/{user_id}")
async def delete_user(user_id: int, db: DBSession):
    await service.delete_user(user_id)
    return SuccessResponse(message="User deleted")
```

## 响应格式

### 成功响应格式

```json
{
  "success": true,
  "code": "SUCCESS",
  "data": {...},
  "message": "Optional message"
}
```

### 错误响应格式

```json
{
  "success": false,
  "code": "ERROR_CODE",
  "message": "Error message",
  "details": null
}
```

> 错误响应**没有 `data` 字段**（见 `app/core/schemas.py::ErrorResponse`），
> `code` 是字符串常量（如 `FORBIDDEN` / `NOT_FOUND` / `TOO_MANY_REQUESTS`），不是 HTTP 数字码。

## 优势

1. **类型安全**：基于 Pydantic 模型，提供类型检查
2. **一致性**：确保所有 API 响应格式统一
3. **可维护性**：集中管理响应格式，易于修改
4. **简洁性**：减少重复代码，提高可读性
5. **兼容性**：完全兼容现有的字典响应格式

## 注意事项

1. 响应类返回的是 `ORJSONResponse` 对象，FastAPI 会自动处理
2. 可以保留 `response_model` 类型提示，用于 OpenAPI 文档生成
3. 建议逐步迁移，不需要一次性修改所有端点
4. 对于复杂的业务逻辑错误，建议抛出自定义异常而不是返回 `ErrorResponse`
