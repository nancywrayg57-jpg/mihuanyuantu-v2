"""
AOJU Backend - AI Assistant Schemas

Pydantic schemas for AI assistant API
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """创建会话请求"""

    module_code: str | None = Field(
        default=None,
        validation_alias=AliasChoices("module_code", "moduleCode"),
        description="模块标识(可选，默认按路由解析)",
    )
    route_path: str = Field(
        ...,
        validation_alias=AliasChoices("route_path", "routePath"),
        description="当前路由",
    )
    context_params: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("context_params", "contextParams"),
    )

    model_config = ConfigDict(populate_by_name=True)


class SessionResponse(BaseModel):
    """会话响应"""

    id: int
    module_code: str
    module_name: str | None = None
    route_path: str
    context_data: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    """发送消息请求"""

    session_id: int = Field(
        ...,
        validation_alias=AliasChoices("session_id", "sessionId"),
        description="会话ID",
    )
    message: str = Field(..., description="消息内容")

    model_config = ConfigDict(populate_by_name=True)


class MessageResponse(BaseModel):
    """消息响应"""

    id: int
    role: str
    content: str
    action_type: str | None = None
    action_result: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PresetPrompt(BaseModel):
    """Assistant preset prompt descriptor."""

    id: str = Field(..., description="Preset id")
    label: str = Field(..., description="Display label")
    prompt: str = Field(..., description="Prompt text")
    icon: str | None = Field(default=None, description="Optional icon")


class ContextResponse(BaseModel):
    """Assistant module context payload."""

    module_code: str = Field(..., alias="moduleCode")
    module_name: str = Field(..., alias="moduleName")
    route_path: str = Field(..., alias="routePath")
    data: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)


class PresetsResponse(BaseModel):
    """Assistant module presets payload."""

    module_code: str = Field(..., alias="moduleCode")
    module_name: str = Field(..., alias="moduleName")
    route_path: str = Field(..., alias="routePath")
    presets: list[PresetPrompt] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class ChatReplyRequest(BaseModel):
    """发送消息并获取完整响应"""

    session_id: int = Field(
        ...,
        validation_alias=AliasChoices("session_id", "sessionId"),
        description="会话ID",
    )
    message: str = Field(..., min_length=1, max_length=4000, description="消息内容")
    route_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("route_path", "routePath"),
        description="当前页面路由，可选；用于在已有会话中按最新页面上下文继续对话。",
    )
    context_params: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("context_params", "contextParams"),
        description="当前页面上下文参数，可选；仅用于本轮对话上下文。",
    )

    model_config = ConfigDict(populate_by_name=True)


class ChatReplyResponse(BaseModel):
    """同步聊天响应"""

    session_id: int
    module_code: str
    module_name: str
    route_path: str
    reply: str
    used_ai: bool
    context: dict[str, Any] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)
    action: dict[str, Any] | None = None


class ActionRequest(BaseModel):
    """执行操作请求"""

    session_id: int = Field(
        ...,
        validation_alias=AliasChoices("session_id", "sessionId"),
        description="会话ID",
    )
    action_type: str = Field(
        ...,
        validation_alias=AliasChoices("action_type", "actionType"),
        description="动作类型/工具ID",
    )
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class ActionResponse(BaseModel):
    """操作结果响应"""

    success: bool
    action_type: str
    result: dict[str, Any] | None = None
    message: str | None = None
