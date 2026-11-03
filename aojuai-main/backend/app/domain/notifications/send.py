"""
AOJU Backend - Notification Helper

Provides a convenience function to send/persist user notifications.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.logger import get_logger
from app.domain.notifications.message_channels import deliver_notification_to_user_channels
from app.domain.notifications.models import Notification
from app.domain.notifications.service import NotificationService

logger = get_logger(__name__)


_ALLOWED_CATEGORIES = {"notification", "message", "todo"}
_ALLOWED_PRIORITIES = {"low", "normal", "high", "urgent"}


def _validate_choice(value: str, *, field: str, allowed: set[str]) -> None:
    if value not in allowed:
        allowed_sorted = ", ".join(sorted(allowed))
        raise ValidationError(message=f"Invalid {field}: {value}. Allowed: {allowed_sorted}")


async def send_notification(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    category: str,
    title: str,
    content: str | None = None,
    avatar: str | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    sender_id: int | None = None,
    sender_name: str | None = None,
    priority: str = "normal",
    status: str | None = None,
    expire_at: datetime | None = None,
    extra: dict[str, Any] | None = None,
    deliver_to_channels: bool = True,
) -> Notification:
    """发送通知给指定用户

    `deliver_to_channels=False` 只落站内通知，不投递到用户的外部消息通道。
    调用方自己负责外部投递（例如 dispatcher 要先做跨作用域去重）时用它，
    避免同一条消息被送两次。
    """
    _validate_choice(category, field="category", allowed=_ALLOWED_CATEGORIES)
    _validate_choice(priority, field="priority", allowed=_ALLOWED_PRIORITIES)

    data: dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "category": category,
        "title": title,
        "content": content,
        "avatar": avatar,
        "is_read": False,
        "read_at": None,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "priority": priority,
        "status": status,
        "expire_at": expire_at,
        "extra": extra or {},
    }

    service = NotificationService(db)
    notification = await service.create(data)

    if not deliver_to_channels:
        return notification

    try:
        await deliver_notification_to_user_channels(
            db,
            user_id=user_id,
            title=title,
            content=content,
            extra={
                "notificationId": notification.id,
                "category": category,
                "priority": priority,
                "referenceType": reference_type,
                "referenceId": reference_id,
                **(extra or {}),
            },
        )
    except Exception as exc:  # noqa: BLE001 - external channel failure must not block site notification
        logger.warning(
            "message_channel_fanout_failed",
            tenant_id=tenant_id,
            user_id=user_id,
            notification_id=notification.id,
            error=str(exc),
        )

    return notification
