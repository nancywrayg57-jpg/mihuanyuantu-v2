"""
AOJU Backend - Operation Logs Endpoints

System-level operation logs for auditing critical actions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.api.deps import CurrentUser, DataScopeCtx, DBSession, PermissionChecker, TenantCtx
from app.core.exceptions import NotFoundError
from app.core.logger import get_logger
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.operation_logs.schemas import (
    OperationLogDetail,
    OperationLogListItem,
    OperationLogStatsResponse,
)
from app.domain.operation_logs.service import OperationLogService

logger = get_logger(__name__)

router = APIRouter()


class OperationLogListQuery(BaseModel):
    """Operation log list query parameters"""

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=200,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )

    module: str | None = None
    action: str | None = None
    status: str | None = None
    username: str | None = None
    user_id: int | None = Field(None, alias="userId")
    start_time: datetime | None = Field(None, alias="startTime")
    end_time: datetime | None = Field(None, alias="endTime")
    # 排序参数
    sort_by: str | None = Field(
        None,
        alias="sortBy",
        description="排序字段: id, created_at, module, action",
    )
    sort_order: str | None = Field(
        None,
        alias="sortOrder",
        description="排序方向: asc, desc",
    )

    model_config = ConfigDict(populate_by_name=True)


class OperationLogStatsQuery(BaseModel):
    """Operation log stats query parameters"""

    module: str | None = None
    action: str | None = None
    start_time: datetime | None = Field(None, alias="startTime")
    end_time: datetime | None = Field(None, alias="endTime")

    model_config = ConfigDict(populate_by_name=True)


@router.get("", response_model=ResponseBase[PageResponse[OperationLogListItem]])
async def list_operation_logs(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    query: OperationLogListQuery = Depends(),
    _: None = Depends(PermissionChecker(["operation_logs:read"])),
) -> dict[str, Any]:
    """Get operation log list with pagination and filters (tenant-scoped, data permission filtered)."""
    # DataScope: filter by team_ids based on user's data permission
    team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids

    service = OperationLogService(db)
    logs, total = await service.list_logs(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        module=query.module,
        action=query.action,
        status=query.status,
        username=query.username,
        user_id=query.user_id,
        start_time=query.start_time,
        end_time=query.end_time,
        team_ids=team_ids,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    logger.info(
        "operation_logs_list_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(logs),
        total=total,
    )

    return SuccessResponse(
        data={
            "list": [service.to_list_item(item) for item in logs],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/stats", response_model=ResponseBase[OperationLogStatsResponse])
async def get_operation_logs_stats(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: OperationLogStatsQuery = Depends(),
    _: None = Depends(PermissionChecker(["operation_logs:read"])),
) -> dict[str, Any]:
    """Get operation log statistics (tenant-scoped)."""
    service = OperationLogService(db)
    total, items = await service.get_stats(
        tenant_id=tenant_ctx.tenant_id,
        start_time=query.start_time,
        end_time=query.end_time,
        module=query.module,
        action=query.action,
    )

    logger.info(
        "operation_logs_stats_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        total=total,
    )

    return SuccessResponse(
        data={
            "total": total,
            "items": [item.model_dump() for item in items],
        }
    )


# ==================== My Data (No Permission Required) ====================


@router.get("/my", response_model=ResponseBase[PageResponse[OperationLogListItem]])
async def list_my_operation_logs(
    current_user: CurrentUser,
    db: DBSession,
    query: OperationLogListQuery = Depends(),
) -> dict[str, Any]:
    """获取当前用户的操作日志（无需权限）"""
    service = OperationLogService(db)
    logs, total = await service.list_logs(
        tenant_id=current_user.tenant_id,
        page=query.page,
        page_size=query.page_size,
        module=query.module,
        action=query.action,
        status=query.status,
        user_id=current_user.id,  # 只查询当前用户的日志
        start_time=query.start_time,
        end_time=query.end_time,
        team_ids=None,  # 不按团队过滤
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    logger.info(
        "my_operation_logs_retrieved",
        user_id=current_user.id,
        count=len(logs),
        total=total,
    )

    return SuccessResponse(
        data={
            "list": [service.to_list_item(item) for item in logs],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/{log_id}", response_model=ResponseBase[OperationLogDetail])
async def get_operation_log_detail(
    log_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["operation_logs:read"])),
) -> dict[str, Any]:
    """Get operation log detail by ID (tenant-scoped)."""
    service = OperationLogService(db)
    log = await service.get_log_by_id(log_id, tenant_ctx.tenant_id)
    if not log:
        raise NotFoundError(message="Operation log not found")

    logger.info(
        "operation_log_detail_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        log_id=log_id,
    )
    return SuccessResponse(data=service.to_detail(log))
