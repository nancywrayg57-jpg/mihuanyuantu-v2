"""
AOJU Backend - Unified Response Classes

统一的响应封装，基于 core.schemas 中的 Pydantic 模型
"""
from typing import Any

import orjson
from fastapi import status as http_status
from starlette.responses import JSONResponse

from app.core.schemas import ResponseBase, ErrorResponse as ErrorSchema


class AppORJSONResponse(JSONResponse):
    """Project-local ORJSON response to avoid FastAPI's deprecated wrapper."""

    def render(self, content: Any) -> bytes:
        return orjson.dumps(
            content,
            option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY,
        )


class SuccessResponse(AppORJSONResponse):
    """
    成功响应类 - 基于 ResponseBase schema
    
    Usage:
        # 替换: return {"success": True, "data": user}
        return SuccessResponse(data=user)
        
        # 替换: return {"success": True, "data": {"list": items, ...}, "count": total}
        return SuccessResponse(data={"list": items, ...}, count=total)
        
        # 替换: return {"success": True, "message": "Operation successful"}
        return SuccessResponse(message="Operation successful")
        
        # 替换: return {"success": True, "data": data, "code": "CUSTOM_CODE"}
        return SuccessResponse(data=data, code="CUSTOM_CODE")
    """

    def __init__(
        self,
        data: Any = None,
        message: str | None = None,
        code: str = "SUCCESS",
        status: int = http_status.HTTP_200_OK,
        **kwargs
    ):
        # 使用 ResponseBase 模型构建响应
        response_model = ResponseBase(
            success=True,
            data=data,
            message=message,
            code=code,
        )
        
        # 转换为字典
        content = response_model.model_dump(exclude_none=False, by_alias=True)
        
        # 支持额外的字段，如 count
        content.update(kwargs)
        
        super().__init__(content=content, status_code=status)


class ErrorResponse(AppORJSONResponse):
    """
    错误响应类 - 基于 ErrorSchema
    
    Usage:
        # 替换: return {"success": False, "message": "Not found", "code": "NOT_FOUND"}
        return ErrorResponse(message="Not found", code="NOT_FOUND")
        
        # 替换: return {"success": False, "message": "Error", "data": None}
        return ErrorResponse(message="Error")
    
    Note: 通常应该抛出异常而不是直接返回 ErrorResponse
    这主要用于不需要抛出异常的错误情况（如某些业务逻辑判断）
    """

    def __init__(
        self,
        message: str,
        code: str = "ERROR",
        status: int = http_status.HTTP_200_OK,
        details: Any = None,
        **kwargs
    ):
        # 使用 ErrorSchema 模型构建响应
        response_model = ErrorSchema(
            success=False,
            code=code,
            message=message,
            details=details,
        )
        
        # 转换为字典
        content = response_model.model_dump(exclude_none=False, by_alias=True)
        
        # 支持额外的字段
        content.update(kwargs)
        
        super().__init__(content=content, status_code=status)
