"""speech voice clone foundation

Revision ID: base_20260424_speech_voice_clone_foundation
Revises: base_20260411_credit_transaction_idempotency
Create Date: 2026-04-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "base_20260424_speech_voice_clone_foundation"
down_revision: Union[str, Sequence[str], None] = "base_20260411_credit_transaction_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    if not _table_exists("speech_voice_clone_assets"):
        op.create_table(
            "speech_voice_clone_assets",
            sa.Column("created_by_user_id", sa.BigInteger(), nullable=False, comment="Creator user ID"),
            sa.Column("display_name", sa.String(length=120), nullable=False, comment="Asset display name"),
            sa.Column("source_file_name", sa.String(length=255), nullable=False, comment="Original uploaded filename"),
            sa.Column("source_content_type", sa.String(length=120), nullable=False, comment="Uploaded content type"),
            sa.Column("source_file_size_bytes", sa.BigInteger(), nullable=False, comment="Uploaded file size in bytes"),
            sa.Column("source_duration_ms", sa.BigInteger(), nullable=False, comment="Audio duration in milliseconds"),
            sa.Column("source_storage_path", sa.String(length=500), nullable=False, comment="Private storage path for the uploaded audio"),
            sa.Column("source_sha256", sa.String(length=64), nullable=False, comment="SHA-256 hash for duplicate diagnostics"),
            sa.Column("transcript_text", sa.Text(), nullable=True, comment="Optional transcript provided by the user"),
            sa.Column("language_type", sa.String(length=32), nullable=True, comment="Declared language for the source sample"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'uploaded'"), comment="Asset status: uploaded | deleted"),
            sa.Column("last_error", sa.Text(), nullable=True, comment="Last processing error if any"),
            sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb"), comment="Extra asset metadata"),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
            sa.PrimaryKeyConstraint("id"),
            comment="租户级语音复刻源音频资产",
        )
    _create_index_if_missing("ix_speech_voice_clone_assets_tenant_created", "speech_voice_clone_assets", ["tenant_id", "created_at"])
    _create_index_if_missing("ix_speech_voice_clone_assets_tenant_status", "speech_voice_clone_assets", ["tenant_id", "status"])
    _create_index_if_missing(op.f("ix_speech_voice_clone_assets_created_by_user_id"), "speech_voice_clone_assets", ["created_by_user_id"])
    _create_index_if_missing(op.f("ix_speech_voice_clone_assets_status"), "speech_voice_clone_assets", ["status"])
    _create_index_if_missing(op.f("ix_speech_voice_clone_assets_tenant_id"), "speech_voice_clone_assets", ["tenant_id"])

    if not _table_exists("speech_voice_clones"):
        op.create_table(
            "speech_voice_clones",
            sa.Column("asset_id", sa.BigInteger(), nullable=False, comment="Linked source asset ID"),
            sa.Column("created_by_user_id", sa.BigInteger(), nullable=False, comment="Creator user ID"),
            sa.Column("display_name", sa.String(length=120), nullable=False, comment="Clone display name"),
            sa.Column("provider_id", sa.String(length=80), nullable=False, server_default=sa.text("'aliyun_qwen_tts'"), comment="Provider identifier"),
            sa.Column("enrollment_model", sa.String(length=120), nullable=False, comment="Voice enrollment model"),
            sa.Column("synthesis_model", sa.String(length=120), nullable=False, comment="Voice clone synthesis model"),
            sa.Column("remote_voice_id", sa.String(length=160), nullable=False, comment="Voice identifier returned by provider"),
            sa.Column("language_type", sa.String(length=32), nullable=True, comment="Declared language for the clone sample"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'ready'"), comment="Clone status: ready | failed | deleted"),
            sa.Column("error_message", sa.Text(), nullable=True, comment="Provider-side error message"),
            sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb"), comment="Extra clone metadata"),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
            sa.ForeignKeyConstraint(["asset_id"], ["speech_voice_clone_assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            comment="租户级语音复刻结果档案",
        )
    _create_index_if_missing("ix_speech_voice_clones_tenant_created", "speech_voice_clones", ["tenant_id", "created_at"])
    _create_index_if_missing("ix_speech_voice_clones_tenant_status", "speech_voice_clones", ["tenant_id", "status"])
    _create_index_if_missing("ix_speech_voice_clones_tenant_voice", "speech_voice_clones", ["tenant_id", "remote_voice_id"])
    _create_index_if_missing(op.f("ix_speech_voice_clones_asset_id"), "speech_voice_clones", ["asset_id"])
    _create_index_if_missing(op.f("ix_speech_voice_clones_created_by_user_id"), "speech_voice_clones", ["created_by_user_id"])
    _create_index_if_missing(op.f("ix_speech_voice_clones_status"), "speech_voice_clones", ["status"])
    _create_index_if_missing(op.f("ix_speech_voice_clones_tenant_id"), "speech_voice_clones", ["tenant_id"])


def downgrade() -> None:
    if _table_exists("speech_voice_clones"):
        for index_name in (
            op.f("ix_speech_voice_clones_tenant_id"),
            op.f("ix_speech_voice_clones_status"),
            op.f("ix_speech_voice_clones_created_by_user_id"),
            op.f("ix_speech_voice_clones_asset_id"),
            "ix_speech_voice_clones_tenant_voice",
            "ix_speech_voice_clones_tenant_status",
            "ix_speech_voice_clones_tenant_created",
        ):
            if _index_exists("speech_voice_clones", index_name):
                op.drop_index(index_name, table_name="speech_voice_clones")
        op.drop_table("speech_voice_clones")

    if _table_exists("speech_voice_clone_assets"):
        for index_name in (
            op.f("ix_speech_voice_clone_assets_tenant_id"),
            op.f("ix_speech_voice_clone_assets_status"),
            op.f("ix_speech_voice_clone_assets_created_by_user_id"),
            "ix_speech_voice_clone_assets_tenant_status",
            "ix_speech_voice_clone_assets_tenant_created",
        ):
            if _index_exists("speech_voice_clone_assets", index_name):
                op.drop_index(index_name, table_name="speech_voice_clone_assets")
        op.drop_table("speech_voice_clone_assets")
