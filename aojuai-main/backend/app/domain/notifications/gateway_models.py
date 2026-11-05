"""System message gateway account models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import BaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON


class MessageGatewayAccount(BaseModel):
    """System-level gateway/bot account used by personal message channels."""

    __tablename__ = "message_gateway_accounts"
    __table_args__ = {"comment": "系统消息 Channel 网关账号表"}

    channel_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True, comment='"wechat" | "feishu" | "wecom"')
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Gateway account display name")
    account_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True, comment="Bot/account ID")
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Provider API base URL")
    token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Encrypted provider token")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="disabled", index=True, comment='"active" | "disabled" | "expired"')
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True, comment="Default account for this channel type")
    get_updates_buf: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Long-poll cursor")
    last_poll_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True, comment="Last poll timestamp")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Last gateway error")
    extra: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False, default=dict, server_default="{}", comment="Extra gateway state")


class MessageGatewayInboundNonce(BaseModel):
    """A short-lived, database-wide replay guard for signed gateway requests."""

    __tablename__ = "message_gateway_inbound_nonces"
    __table_args__ = (
        Index(
            "uq_message_gateway_inbound_nonces_account_digest",
            "gateway_account_id",
            "nonce_digest",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_message_gateway_inbound_nonces_expires_at", "expires_at"),
        {"comment": "消息网关入站签名 nonce 防重放表"},
    )

    gateway_account_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Gateway account ID",
    )
    nonce_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 digest of the request nonce",
    )
    expires_at: Mapped[datetime] = mapped_column(
        PortableDateTime(),
        nullable=False,
        comment="Replay guard expiration",
    )


class MessageChannelBindGuard(BaseModel):
    """Failed binding attempts aggregated by hashed sender/source identity."""

    __tablename__ = "message_channel_bind_guards"
    __table_args__ = (
        Index(
            "uq_message_channel_bind_guards_key",
            "guard_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_message_channel_bind_guards_expires_at", "expires_at"),
        {"comment": "消息 Channel 关联码失败计数与限流表"},
    )

    guard_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 digest of the rate-limit subject",
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Failed attempts in the active window",
    )
    blocked_until: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Reject binding attempts until this time",
    )
    expires_at: Mapped[datetime] = mapped_column(
        PortableDateTime(),
        nullable=False,
        comment="Guard record expiration",
    )
