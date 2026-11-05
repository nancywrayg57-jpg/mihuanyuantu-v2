"""Tenant-safe support workflow.

继承 `RepositoryBase` 是基座的既定约定（软删除过滤、分页与计数、更新/软删除都在基类里）。
租户过滤**不**交给基类：基类不知道"当前租户是谁"，每个查询自己把 `tenant_id` 带上，
不让越权变成隐式行为。

这个模块只认识工单本身。`related_type` / `related_id` 是**不透明**的泛化关联，
取值与生命周期都归调用方；本模块不 import 任何业务域，也不 import CMS——
依赖方向由 `tests/capabilities/support/test_support_module_boundaries.py` 钉住。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.core.logger import get_logger
from app.domain.menus.models import Menu
from app.domain.notifications.send import send_notification
from app.domain.roles.models import Role, RoleMenu
from app.domain.users.models import User, UserRole, UserStatus
from app.infrastructure.repository import RepositoryBase

from .constants import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_PRIORITY,
    DEFAULT_SLA_HOURS,
    PRIORITIES,
    STATUSES,
    TERMINAL_STATUSES,
)
from .models import ANONYMOUS_REQUESTER_ID, SupportTicket, SupportTicketMessage
from .permissions import MANAGE
from .schemas import (
    TicketCreate,
    TicketDetail,
    TicketListItem,
    TicketMessageItem,
    TicketUpdate,
)

logger = get_logger(__name__)


class SupportService(RepositoryBase[SupportTicket]):
    """Every read and write is scoped by ``tenant_id``."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, SupportTicket)

    # ------------------------------------------------------------------ reads

    @staticmethod
    def options() -> dict[str, list[str]]:
        return {
            "categories": list(CATEGORIES),
            "statuses": list(STATUSES),
            "priorities": list(PRIORITIES),
        }

    async def list_tickets(
        self,
        *,
        tenant_id: int,
        page: int,
        page_size: int,
        owner_user_id: int | None = None,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        keyword: str | None = None,
        requester_user_id: int | None = None,
        assignee_user_id: int | None = None,
        unassigned: bool | None = None,
        related_type: str | None = None,
        exclude_related_type: str | None = None,
    ) -> tuple[list[SupportTicket], int]:
        where = [SupportTicket.tenant_id == tenant_id]
        if owner_user_id is not None:
            where.append(SupportTicket.requester_user_id == owner_user_id)
        if requester_user_id is not None:
            where.append(SupportTicket.requester_user_id == requester_user_id)
        if assignee_user_id is not None:
            where.append(SupportTicket.assignee_user_id == assignee_user_id)
        if unassigned is True:
            where.append(SupportTicket.assignee_user_id.is_(None))
        if status:
            where.append(SupportTicket.status == status)
        if category:
            where.append(SupportTicket.category == category)
        if priority:
            where.append(SupportTicket.priority == priority)
        if related_type:
            where.append(SupportTicket.related_type == related_type)
        if exclude_related_type:
            where.append(
                or_(
                    SupportTicket.related_type.is_(None),
                    SupportTicket.related_type != exclude_related_type,
                )
            )
        if keyword and keyword.strip():
            like = f"%{keyword.strip()}%"
            where.append(
                or_(
                    SupportTicket.ticket_no.ilike(like),
                    SupportTicket.subject.ilike(like),
                    SupportTicket.description.ilike(like),
                    SupportTicket.related_id.ilike(like),
                )
            )

        rows, total = await self.get_list(
            page=page,
            page_size=page_size,
            where=where,
            order_by="last_message_at",
            order_desc=True,
            return_total=True,
        )
        return list(rows), int(total or 0)

    async def get_ticket(
        self,
        *,
        tenant_id: int,
        ticket_id: int,
        owner_user_id: int | None = None,
    ) -> SupportTicket:
        where = [
            SupportTicket.tenant_id == tenant_id,
            SupportTicket.id == ticket_id,
            SupportTicket.deleted_at.is_(None),
        ]
        if owner_user_id is not None:
            where.append(SupportTicket.requester_user_id == owner_user_id)
        stmt = select(SupportTicket).options(selectinload(SupportTicket.messages)).where(*where)
        ticket = (await self.db.execute(stmt)).scalar_one_or_none()
        if ticket is None:
            # 同租户他人的工单与跨租户工单一律 404：403 会泄漏"这里有一条工单"。
            raise NotFoundError(message="工单不存在")
        return ticket

    async def summary(self, *, tenant_id: int) -> dict[str, int]:
        stmt = (
            select(SupportTicket.status, func.count())
            .where(SupportTicket.tenant_id == tenant_id, SupportTicket.deleted_at.is_(None))
            .group_by(SupportTicket.status)
        )
        counts = {str(status): int(count) for status, count in (await self.db.execute(stmt)).all()}
        return {
            "total": sum(counts.values()),
            **{status: counts.get(status, 0) for status in STATUSES},
        }

    # ----------------------------------------------------------------- writes

    async def create_ticket(
        self,
        *,
        tenant_id: int,
        user_id: int,
        data: TicketCreate,
    ) -> SupportTicket:
        ticket = await self._insert_ticket(
            tenant_id=tenant_id,
            requester_user_id=user_id,
            author_user_id=user_id,
            author_role="user",
            category=data.category,
            priority=data.priority,
            subject=data.subject,
            description=data.description,
            related_type=data.related_type,
            related_id=data.related_id,
            attachments=data.attachments,
            extra=data.extra,
            actor_user_id=user_id,
        )
        await self._notify_managers(
            tenant_id=tenant_id,
            ticket=ticket,
            sender_id=user_id,
            title=f"new ticket {ticket.ticket_no}",
            content=ticket.subject,
        )
        await self._refresh_for_response(ticket)
        return ticket

    async def create_anonymous_ticket(
        self,
        *,
        tenant_id: int,
        subject: str,
        description: str,
        category: str = DEFAULT_CATEGORY,
        priority: str = DEFAULT_PRIORITY,
        related_type: str | None = None,
        related_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> SupportTicket:
        """Create a ticket for a visitor who has no account.

        调用方负责匿名入口的防护（蜜罐 + 限流 + 租户解析），本方法只保证：
        分类/优先级取值被收敛到白名单，requester 用哨兵而不是伪造某个真实用户。
        """
        ticket = await self._insert_ticket(
            tenant_id=tenant_id,
            requester_user_id=ANONYMOUS_REQUESTER_ID,
            author_user_id=None,
            author_role="visitor",
            category=category if category in CATEGORIES else DEFAULT_CATEGORY,
            priority=priority if priority in PRIORITIES else DEFAULT_PRIORITY,
            subject=subject,
            description=description,
            related_type=related_type,
            related_id=related_id,
            attachments=[],
            extra=extra,
            actor_user_id=None,
        )
        await self._notify_managers(
            tenant_id=tenant_id,
            ticket=ticket,
            sender_id=None,
            title=f"new ticket {ticket.ticket_no}",
            content=ticket.subject,
        )
        await self._refresh_for_response(ticket)
        return ticket

    async def add_user_message(
        self,
        *,
        tenant_id: int,
        ticket_id: int,
        user_id: int,
        body: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> SupportTicket:
        ticket = await self.get_ticket(
            tenant_id=tenant_id, ticket_id=ticket_id, owner_user_id=user_id
        )
        if ticket.status == "closed":
            raise BusinessError(message="已关闭的工单不可继续回复")
        now = datetime.now(UTC)
        ticket.status = "open"
        ticket.last_message_at = now
        ticket.updated_by = user_id
        self.db.add(
            SupportTicketMessage(
                tenant_id=tenant_id,
                ticket_id=ticket.id,
                author_user_id=user_id,
                author_role="user",
                message_type="reply",
                body=body.strip(),
                is_internal=False,
                attachments=attachments or [],
                extra={},
            )
        )
        await self.db.flush()
        recipients = (
            [int(ticket.assignee_user_id)]
            if ticket.assignee_user_id and ticket.assignee_user_id != user_id
            else await self._manager_user_ids(tenant_id=tenant_id)
        )
        await self._notify_users(
            tenant_id=tenant_id,
            user_ids=recipients,
            ticket=ticket,
            sender_id=user_id,
            title=f"ticket reply {ticket.ticket_no}",
            content=body.strip(),
        )
        await self._refresh_for_response(ticket)
        return ticket

    async def add_admin_message(
        self,
        *,
        tenant_id: int,
        ticket_id: int,
        user_id: int,
        body: str,
        is_internal: bool = False,
        status: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> SupportTicket:
        ticket = await self.get_ticket(tenant_id=tenant_id, ticket_id=ticket_id)
        if ticket.status == "closed" and not status:
            raise BusinessError(message="已关闭的工单需要先重新打开后再回复")
        now = datetime.now(UTC)
        if status:
            self._apply_status(ticket, status, now=now)
        elif not is_internal and ticket.status not in TERMINAL_STATUSES:
            ticket.status = "pending"
        if not is_internal:
            ticket.last_replied_at = now
            ticket.last_message_at = now
        ticket.updated_by = user_id
        self.db.add(
            SupportTicketMessage(
                tenant_id=tenant_id,
                ticket_id=ticket.id,
                author_user_id=user_id,
                author_role="agent",
                message_type="internal_note" if is_internal else "reply",
                body=body.strip(),
                is_internal=is_internal,
                attachments=attachments or [],
                extra={},
            )
        )
        await self.db.flush()
        if (
            not is_internal
            and ticket.requester_user_id > ANONYMOUS_REQUESTER_ID
            and ticket.requester_user_id != user_id
        ):
            await self._notify_users(
                tenant_id=tenant_id,
                user_ids=[int(ticket.requester_user_id)],
                ticket=ticket,
                sender_id=user_id,
                title=f"ticket reply {ticket.ticket_no}",
                content=body.strip(),
            )
        await self._refresh_for_response(ticket)
        return ticket

    async def update_ticket(
        self,
        *,
        tenant_id: int,
        ticket_id: int,
        user_id: int,
        data: TicketUpdate,
    ) -> SupportTicket:
        ticket = await self.get_ticket(tenant_id=tenant_id, ticket_id=ticket_id)
        now = datetime.now(UTC)
        previous_status = ticket.status
        previous_assignee = ticket.assignee_user_id
        changes: list[str] = []

        if data.category is not None and data.category != ticket.category:
            changes.append(f"category {ticket.category} -> {data.category}")
            ticket.category = data.category
        if data.priority is not None and data.priority != ticket.priority:
            changes.append(f"priority {ticket.priority} -> {data.priority}")
            ticket.priority = data.priority
        if data.status is not None and data.status != ticket.status:
            changes.append(f"status {ticket.status} -> {data.status}")
            self._apply_status(ticket, data.status, now=now)
        if data.clear_assignee:
            if ticket.assignee_user_id is not None:
                changes.append("assignee cleared")
            ticket.assignee_user_id = None
        elif data.assignee_user_id is not None and data.assignee_user_id != ticket.assignee_user_id:
            changes.append(f"assignee -> {data.assignee_user_id}")
            ticket.assignee_user_id = data.assignee_user_id
        if data.subject is not None and data.subject.strip() != ticket.subject:
            changes.append("subject updated")
            ticket.subject = data.subject.strip()
        if data.related_type is not None:
            ticket.related_type = data.related_type.strip() or None
        if data.related_id is not None:
            ticket.related_id = data.related_id.strip() or None
        ticket.updated_by = user_id

        if data.internal_note:
            self.db.add(
                SupportTicketMessage(
                    tenant_id=tenant_id,
                    ticket_id=ticket.id,
                    author_user_id=user_id,
                    author_role="agent",
                    message_type="internal_note",
                    body=data.internal_note.strip(),
                    is_internal=True,
                    attachments=[],
                    extra={},
                )
            )
        elif changes:
            self.db.add(
                SupportTicketMessage(
                    tenant_id=tenant_id,
                    ticket_id=ticket.id,
                    author_user_id=user_id,
                    author_role="system",
                    message_type="status_change",
                    body="; ".join(changes),
                    is_internal=True,
                    attachments=[],
                    extra={"changes": changes},
                )
            )
        await self.db.flush()

        if (
            ticket.status != previous_status
            and ticket.requester_user_id > ANONYMOUS_REQUESTER_ID
            and ticket.requester_user_id != user_id
        ):
            await self._notify_users(
                tenant_id=tenant_id,
                user_ids=[int(ticket.requester_user_id)],
                ticket=ticket,
                sender_id=user_id,
                title=f"ticket status {ticket.ticket_no}",
                content=ticket.status,
            )
        if (
            ticket.assignee_user_id
            and ticket.assignee_user_id != previous_assignee
            and ticket.assignee_user_id != user_id
        ):
            await self._notify_users(
                tenant_id=tenant_id,
                user_ids=[int(ticket.assignee_user_id)],
                ticket=ticket,
                sender_id=user_id,
                title=f"ticket assigned {ticket.ticket_no}",
                content=ticket.subject,
            )
        await self._refresh_for_response(ticket)
        return ticket

    # -------------------------------------------------------------- internals

    async def _insert_ticket(
        self,
        *,
        tenant_id: int,
        requester_user_id: int,
        author_user_id: int | None,
        author_role: str,
        category: str,
        priority: str,
        subject: str,
        description: str,
        related_type: str | None,
        related_id: str | None,
        attachments: list[dict[str, Any]] | None,
        extra: dict[str, Any] | None,
        actor_user_id: int | None,
    ) -> SupportTicket:
        now = datetime.now(UTC)
        body = description.strip()
        ticket = SupportTicket(
            tenant_id=tenant_id,
            requester_user_id=requester_user_id,
            category=category,
            status="open",
            priority=priority,
            subject=subject.strip()[:200],
            description=body,
            related_type=(related_type or "").strip() or None,
            related_id=(related_id or "").strip() or None,
            last_message_at=now,
            created_by=actor_user_id,
            updated_by=actor_user_id,
            extra=extra or {},
        )
        self.db.add(ticket)
        await self.db.flush()
        ticket.ticket_no = f"SUP-{tenant_id}-{ticket.id:06d}"
        self.db.add(
            SupportTicketMessage(
                tenant_id=tenant_id,
                ticket_id=ticket.id,
                author_user_id=author_user_id,
                author_role=author_role,
                message_type="initial",
                body=body,
                is_internal=False,
                attachments=attachments or [],
                extra={},
            )
        )
        await self.db.flush()
        return ticket

    async def _refresh_for_response(self, ticket: SupportTicket) -> None:
        """Reload server-managed scalars before serializing the response."""
        await self.db.refresh(ticket)
        await self.db.refresh(ticket, attribute_names=["messages"])

    @staticmethod
    def _apply_status(ticket: SupportTicket, status: str, *, now: datetime) -> None:
        ticket.status = status
        if status == "resolved":
            ticket.resolved_at = now
            ticket.closed_at = None
        elif status == "closed":
            ticket.closed_at = now
        else:
            ticket.resolved_at = None
            ticket.closed_at = None

    async def _manager_user_ids(self, *, tenant_id: int) -> list[int]:
        """Tenant members whose role grants the ``support:manage`` button."""
        stmt = (
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .join(RoleMenu, RoleMenu.role_id == Role.id)
            .join(Menu, Menu.id == RoleMenu.menu_id)
            .where(
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
                # A disabled account cannot sign in to read the ticket, and a
                # deactivated role no longer grants the button this query is
                # asking about — notifying either is noise the recipient can
                # never act on. Matches how the kernel resolves a user's roles.
                User.status == UserStatus.ENABLED,
                UserRole.tenant_id == tenant_id,
                Role.tenant_id == tenant_id,
                Role.deleted_at.is_(None),
                Role.is_active.is_(True),
                RoleMenu.tenant_id == tenant_id,
                Menu.tenant_id == tenant_id,
                Menu.perms == MANAGE,
                Menu.deleted_at.is_(None),
            )
            .distinct()
        )
        return [int(value) for value in (await self.db.execute(stmt)).scalars().all()]

    async def _notify_managers(
        self,
        *,
        tenant_id: int,
        ticket: SupportTicket,
        sender_id: int | None,
        title: str,
        content: str,
    ) -> None:
        await self._notify_users(
            tenant_id=tenant_id,
            user_ids=await self._manager_user_ids(tenant_id=tenant_id),
            ticket=ticket,
            sender_id=sender_id,
            title=title,
            content=content,
        )

    async def _notify_users(
        self,
        *,
        tenant_id: int,
        user_ids: list[int],
        ticket: SupportTicket,
        sender_id: int | None,
        title: str,
        content: str,
    ) -> None:
        """站内通知是**尽力而为**的副作用：投递失败不能把工单写入一起拖挂。"""
        if not user_ids:
            return
        for user_id in dict.fromkeys(user_ids):
            try:
                await send_notification(
                    self.db,
                    tenant_id=tenant_id,
                    user_id=int(user_id),
                    category="notification",
                    title=title,
                    content=content[:2000],
                    reference_type="support_ticket",
                    reference_id=int(ticket.id),
                    sender_id=sender_id,
                    priority=ticket.priority if ticket.priority in PRIORITIES else "normal",
                    extra={
                        "ticketNo": ticket.ticket_no,
                        "ticketStatus": ticket.status,
                        "path": "/support/tickets",
                    },
                )
            except Exception:  # noqa: BLE001 - 通知失败不改变工单结果
                logger.warning(
                    "support_notification_failed",
                    tenant_id=tenant_id,
                    ticket_id=int(ticket.id),
                    exc_info=True,
                )

    # ------------------------------------------------------------ serializing

    async def user_briefs(self, tickets: list[SupportTicket]) -> dict[int, dict[str, Any]]:
        user_ids = {
            int(value)
            for ticket in tickets
            for value in (ticket.requester_user_id, ticket.assignee_user_id)
            if value
        }
        for ticket in tickets:
            for message in getattr(ticket, "messages", None) or []:
                if message.author_user_id:
                    user_ids.add(int(message.author_user_id))
        if not user_ids:
            return {}
        stmt = select(User).where(User.id.in_(user_ids), User.deleted_at.is_(None))
        return {
            int(user.id): {
                "id": int(user.id),
                "username": user.username,
                "nickname": user.nickname,
                "email": user.email,
            }
            for user in (await self.db.execute(stmt)).scalars().all()
        }

    @staticmethod
    def sla_fields(ticket: SupportTicket, *, now: datetime | None = None) -> dict[str, Any]:
        """First-response SLA measured from the newest conversation activity.

        `pending`（球在用户那边）与终态工单**不**标超时：那不是客服欠的响应。
        """
        sla_hours = max(0, int(DEFAULT_SLA_HOURS))
        anchors = [
            value if value.tzinfo else value.replace(tzinfo=UTC)
            for value in (ticket.created_at, ticket.last_message_at, ticket.last_replied_at)
            if value is not None
        ]
        anchor = max(anchors) if anchors else None
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        due_at = anchor + timedelta(hours=sla_hours) if anchor and sla_hours else None
        return {
            "slaHours": sla_hours,
            "slaDueAt": due_at,
            "slaOverdue": bool(due_at and ticket.status == "open" and current > due_at),
            "waitingHours": (
                round(max(0.0, (current - anchor).total_seconds() / 3600), 1) if anchor else None
            ),
        }

    @staticmethod
    def ticket_payload(
        ticket: SupportTicket,
        *,
        user_briefs: dict[int, dict[str, Any]] | None = None,
        include_messages: bool = False,
        include_internal: bool = False,
    ) -> dict[str, Any]:
        users = user_briefs or {}
        payload = TicketListItem(
            id=int(ticket.id),
            ticketNo=ticket.ticket_no,
            requesterUserId=int(ticket.requester_user_id),
            requester=users.get(int(ticket.requester_user_id)),
            assigneeUserId=int(ticket.assignee_user_id) if ticket.assignee_user_id else None,
            assignee=users.get(int(ticket.assignee_user_id)) if ticket.assignee_user_id else None,
            category=ticket.category,
            status=ticket.status,
            priority=ticket.priority,
            subject=ticket.subject,
            relatedType=ticket.related_type,
            relatedId=ticket.related_id,
            lastMessageAt=ticket.last_message_at,
            lastRepliedAt=ticket.last_replied_at,
            **SupportService.sla_fields(ticket),
            resolvedAt=ticket.resolved_at,
            closedAt=ticket.closed_at,
            createdAt=ticket.created_at,
            updatedAt=ticket.updated_at,
            extra=ticket.extra or {},
        ).model_dump(by_alias=True)
        if not include_messages:
            return payload
        messages = [
            TicketMessageItem(
                id=int(message.id),
                ticketId=int(message.ticket_id),
                authorUserId=int(message.author_user_id) if message.author_user_id else None,
                author=users.get(int(message.author_user_id)) if message.author_user_id else None,
                authorRole=message.author_role,
                messageType=message.message_type,
                body=message.body,
                isInternal=bool(message.is_internal),
                attachments=message.attachments or [],
                createdAt=message.created_at,
            )
            for message in ticket.messages
            if include_internal or not message.is_internal
        ]
        return TicketDetail(
            **payload,
            description=ticket.description,
            messages=messages,
        ).model_dump(by_alias=True)


__all__ = ["SupportService"]
