"""
AOJU Backend - Verification Models

Stores short-lived verification codes used for binding phone/email.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.infrastructure.database.types import PortableDateTime

from app.infrastructure.database.base import TenantBaseModel


class VerificationCode(TenantBaseModel):
    __tablename__ = "verification_codes"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID",
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Channel: sms/email",
    )
    purpose: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Purpose: bind_phone/bind_email",
    )
    target: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Target phone/email (normalized)",
    )
    code_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="HMAC-SHA256 hex digest",
    )
    salt: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Hash salt",
    )
    expires_at: Mapped[datetime] = mapped_column(
        PortableDateTime(),
        nullable=False,
        index=True,
        comment="Expiry timestamp",
    )
    used_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        index=True,
        comment="Used timestamp",
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Failed verification attempts",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VerificationCode(id={self.id}, channel={self.channel}, purpose={self.purpose})>"

