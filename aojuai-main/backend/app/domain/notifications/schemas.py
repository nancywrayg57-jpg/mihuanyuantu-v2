"""
AOJU Backend - Notification Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

NotificationCategoryLiteral = Literal["notification", "message", "todo"]
NotificationPriorityLiteral = Literal["low", "normal", "high", "urgent"]
MessageChannelTypeLiteral = Literal["wechat", "feishu", "wecom", "webhook"]
MessageChannelStatusLiteral = Literal["pending", "active", "disabled"]


class NotificationListItem(BaseModel):
    """Notification list item schema (for current user)"""

    id: int
    category: str
    title: str
    content: str | None = None
    avatar: str | None = None

    is_read: bool = Field(False, alias="isRead")
    read_at: datetime | None = Field(None, alias="readAt")

    reference_type: str | None = Field(None, alias="referenceType")
    reference_id: int | None = Field(None, alias="referenceId")
    sender_id: int | None = Field(None, alias="senderId")
    sender_name: str | None = Field(None, alias="senderName")

    priority: str = "normal"
    status: str | None = None
    expire_at: datetime | None = Field(None, alias="expireAt")

    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class NotificationDetail(BaseModel):
    """Notification detail schema"""

    id: int
    tenant_id: int = Field(..., alias="tenantId")
    user_id: int = Field(..., alias="userId")

    category: str
    title: str
    content: str | None = None
    avatar: str | None = None

    is_read: bool = Field(False, alias="isRead")
    read_at: datetime | None = Field(None, alias="readAt")

    reference_type: str | None = Field(None, alias="referenceType")
    reference_id: int | None = Field(None, alias="referenceId")
    sender_id: int | None = Field(None, alias="senderId")
    sender_name: str | None = Field(None, alias="senderName")

    priority: str = "normal"
    status: str | None = None
    expire_at: datetime | None = Field(None, alias="expireAt")

    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class NotificationSendRequest(BaseModel):
    """Send notification request (admin/system)"""

    user_id: int = Field(..., alias="userId", ge=1)
    category: NotificationCategoryLiteral
    title: str = Field(..., min_length=1, max_length=200)

    content: str | None = None
    avatar: str | None = None

    reference_type: str | None = Field(None, alias="referenceType")
    reference_id: int | None = Field(None, alias="referenceId", ge=1)
    sender_id: int | None = Field(None, alias="senderId", ge=1)
    sender_name: str | None = Field(None, alias="senderName", max_length=100)

    priority: NotificationPriorityLiteral = "normal"
    status: str | None = None
    expire_at: datetime | None = Field(None, alias="expireAt")

    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class NotificationBroadcastRequest(BaseModel):
    """Broadcast notification request (superuser only)."""

    category: NotificationCategoryLiteral
    title: str = Field(..., min_length=1, max_length=200)

    content: str | None = None
    avatar: str | None = None

    reference_type: str | None = Field(None, alias="referenceType")
    reference_id: int | None = Field(None, alias="referenceId", ge=1)
    sender_id: int | None = Field(None, alias="senderId", ge=1)
    sender_name: str | None = Field(None, alias="senderName", max_length=100)

    priority: NotificationPriorityLiteral = "normal"
    status: str | None = None
    expire_at: datetime | None = Field(None, alias="expireAt")

    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class NotificationUnreadCountResponse(BaseModel):
    """Unread count response"""

    unread_count: int = Field(..., alias="unreadCount", ge=0)

    model_config = ConfigDict(populate_by_name=True)


class NotificationReadAllResponse(BaseModel):
    """Mark all as read response"""

    updated: int = Field(..., ge=0)


class NotificationBulkSendRequest(BaseModel):
    """Bulk send notification request (tenant admin/system)."""

    user_ids: list[int] = Field(default_factory=list, alias="userIds", description="目标用户ID列表")
    team_ids: list[int] = Field(default_factory=list, alias="teamIds", description="目标团队ID列表")
    include_children: bool = Field(True, alias="includeChildren", description="团队是否包含子团队")

    category: NotificationCategoryLiteral
    title: str = Field(..., min_length=1, max_length=200)

    content: str | None = None
    avatar: str | None = None

    reference_type: str | None = Field(None, alias="referenceType")
    reference_id: int | None = Field(None, alias="referenceId", ge=1)
    sender_id: int | None = Field(None, alias="senderId", ge=1)
    sender_name: str | None = Field(None, alias="senderName", max_length=100)

    priority: NotificationPriorityLiteral = "normal"
    status: str | None = None
    expire_at: datetime | None = Field(None, alias="expireAt")

    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class NotificationBulkSendResponse(BaseModel):
    """Bulk send response"""

    requested: int = Field(..., ge=0)
    sent: int = Field(..., ge=0)


class UserMessageChannelItem(BaseModel):
    """User message channel list item."""

    id: int
    channel_type: str = Field(..., alias="channelType")
    name: str
    target: str | None = None
    external_user_id: str | None = Field(None, alias="externalUserId")
    conversation_id: str | None = Field(None, alias="conversationId")
    display_name: str | None = Field(None, alias="displayName")
    avatar: str | None = None
    status: str = "active"
    is_default: bool = Field(False, alias="isDefault")
    message_types: list[str] = Field(default_factory=lambda: ["notification"], alias="messageTypes")
    bound_at: datetime | None = Field(None, alias="boundAt")
    last_inbound_at: datetime | None = Field(None, alias="lastInboundAt")
    last_sent_at: datetime | None = Field(None, alias="lastSentAt")
    last_error: str | None = Field(None, alias="lastError")
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class UserMessageChannelUpsertRequest(BaseModel):
    """Create or update current user's outbound message channel."""

    name: str = Field(..., min_length=1, max_length=100)
    target: str | None = Field(None, max_length=500)
    secret: str | None = Field(None, max_length=500)
    status: MessageChannelStatusLiteral = "active"
    is_default: bool = Field(False, alias="isDefault")
    message_types: list[str] = Field(default_factory=lambda: ["notification"], alias="messageTypes")
    # **默认 None（= 保持原样），不是 `{}`。**
    #
    # `update_user_channel` 的写法是 `extra if extra is not None else channel.extra`，
    # 所以传 `{}` 会把整个 extra 覆盖掉。而扫码绑定的渠道把会话状态存在这里：
    # 微信的 `lastInboundContextToken`、`lastInbound`、续期提醒偏好……
    # 一旦编辑表单顺手带上 `extra: {}`，这条渠道就再也发不出消息了，
    # 而且**不会报错**——只会在下次投递时莫名失败。
    #
    # 默认设成 None 之后，"没传" 才真正等于 "别动"。要清空得显式传 `{}`。
    extra: dict[str, Any] | None = None
    #: 会话到期前提醒（只对会话会过期的渠道有意义）。
    #:
    #: **单独一个字段，而不是让前端塞进 extra。** 前端拿到的 `extra` 来自页面缓存，
    #: 可能已经过时；整块提交会把期间的入站写入（context token、
    #: `lastInboundOriginAt` 等）一起回滚。后端收到这个布尔后走 PortableJSON 局部合并，
    #: 只动这一个键。（codex 复核发现）
    renewal_reminder: bool | None = Field(None, alias="renewalReminder")
    #: 会话过期时保留消息、刷新后自动补发（同样走 PortableJSON 局部合并）
    hold_until_active: bool | None = Field(None, alias="holdUntilActive")

    model_config = ConfigDict(populate_by_name=True)


class UserMessageChannelManualCreateRequest(UserMessageChannelUpsertRequest):
    """Create a manual webhook-style channel."""

    channel_type: MessageChannelTypeLiteral = Field(..., alias="channelType")


class UserMessageChannelBindStartRequest(BaseModel):
    """Start QR/inbound binding for a personal message channel."""

    channel_type: Literal["wechat", "feishu", "wecom"] = Field(..., alias="channelType")
    name: str | None = Field(None, max_length=100)
    message_types: list[str] = Field(default_factory=lambda: ["notification"], alias="messageTypes")

    model_config = ConfigDict(populate_by_name=True)


class UserMessageChannelBindStartResponse(BaseModel):
    """QR/inbound binding bootstrap response."""

    channel_id: int = Field(..., alias="channelId")
    bind_token: str = Field(..., alias="bindToken")
    binding_code: str = Field(..., alias="bindingCode")
    qr_text: str = Field(..., alias="qrText")
    qr_url: str | None = Field(None, alias="qrUrl")
    qr_image_url: str | None = Field(None, alias="qrImageUrl")
    qr_payload: str | None = Field(None, alias="qrPayload")
    verification_uri_complete: str | None = Field(None, alias="verificationUriComplete")
    scode: str | None = None
    expires_at: datetime | None = Field(None, alias="expiresAt")
    instructions: list[str] = Field(default_factory=list)
    gateway_ready: bool = Field(False, alias="gatewayReady")
    status: str = "pending"

    model_config = ConfigDict(populate_by_name=True)


class UserMessageChannelInboundBindRequest(BaseModel):
    """Gateway callback when user's first inbound message confirms binding."""

    bind_token: str = Field(
        ...,
        validation_alias=AliasChoices("bindToken", "bindingCode", "bind_code", "bindCode"),
        serialization_alias="bindToken",
        min_length=6,
        max_length=120,
    )
    channel_type: Literal["wechat", "feishu", "wecom"] = Field(..., alias="channelType")
    external_user_id: str = Field(..., alias="externalUserId", min_length=1, max_length=200)
    conversation_id: str | None = Field(None, alias="conversationId", max_length=200)
    context_token: str | None = Field(None, alias="contextToken")
    display_name: str | None = Field(None, alias="displayName", max_length=100)
    avatar: str | None = Field(None, max_length=500)
    raw_payload: dict[str, Any] = Field(default_factory=dict, alias="rawPayload")

    model_config = ConfigDict(populate_by_name=True)


class UserMessageChannelTestRequest(BaseModel):
    """Send a test message to a bound message channel."""

    title: str = Field("测试消息", min_length=1, max_length=200)
    content: str | None = "这是一条来自个人消息 Channel的测试消息。"


class UserMessageChannelTestResponse(BaseModel):
    """Channel test response."""

    ok: bool
    message: str
