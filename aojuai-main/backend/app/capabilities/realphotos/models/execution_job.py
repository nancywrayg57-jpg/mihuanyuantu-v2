"""Durable execution job queue row (S0 skeleton)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON


class RealphotosExecutionJob(TenantBaseModel):
    """PG 持久队列骨架：可被同机 worker 认领至终态。"""

    __tablename__ = "cap_realphotos_execution_jobs"
    __table_args__ = (
        Index(
            "ix_cap_realphotos_execution_jobs_claim",
            "status",
            "available_at",
            "created_at",
        ),
        Index("ix_cap_realphotos_execution_jobs_tenant_status", "tenant_id", "status"),
        {"comment": "realphotos durable execution jobs"},
    )

    job_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", server_default="queued", index=True
    )
    # task_queue.claim_one 约定字段名
    claimed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    available_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lease_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    dispatch_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    owner_account_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    result: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
