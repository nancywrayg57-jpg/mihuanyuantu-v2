"""
AOJU Backend - Speech Models

租户级语音配置（仅配置项，不包含具体 TTS/ASR 运行逻辑）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Index, String, text
from app.infrastructure.database.types import PortableJSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel


class SpeechTenantConfig(TenantBaseModel):
    """
    Speech Tenant Config

    - config: 非敏感配置（provider 选择、参数等）
    - secrets: 敏感配置（api_key/access_token 等），API 返回时必须脱敏
    """

    __tablename__ = "speech_tenant_configs"
    __table_args__ = (
        Index(
            "uq_speech_tenant_configs_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "租户语音配置表（TTS/STT Provider 配置与密钥）"},
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
        comment="Operational status: active | degraded | error | disabled",
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

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        comment="Legacy availability mirror; synced from canonical enabled/status contract",
    )
