"""Auth challenge + per-account login guard (S0)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import BaseModel
from app.infrastructure.database.types import PortableDateTime


class RealphotosAuthChallenge(BaseModel):
    """一次性验证码挑战（全局表，不按租户切分；消费后不可复用）。"""

    __tablename__ = "cap_realphotos_auth_challenges"
    __table_args__ = (
        Index(
            "ix_cap_realphotos_auth_challenges_challenge_public_id",
            "challenge_public_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_cap_realphotos_auth_challenges_expires_at", "expires_at"),
        {"comment": "realphotos login captcha challenges"},
    )

    challenge_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    client_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(PortableDateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)


class RealphotosAuthGuard(BaseModel):
    """按用户名的登录失败计数与锁定（与预审冻结分离）。"""

    __tablename__ = "cap_realphotos_auth_guards"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_auth_guards_username",
            "username_normalized",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos login failure guards"},
    )

    username_normalized: Mapped[str] = mapped_column(String(64), nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
