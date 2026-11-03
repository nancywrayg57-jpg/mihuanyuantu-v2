"""
AOJU Backend - Notification Service

Provides tenant-scoped notification CRUD and read-state management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notifications.models import Notification
from app.domain.notifications.schemas import NotificationDetail, NotificationListItem
from app.infrastructure.repository import RepositoryBase


class NotificationService(RepositoryBase[Notification]):
    """Notification service (tenant + user scoped)"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Notification)

    async def get_notification_by_id(
        self,
        notification_id: int,
        *,
        tenant_id: int,
        user_id: int,
    ) -> Notification | None:
        """Get notification detail by ID (tenant + user scoped)."""
        return await self.get_one(
            where=[
                Notification.id == notification_id,
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
            ]
        )

    async def list_notifications(
        self,
        *,
        tenant_id: int,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        category: str | None = None,
        is_read: bool | None = None,
        priority: str | None = None,
        status: str | None = None,
        include_expired: bool = False,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[Notification], int]:
        """List notifications for current user with pagination."""
        where = [
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        ]

        if not include_expired:
            now = datetime.now(timezone.utc)
            where.append(or_(Notification.expire_at.is_(None), Notification.expire_at > now))

        filters: dict[str, Any] = {}
        if category:
            filters["category"] = category
        if is_read is not None:
            filters["is_read"] = is_read
        if priority:
            filters["priority"] = priority
        if status:
            filters["status"] = status

        # 排序处理
        allowed_sort_fields = {"id", "created_at", "priority"}
        order_field = sort_by if sort_by in allowed_sort_fields else "id"
        order_desc = sort_order and sort_order.lower() == "desc"

        notifications, total = await self.get_list(
            page=page,
            page_size=page_size,
            where=where,
            order_by=order_field,
            order_desc=order_desc,
            return_total=True,
            **filters,
        )
        return notifications, total

    async def get_unread_count(
        self,
        *,
        tenant_id: int,
        user_id: int,
        category: str | None = None,
        include_expired: bool = False,
    ) -> int:
        """Get unread notification count for current user."""
        where = [
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        ]

        if category:
            where.append(Notification.category == category)

        if not include_expired:
            now = datetime.now(timezone.utc)
            where.append(or_(Notification.expire_at.is_(None), Notification.expire_at > now))

        return await self.get_count(where=where)

    async def mark_as_read(self, notification: Notification) -> Notification:
        """Mark a single notification as read."""
        if notification.is_read:
            return notification

        now = datetime.now(timezone.utc)
        return await self.update(notification, {"is_read": True, "read_at": now})

    async def mark_all_as_read(
        self,
        *,
        tenant_id: int,
        user_id: int,
        category: str | None = None,
        include_expired: bool = False,
    ) -> int:
        """Mark all unread notifications as read (bulk)."""
        now = datetime.now(timezone.utc)

        conditions = [
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
            Notification.deleted_at.is_(None),
        ]
        if category:
            conditions.append(Notification.category == category)
        if not include_expired:
            conditions.append(or_(Notification.expire_at.is_(None), Notification.expire_at > now))

        stmt = (
            update(Notification)
            .where(and_(*conditions))
            .values(is_read=True, read_at=now)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def to_list_item(notification: Notification) -> dict[str, Any]:
        return NotificationListItem.model_validate(notification).model_dump(by_alias=True, exclude_none=False)

    @staticmethod
    def to_detail(notification: Notification) -> dict[str, Any]:
        return NotificationDetail.model_validate(notification).model_dump(by_alias=True, exclude_none=False)

