"""Minimal outbox row for S0 (business events)."""

from __future__ import annotations

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON


class RealphotosOutbox(TenantBaseModel):
    """业务事件 outbox（S0 最小：可写入、可按 event_key 幂等）。"""

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
