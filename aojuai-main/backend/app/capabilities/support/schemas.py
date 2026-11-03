"""API schemas for the support capability."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

SupportCategory = Literal["question", "incident", "billing", "feature", "other"]
SupportStatus = Literal["open", "pending", "resolved", "closed"]
SupportPriority = Literal["low", "normal", "high", "urgent"]


class UserBrief(BaseModel):
    id: int
    username: str | None = None
    nickname: str | None = None
    email: str | None = None


class TicketMessageItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    ticket_id: int = Field(..., alias="ticketId")
    author_user_id: int | None = Field(None, alias="authorUserId")
    author: UserBrief | None = None
    author_role: str = Field(..., alias="authorRole")
    message_type: str = Field(..., alias="messageType")
    body: str
    is_internal: bool = Field(False, alias="isInternal")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = Field(None, alias="createdAt")


class TicketListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    ticket_no: str | None = Field(None, alias="ticketNo")
    requester_user_id: int = Field(..., alias="requesterUserId")
    requester: UserBrief | None = None
    assignee_user_id: int | None = Field(None, alias="assigneeUserId")
    assignee: UserBrief | None = None
    category: str
    status: str
    priority: str
    subject: str
    related_type: str | None = Field(None, alias="relatedType")
    related_id: str | None = Field(None, alias="relatedId")
    last_message_at: datetime | None = Field(None, alias="lastMessageAt")
    last_replied_at: datetime | None = Field(None, alias="lastRepliedAt")
    sla_hours: int = Field(0, alias="slaHours")
    sla_due_at: datetime | None = Field(None, alias="slaDueAt")
    sla_overdue: bool = Field(False, alias="slaOverdue")
    waiting_hours: float | None = Field(None, alias="waitingHours")
    resolved_at: datetime | None = Field(None, alias="resolvedAt")
    closed_at: datetime | None = Field(None, alias="closedAt")
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    extra: dict[str, Any] = Field(default_factory=dict)


class TicketDetail(TicketListItem):
    description: str
    messages: list[TicketMessageItem] = Field(default_factory=list)


class TicketCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: SupportCategory = "other"
    priority: SupportPriority = "normal"
    subject: str = Field(..., min_length=2, max_length=200)
    description: str = Field(..., min_length=2, max_length=5000)
    # related_type 保持自由字符串：它的取值由调用方定义，
    # 本模块不认识任何具体业务实体（这正是它能被任何分支复用的原因）。
    related_type: str | None = Field(None, alias="relatedType", max_length=40)
    related_id: str | None = Field(None, alias="relatedId", max_length=80)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class TicketMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class AdminMessageCreate(TicketMessageCreate):
    model_config = ConfigDict(populate_by_name=True)

    is_internal: bool = Field(False, alias="isInternal")
    status: SupportStatus | None = None


class TicketUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: SupportCategory | None = None
    status: SupportStatus | None = None
    priority: SupportPriority | None = None
    assignee_user_id: int | None = Field(None, alias="assigneeUserId", ge=1)
    clear_assignee: bool = Field(False, alias="clearAssignee")
    subject: str | None = Field(None, min_length=2, max_length=200)
    related_type: str | None = Field(None, alias="relatedType", max_length=40)
    related_id: str | None = Field(None, alias="relatedId", max_length=80)
    internal_note: str | None = Field(None, alias="internalNote", max_length=5000)


class TicketListQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(1, ge=1, validation_alias=AliasChoices("page", "currentPage"))
    page_size: int = Field(
        20, ge=1, le=100, validation_alias=AliasChoices("pageSize", "page_size", "size")
    )
    status: SupportStatus | None = None
    category: SupportCategory | None = None
    priority: SupportPriority | None = None
    keyword: str | None = Field(None, max_length=120)


class AdminTicketListQuery(TicketListQuery):
    requester_user_id: int | None = Field(None, alias="requesterUserId", ge=1)
    assignee_user_id: int | None = Field(None, alias="assigneeUserId", ge=1)
    unassigned: bool | None = None
    related_type: str | None = Field(None, alias="relatedType", max_length=40)
    exclude_related_type: str | None = Field(None, alias="excludeRelatedType", max_length=40)


class PublicTicketCreate(BaseModel):
    """Anonymous submission payload.

    `website` 是蜜罐字段：正常浏览器看不见它，机器人会照填。命中时**静默接受**——
    报错等于告诉对方这里有防护。
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., min_length=3, max_length=160)
    subject: str | None = Field(None, max_length=200)
    message: str = Field(..., min_length=2, max_length=5000)
    category: SupportCategory = "other"
    source_page: str | None = Field(None, alias="sourcePage", max_length=200)
    website: str | None = Field(None, max_length=200)


class PublicTicketReceipt(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accepted: bool = True
    ticket_id: int | None = Field(None, alias="ticketId")
    ticket_no: str | None = Field(None, alias="ticketNo")


class SupportOptions(BaseModel):
    """Only values travel over the wire; labels come from the frontend locale pack."""

    categories: list[str]
    statuses: list[str]
    priorities: list[str]


class SupportSummary(BaseModel):
    total: int = 0
    open: int = 0
    pending: int = 0
    resolved: int = 0
    closed: int = 0
