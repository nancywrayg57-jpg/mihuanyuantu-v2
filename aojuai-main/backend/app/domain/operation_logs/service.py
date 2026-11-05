"""
AOJU Backend - Operation Log Service

Provides tenant-scoped listing and retrieval utilities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.domain.operation_logs.models import OperationLog
from app.domain.operation_logs.schemas import (
    OperationLogDetail,
    OperationLogListItem,
    OperationLogStatsItem,
)
from app.domain.users.models import UserTeam
from app.infrastructure.repository import RepositoryBase

logger = get_logger(__name__)


class OperationLogService(RepositoryBase[OperationLog]):
    """Operation log service (tenant-scoped)"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, OperationLog)

    async def get_log_by_id(self, log_id: int, tenant_id: int) -> OperationLog | None:
        """Get operation log by ID (tenant-scoped)"""
        return await self.get_one(where=[OperationLog.id == log_id, OperationLog.tenant_id == tenant_id])

    async def list_logs(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 10,
        module: str | None = None,
        action: str | None = None,
        status: str | None = None,
        username: str | None = None,
        user_id: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        team_ids: list[int] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[OperationLog], int]:
        """List operation logs (tenant-scoped, paginated, data permission filtered)"""
        where = [OperationLog.tenant_id == tenant_id]

        # Data permission: filter by team_ids via user_teams association
        if team_ids is not None:
            # Subquery: get user_ids that belong to the specified teams
            user_ids_subquery = (
                select(UserTeam.user_id)
                .where(UserTeam.team_id.in_(team_ids))
                .distinct()
            )
            where.append(OperationLog.user_id.in_(user_ids_subquery))

        filters: dict[str, Any] = {}
        if module:
            filters["module"] = ("like", module)
        if action:
            filters["action"] = ("like", action)
        if status:
            filters["status"] = status
        if username:
            filters["username"] = ("like", username)
        if user_id is not None:
            filters["user_id"] = user_id

        if start_time and end_time:
            filters["created_at"] = ("between", [start_time, end_time])
        elif start_time:
            filters["created_at"] = (">=", start_time)
        elif end_time:
            filters["created_at"] = ("<=", end_time)

        # 排序处理
        allowed_sort_fields = {"id", "created_at", "module", "action"}
        order_field = sort_by if sort_by in allowed_sort_fields else "id"
        order_desc = sort_order and sort_order.lower() == "desc"

        return await self.get_list(
            page=page,
            page_size=page_size,
            where=where,
            order_by=order_field,
            order_desc=order_desc,
            return_total=True,
            **filters,
        )

    async def get_stats(
        self,
        tenant_id: int,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        module: str | None = None,
        action: str | None = None,
    ) -> tuple[int, list[OperationLogStatsItem]]:
        """Get aggregated stats (group by action + status)"""
        stmt = (
            select(OperationLog.action, OperationLog.status, func.count(OperationLog.id))
            .where(OperationLog.tenant_id == tenant_id, OperationLog.deleted_at.is_(None))
            .group_by(OperationLog.action, OperationLog.status)
        )
        if start_time:
            stmt = stmt.where(OperationLog.created_at >= start_time)
        if end_time:
            stmt = stmt.where(OperationLog.created_at <= end_time)
        if module:
            stmt = stmt.where(OperationLog.module.like(f"%{module}%"))
        if action:
            stmt = stmt.where(OperationLog.action.like(f"%{action}%"))

        result = await self.db.execute(stmt)
        rows = result.all()

        items = [
            OperationLogStatsItem(action=row[0], status=row[1], count=int(row[2]))
            for row in rows
        ]
        total = sum(item.count for item in items)
        return total, items

    @staticmethod
    def to_list_item(log: OperationLog) -> dict[str, Any]:
        return OperationLogListItem.model_validate(log).model_dump(by_alias=True, exclude_none=False)

    @staticmethod
    def to_detail(log: OperationLog) -> dict[str, Any]:
        return OperationLogDetail.model_validate(log).model_dump(by_alias=True, exclude_none=False)
