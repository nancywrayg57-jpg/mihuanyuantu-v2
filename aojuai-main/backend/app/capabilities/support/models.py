"""Tenant-scoped persistence for the support capability.

两张表都用 `cap_` 前缀：那是能力包表的基座约定（`module_manifest.CAPABILITY_TABLE_PREFIX`），
核心链的 autogenerate 靠它把包自管的表挡在外面——换个前缀，核心链第一次
autogenerate 就会生成 DROP TABLE。

列类型一律走 `PortableJSON` / `PortableDateTime`：基座有 SQLite 轻量档，
直接写 PostgreSQL 专有的 JSONB 或带时区的 DateTime 会被
`tests/test_sqlite_app_portability.py` 判红。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON

#: 匿名访客提交的工单没有账号。用哨兵 0 而不是把列改成 nullable：
#: 后者要动索引、动全部查询，收益却只是省下一个常量。
ANONYMOUS_REQUESTER_ID = 0


class SupportTicket(TenantBaseModel):
    """One help-desk ticket owned by a tenant."""

    __tablename__ = "cap_support_tickets"
    __table_args__ = (
        Index("ix_cap_support_tickets_tenant_status", "tenant_id", "status"),
        Index("ix_cap_support_tickets_tenant_requester", "tenant_id", "requester_user_id"),
        Index(
            "ix_cap_support_tickets_tenant_assignee",
            "tenant_id",
            "assignee_user_id",
            "status",
        ),
        Index(
            "uq_cap_support_tickets_tenant_ticket_no",
            "tenant_id",
            "ticket_no",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND ticket_no IS NOT NULL"),
            sqlite_where=text("deleted_at IS NULL AND ticket_no IS NOT NULL"),
        ),
        {"comment": "Support capability tickets"},
    )

    ticket_no: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    requester_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    assignee_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="other", server_default="other", index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", server_default="open", index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal", server_default="normal", index=True
    )

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # 泛化关联对本模块**故意不透明**：related_type 的取值由调用方定义，
    # support 不认识任何具体业务实体，也不管它的生命周期。
    related_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    related_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    last_message_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(), nullable=True, index=True
    )
    last_replied_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)

    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )

    messages: Mapped[list["SupportTicketMessage"]] = relationship(
        "SupportTicketMessage",
        back_populates="ticket",
        lazy="selectin",
        order_by="SupportTicketMessage.id.asc()",
    )


class SupportTicketMessage(TenantBaseModel):
    """A public reply, an internal note, or a status event on one ticket."""

    __tablename__ = "cap_support_ticket_messages"
    __table_args__ = (
        Index("ix_cap_support_messages_tenant_ticket", "tenant_id", "ticket_id"),
        Index("ix_cap_support_messages_tenant_author", "tenant_id", "author_user_id"),
        {"comment": "Support capability ticket messages"},
    )

    ticket_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cap_support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    author_role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default="user"
    )
    message_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="reply", server_default="reply"
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default="[]"
    )
    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )

    ticket: Mapped[SupportTicket] = relationship(
        "SupportTicket", back_populates="messages", lazy="joined"
    )


__all__ = ["ANONYMOUS_REQUESTER_ID", "SupportTicket", "SupportTicketMessage"]
