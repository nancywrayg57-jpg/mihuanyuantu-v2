"""Integer tenant credit account + append-only ledger (S0)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON


class RealphotosCreditAccount(TenantBaseModel):
    """租户唯一整数积分户：available + reserved；CAS 用 version。"""

    __tablename__ = "cap_realphotos_credit_accounts"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_credit_accounts_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos integer credit accounts"},
    )

    available_integer: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    reserved_integer: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class RealphotosCreditLedgerEntry(TenantBaseModel):
    """追加不可改流水；tenant + event_key 永久唯一。"""

    __tablename__ = "cap_realphotos_credit_ledger_entries"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_credit_ledger_tenant_event",
            "tenant_id",
            "event_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_cap_realphotos_credit_ledger_tenant_created",
            "tenant_id",
            "created_at",
        ),
        {"comment": "realphotos integer credit ledger"},
    )

    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    delta_available: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    delta_reserved: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    before_available: Mapped[int] = mapped_column(BigInteger, nullable=False)
    after_available: Mapped[int] = mapped_column(BigInteger, nullable=False)
    before_reserved: Mapped[int] = mapped_column(BigInteger, nullable=False)
    after_reserved: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    target_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
