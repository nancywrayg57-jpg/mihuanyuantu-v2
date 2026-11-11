"""Upstream provider usage ledger (architecture name: rp_provider_usage).

Physical table follows the repo convention ``cap_realphotos_*``.
Never store upstream API keys or full signed URLs here.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel


class RealphotosProviderUsage(TenantBaseModel):
    """One row per auditable upstream call (success or failed transport)."""

    __tablename__ = "cap_realphotos_provider_usage"
    __table_args__ = (
        Index("ix_cap_realphotos_provider_usage_duty_created", "duty", "created_at"),
        {"comment": "realphotos upstream usage/cost ledger (maps to architecture rp_provider_usage)"},
    )

    duty: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    config_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    units: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("1"))
    unit_name: Mapped[str] = mapped_column(String(32), nullable=False, default="call")
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    # known | unknown | unavailable
    cost_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unavailable")
    task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attempt_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
