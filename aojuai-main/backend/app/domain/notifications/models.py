"""
AOJU Backend - Notification Models

System-level user notifications:
- notification: 系统公告、重要通知
- message: 个人消息、评论回复
- todo: 任务提醒、待处理事项
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import BaseModel, TenantBaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON


class NotificationCategory(StrEnum):
    """Notification category"""

    NOTIFICATION = "notification"
    MESSAGE = "message"
    TODO = "todo"


class NotificationPriority(StrEnum):
    """Notification priority"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageChannelType(StrEnum):
    """User message channel type."""

    WECHAT = "wechat"
    FEISHU = "feishu"
    WECOM = "wecom"
    WEBHOOK = "webhook"


class MessageChannelStatus(StrEnum):
    """User message channel status."""

    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class Notification(TenantBaseModel):
    """
    Notification Model - 消息通知

    Multi-tenant isolated user notifications.
    """

    __tablename__ = "notifications"
    __table_args__ = {"comment": "用户消息通知表"}

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="Recipient user ID",
    )

    # Content
    category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment='Category: "notification" | "message" | "todo"',
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Title",
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Content",
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Avatar URL",
    )

    # State
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Is read",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Read timestamp",
    )

    # References / Sender
    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Business reference type",
    )
    reference_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Business reference ID",
    )
    sender_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Sender user ID",
    )
    sender_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Sender display name",
    )

    # Priority / Status
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=NotificationPriority.NORMAL.value,
        index=True,
        comment='Priority: "low" | "normal" | "high" | "urgent"',
    )
    status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment='Custom status, e.g. "pending", "processing", "done"',
    )

    # Expiration
    expire_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        index=True,
        comment="Expire timestamp",
    )

    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra attributes (JSONB)",
    )


class UserMessageChannel(BaseModel):
    """
    User message channel binding.

    Stores per-user message channel bindings. This is system-level personal
    data, not tenant-admin-managed configuration.
    """

    __tablename__ = "user_message_channels"
    __table_args__ = (
        Index(
            "uq_user_message_channels_bind_token",
            "bind_token",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND bind_token IS NOT NULL"),
            sqlite_where=text("deleted_at IS NULL AND bind_token IS NOT NULL"),
        ),
        {"comment": "用户个人消息 Channel 绑定表"},
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    bind_token: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        comment="One-time token for QR/inbound binding",
    )
    channel_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment='Channel type: "wechat" | "feishu" | "wecom" | "webhook"',
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name",
    )
    target: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Manual target, e.g. webhook URL",
    )
    gateway_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment=(
            "绑定这条渠道的网关账号ID。入站解析时用它限定归属——"
            "签名只证明'某个合法网关'，不证明'这个用户所属的网关'"
        ),
    )
    external_user_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        index=True,
        comment="External sender/user ID, e.g. WeChat from_user_id",
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        index=True,
        comment="External conversation/session ID",
    )
    context_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Latest conversation context token for active push/reply",
    )
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="External display name",
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="External avatar URL",
    )
    secret: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Optional channel secret or token",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MessageChannelStatus.ACTIVE.value,
        index=True,
        comment='Status: "active" | "disabled"',
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this channel is selected by default",
    )
    message_types: Mapped[list[str]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=lambda: ["notification"],
        server_default='["notification"]',
        comment="Subscribed message types",
    )
    bound_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Binding completed timestamp",
    )
    last_inbound_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Last inbound message timestamp",
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Last successful delivery timestamp",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last delivery error",
    )
    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra channel settings (JSONB)",
    )
