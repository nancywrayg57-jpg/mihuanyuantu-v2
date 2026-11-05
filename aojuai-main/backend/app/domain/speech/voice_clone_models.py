"""Tenant-level speech voice clone asset models."""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON


class SpeechVoiceCloneAsset(TenantBaseModel):
    """Tenant-scoped source audio asset used for voice cloning."""

    __tablename__ = "speech_voice_clone_assets"
    __table_args__ = (
        Index("ix_speech_voice_clone_assets_tenant_created", "tenant_id", "created_at"),
        Index("ix_speech_voice_clone_assets_tenant_status", "tenant_id", "status"),
        {"comment": "租户级语音复刻源音频资产"},
    )

    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="Creator user ID",
    )
    display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Asset display name",
    )
    source_file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original uploaded filename",
    )
    source_content_type: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Uploaded content type",
    )
    source_file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Uploaded file size in bytes",
    )
    source_duration_ms: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Audio duration in milliseconds",
    )
    source_storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Private storage path for the uploaded audio",
    )
    source_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash for duplicate diagnostics",
    )
    transcript_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional transcript provided by the user",
    )
    language_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="Declared language for the source sample",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploaded",
        server_default="uploaded",
        index=True,
        comment="Asset status: uploaded | deleted",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last processing error if any",
    )
    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra asset metadata",
    )


class SpeechVoiceCloneProfile(TenantBaseModel):
    """Tenant-level cloned voice profile."""

    __tablename__ = "speech_voice_clones"
    __table_args__ = (
        Index("ix_speech_voice_clones_tenant_created", "tenant_id", "created_at"),
        Index("ix_speech_voice_clones_tenant_status", "tenant_id", "status"),
        Index("ix_speech_voice_clones_tenant_voice", "tenant_id", "remote_voice_id"),
        {"comment": "租户级语音复刻结果档案"},
    )

    asset_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("speech_voice_clone_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Linked source asset ID",
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="Creator user ID",
    )
    display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Clone display name",
    )
    provider_id: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="aliyun_qwen_tts",
        server_default="aliyun_qwen_tts",
        comment="Provider identifier",
    )
    enrollment_model: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Voice enrollment model",
    )
    synthesis_model: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Voice clone synthesis model",
    )
    remote_voice_id: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        comment="Voice identifier returned by provider",
    )
    language_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="Declared language for the clone sample",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ready",
        server_default="ready",
        index=True,
        comment="Clone status: ready | failed | deleted",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Provider-side error message",
    )
    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra clone metadata",
    )
