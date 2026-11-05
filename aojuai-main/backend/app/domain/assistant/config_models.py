"""
AOJU Backend - AI Assistant Config Models

租户级 AI 助手配置（OpenAI 兼容 API 配置）
"""
from typing import Any

from sqlalchemy import Boolean, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON


class AssistantTenantConfig(TenantBaseModel):
    """
    AI Assistant Tenant Config - 租户级 AI 助手配置

    - enabled: 是否启用 AI 助手（租户级功能开关：影响 API 可用性）
    - deduct_credits: 是否扣除用户积分
    - credits_per_call: 每次调用扣除积分数
    - config: 非敏感配置（model、temperature 等）
    - secrets: 敏感配置（api_key 等），API 返回时必须脱敏
    """

    __tablename__ = "assistant_tenant_configs"
    __table_args__ = (
        Index(
            "uq_assistant_tenant_configs_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "租户 AI 助手配置表"},
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="是否启用 AI 助手",
    )

    deduct_credits: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="是否扣除用户积分",
    )

    credits_per_call: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="每次调用扣除积分数",
    )

    config: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Non-secret configuration (JSONB)",
    )

    secrets: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Secret configuration (JSONB)",
    )
