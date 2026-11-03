"""
AOJU Backend - Operation Log Schemas
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OperationLogListItem(BaseModel):
    """Operation log list item schema"""

    id: int
    user_id: int | None = Field(None, alias="userId")
    username: str | None = None
    module: str
    action: str
    target_type: str | None = Field(None, alias="targetType")
    target_id: int | None = Field(None, alias="targetId")
    method: str | None = None
    path: str | None = None
    ip: str | None = None
    status: str
    status_code: int | None = Field(None, alias="statusCode")
    duration_ms: int | None = Field(None, alias="durationMs")
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class OperationLogDetail(BaseModel):
    """Operation log detail schema"""

    id: int
    tenant_id: int = Field(..., alias="tenantId")

    user_id: int | None = Field(None, alias="userId")
    username: str | None = None

    module: str
    action: str
    target_type: str | None = Field(None, alias="targetType")
    target_id: int | None = Field(None, alias="targetId")

    method: str | None = None
    path: str | None = None
    ip: str | None = None
    user_agent: str | None = Field(None, alias="userAgent")

    status: str
    status_code: int | None = Field(None, alias="statusCode")
    error_message: str | None = Field(None, alias="errorMessage")

    request_data: dict[str, Any] | None = Field(None, alias="requestData")
    response_data: dict[str, Any] | None = Field(None, alias="responseData")
    duration_ms: int | None = Field(None, alias="durationMs")
    extra: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class OperationLogStatsItem(BaseModel):
    """Aggregated stats item"""

    action: str
    status: str
    count: int


class OperationLogStatsResponse(BaseModel):
    """Operation log stats response"""

    total: int
    items: list[OperationLogStatsItem]
