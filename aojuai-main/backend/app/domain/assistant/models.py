"""
AOJU Backend - AI Assistant Models

AI 全局助手数据模型
"""
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, ForeignKey, String, Text
from app.infrastructure.database.types import PortableJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import TenantBaseModel

if TYPE_CHECKING:
    from app.domain.users.models import User


class MessageRole(StrEnum):
    """消息角色"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ActionType(StrEnum):
    """操作类型"""

    ANALYZE = "analyze"
    FILL = "fill"
    SUMMARIZE = "summarize"
    SUGGEST = "suggest"
    QUERY = "query"


class AssistantSession(TenantBaseModel):
    """AI 助手会话"""

    __tablename__ = "assistant_sessions"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    module_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="模块标识",
    )
    route_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="当前路由",
    )
    context_data: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="上下文数据",
    )
    agent_app_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="关联的 Agent 应用 ID",
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    messages: Mapped[list["AssistantMessage"]] = relationship(
        "AssistantMessage",
        back_populates="session",
        lazy="selectin",
        order_by="AssistantMessage.created_at",
    )


class AssistantMessage(TenantBaseModel):
    """AI 助手消息"""

    __tablename__ = "assistant_messages"

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assistant_sessions.id"),
        nullable=False,
        index=True,
        comment="会话ID",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="消息角色: user/assistant/system",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息内容",
    )
    action_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="操作类型",
    )
    action_result: Mapped[dict[str, Any] | None] = mapped_column(
        PortableJSON,
        nullable=True,
        comment="操作结果",
    )

    session: Mapped["AssistantSession"] = relationship(
        "AssistantSession",
        back_populates="messages",
    )
