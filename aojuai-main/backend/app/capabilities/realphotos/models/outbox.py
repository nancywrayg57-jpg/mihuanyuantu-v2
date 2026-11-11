"""Outbox row for durable inbox delivery (FR-023 / AD-001 minimal)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON


class RealphotosOutbox(TenantBaseModel):
    """业务事件 outbox：业务路径只写本表；独立 notify worker 投递 inbox。"""

    __tablename__ = "cap_realphotos_outbox"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_outbox_tenant_event",
            "tenant_id",
            "event_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_cap_realphotos_outbox_claim",
            "status",
            "next_attempt_at",
            "created_at",
        ),
        {"comment": "realphotos outbox events"},
    )

    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    recipient_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
