"""
AOJU Backend - Notifications Endpoints

System-level user notifications:
- notification: 系统公告、重要通知
- message: 个人消息、评论回复
- todo: 任务提醒、待处理事项
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.api.deps import CurrentSuperuser, CurrentTenantAdmin, CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.core.exceptions import BusinessError, NotFoundError
from app.core.logger import get_logger
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.notifications.schemas import (
    NotificationBroadcastRequest,
    NotificationBulkSendRequest,
    NotificationBulkSendResponse,
    NotificationDetail,
    NotificationListItem,
    NotificationReadAllResponse,
    NotificationSendRequest,
    NotificationUnreadCountResponse,
)
from app.domain.notifications.send import send_notification as send_notification_helper
from app.domain.notifications.service import NotificationService
from app.domain.teams.service import TeamService
from app.domain.users.service import UserService

logger = get_logger(__name__)

router = APIRouter()


class NotificationListQuery(BaseModel):
    """Notification list query parameters"""

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=200,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    category: str | None = None
    is_read: bool | None = Field(None, alias="isRead")
    priority: str | None = None
    status: str | None = None
    # 排序参数
    sort_by: str | None = Field(
        None,
        alias="sortBy",
        description="排序字段: id, created_at, priority",
    )
    sort_order: str | None = Field(
        None,
        alias="sortOrder",
        description="排序方向: asc, desc",
    )

    model_config = ConfigDict(populate_by_name=True)


class NotificationUnreadCountQuery(BaseModel):
    """Unread count query parameters"""

    category: str | None = None


@router.get("", response_model=ResponseBase[PageResponse[NotificationListItem]])
async def list_notifications(
    current_user: CurrentUser,
    db: DBSession,
    query: NotificationListQuery = Depends(),
) -> dict[str, Any]:
    """Get current user's notification list (paginated)."""
    service = NotificationService(db)
    notifications, total = await service.list_notifications(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        page=query.page,
        page_size=query.page_size,
        category=query.category,
        is_read=query.is_read,
        priority=query.priority,
        status=query.status,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    logger.info(
        "notifications_list_retrieved",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        count=len(notifications),
        total=total,
    )

    return SuccessResponse(
        data={
            "list": [service.to_list_item(item) for item in notifications],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/unread-count", response_model=ResponseBase[NotificationUnreadCountResponse])
async def get_unread_count(
    current_user: CurrentUser,
    db: DBSession,
    query: NotificationUnreadCountQuery = Depends(),
) -> dict[str, Any]:
    """Get current user's unread notification count."""
    service = NotificationService(db)
    count = await service.get_unread_count(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        category=query.category,
    )
    return SuccessResponse(data={"unreadCount": count})


@router.put("/read-all", response_model=ResponseBase[NotificationReadAllResponse])
async def mark_all_as_read(
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Mark all notifications as read for current user."""
    service = NotificationService(db)
    updated = await service.mark_all_as_read(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    logger.info(
        "notifications_mark_all_read",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        updated=updated,
    )
    return SuccessResponse(data={"updated": updated})


@router.get("/{notification_id}", response_model=ResponseBase[NotificationDetail])
async def get_notification_detail(
    notification_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Get notification detail by ID (current user only)."""
    service = NotificationService(db)
    notification = await service.get_notification_by_id(
        notification_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    if not notification:
        raise NotFoundError(message="Notification not found")
    return SuccessResponse(data=service.to_detail(notification))


@router.put("/{notification_id}/read", response_model=ResponseBase[NotificationDetail])
async def mark_as_read(
    notification_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Mark a notification as read (current user only)."""
    service = NotificationService(db)
    notification = await service.get_notification_by_id(
        notification_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    if not notification:
        raise NotFoundError(message="Notification not found")

    notification = await service.mark_as_read(notification)
    return SuccessResponse(data=service.to_detail(notification))


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Delete (soft delete) a notification (current user only)."""
    service = NotificationService(db)
    notification = await service.get_notification_by_id(
        notification_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    if not notification:
        raise NotFoundError(message="Notification not found")

    await service.delete(notification)
    logger.info(
        "notification_deleted",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        notification_id=notification_id,
    )
    return SuccessResponse(message="Deleted")


@router.post("", response_model=ResponseBase[NotificationDetail])
async def send_notification(
    data: NotificationSendRequest,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["notifications:send"])),
) -> dict[str, Any]:
    """Send a notification to a user (tenant admin / superuser)."""
    user_service = UserService(db)
    recipient = await user_service.get_user_by_id(data.user_id, tenant_ctx.tenant_id)
    if not recipient:
        raise NotFoundError(message="Recipient user not found")

    sender_id = data.sender_id if data.sender_id is not None else current_user.id
    sender_name = data.sender_name or current_user.nickname or current_user.username

    notification = await send_notification_helper(
        db,
        tenant_id=tenant_ctx.tenant_id,
        user_id=data.user_id,
        category=data.category,
        title=data.title,
        content=data.content,
        avatar=data.avatar,
        reference_type=data.reference_type,
        reference_id=data.reference_id,
        sender_id=sender_id,
        sender_name=sender_name,
        priority=data.priority,
        status=data.status,
        expire_at=data.expire_at,
        extra=data.extra,
    )

    logger.info(
        "notification_sent",
        tenant_id=tenant_ctx.tenant_id,
        sender_id=current_user.id,
        recipient_id=data.user_id,
        notification_id=notification.id,
        category=data.category,
    )
    return SuccessResponse(data=NotificationService.to_detail(notification))


@router.post("/bulk", response_model=ResponseBase[NotificationBulkSendResponse])
async def send_notification_bulk(
    data: NotificationBulkSendRequest,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["notifications:send"])),
) -> dict[str, Any]:
    """Send notifications to multiple users/teams (tenant-scoped)."""
    requested_user_ids: set[int] = {int(uid) for uid in (data.user_ids or [])}

    if data.team_ids:
        team_ids = [int(tid) for tid in data.team_ids]
        team_service = TeamService(db)
        existing_team_ids = await team_service.get_team_ids_by_tenant(tenant_ctx.tenant_id, team_ids)
        missing_team_ids = sorted(set(team_ids) - set(existing_team_ids))
        if missing_team_ids:
            raise NotFoundError(message=f"团队不存在: {missing_team_ids}")
        effective_team_ids: set[int] = set()
        for team_id in existing_team_ids:
            if data.include_children:
                child_ids = await team_service.get_children_ids(team_id, tenant_ctx.tenant_id, include_self=True)
                effective_team_ids.update(int(x) for x in child_ids)
            else:
                effective_team_ids.add(int(team_id))

        if effective_team_ids:
            user_service = UserService(db)
            users, _ = await user_service.list_users(
                tenant_id=tenant_ctx.tenant_id,
                page_size=0,
                team_ids=sorted(effective_team_ids),
            )
            requested_user_ids.update(int(u.id) for u in users)

    if not requested_user_ids:
        raise BusinessError(message="请选择目标用户或团队")

    user_service = UserService(db)
    existing_user_ids = await user_service.get_user_ids_by_tenant(tenant_ctx.tenant_id, sorted(requested_user_ids))
    missing_user_ids = sorted(requested_user_ids - set(existing_user_ids))
    if missing_user_ids:
        raise NotFoundError(message=f"用户不存在: {missing_user_ids}")

    sender_id = data.sender_id if data.sender_id is not None else current_user.id
    sender_name = data.sender_name or current_user.nickname or current_user.username

    service = NotificationService(db)
    data_list = [
        {
            "tenant_id": tenant_ctx.tenant_id,
            "user_id": user_id,
            "category": data.category,
            "title": data.title,
            "content": data.content,
            "avatar": data.avatar,
            "is_read": False,
            "read_at": None,
            "reference_type": data.reference_type,
            "reference_id": data.reference_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "priority": data.priority,
            "status": data.status,
            "expire_at": data.expire_at,
            "extra": data.extra or {},
        }
        for user_id in sorted(existing_user_ids)
    ]
    await service.create_batch(data_list)

    logger.info(
        "notifications_bulk_sent",
        tenant_id=tenant_ctx.tenant_id,
        sender_id=current_user.id,
        requested=len(requested_user_ids),
        sent=len(existing_user_ids),
    )
    return SuccessResponse(
        data={"requested": len(requested_user_ids), "sent": len(existing_user_ids)},
        message="批量发送成功",
    )


@router.post("/broadcast", response_model=ResponseBase[NotificationBulkSendResponse])
async def broadcast_notification(
    data: NotificationBroadcastRequest,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """Broadcast notification to all enabled users across all tenants (superuser only)."""
    sender_id = data.sender_id if data.sender_id is not None else current_user.id
    sender_name = data.sender_name or current_user.nickname or current_user.username

    service = NotificationService(db)
    user_service = UserService(db)
    batch_size = 1000
    rows = await user_service.get_all_enabled_users()
    sent = len(rows)

    for start in range(0, len(rows), batch_size):
        batch_rows = rows[start : start + batch_size]
        data_list = [
            {
                "tenant_id": int(tenant_id),
                "user_id": int(user_id),
                "category": data.category,
                "title": data.title,
                "content": data.content,
                "avatar": data.avatar,
                "is_read": False,
                "read_at": None,
                "reference_type": data.reference_type,
                "reference_id": data.reference_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "priority": data.priority,
                "status": data.status,
                "expire_at": data.expire_at,
                "extra": data.extra or {},
            }
            for user_id, tenant_id in batch_rows
        ]
        await service.create_batch(data_list)

    logger.info(
        "notifications_broadcast_sent",
        sender_id=current_user.id,
        sent=sent,
    )
    return SuccessResponse(
        data={"requested": sent, "sent": sent},
        message="全站发送成功" if sent else "暂无可发送用户",
    )
