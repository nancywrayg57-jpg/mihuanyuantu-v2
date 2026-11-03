"""add user message channels

Revision ID: base_20260425_user_message_channels
Revises: base_20260411_credit_transaction_idempotency
Create Date: 2026-04-25

Adds system-level per-user message channel bindings for personal
OpenClaw/QClaw-style integrations such as WeChat and Feishu gateways.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

from alembic import op

revision: str = "base_20260425_user_message_channels"
down_revision: str | None = "base_20260411_credit_transaction_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(inspector: Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {item["name"] for item in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)


    if not _has_table(inspector, "message_gateway_accounts"):
        op.create_table(
            "message_gateway_accounts",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("channel_type", sa.String(length=30), nullable=False, comment='"wechat" | "feishu"'),
            sa.Column("name", sa.String(length=100), nullable=False, comment="Gateway account display name"),
            sa.Column("account_id", sa.String(length=200), nullable=True, comment="Bot/account ID"),
            sa.Column("base_url", sa.String(length=500), nullable=True, comment="Provider API base URL"),
            sa.Column("token_encrypted", sa.Text(), nullable=True, comment="Encrypted provider token"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="disabled", comment='"active" | "disabled" | "expired"'),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false(), comment="Default account for this channel type"),
            sa.Column("get_updates_buf", sa.Text(), nullable=True, comment="Long-poll cursor"),
            sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True, comment="Last poll timestamp"),
            sa.Column("last_error", sa.Text(), nullable=True, comment="Last gateway error"),
            sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False, comment="Extra gateway state"),
            sa.PrimaryKeyConstraint("id"),
            comment="系统消息 Channel 网关账号表",
        )

    inspector = sa.inspect(bind)
    for index_name, columns in (
        ("ix_message_gateway_accounts_channel_type", ["channel_type"]),
        ("ix_message_gateway_accounts_account_id", ["account_id"]),
        ("ix_message_gateway_accounts_status", ["status"]),
        ("ix_message_gateway_accounts_is_default", ["is_default"]),
    ):
        if not _has_index(inspector, "message_gateway_accounts", index_name):
            op.create_index(index_name, "message_gateway_accounts", columns, unique=False)

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "message_gateway_accounts", "uq_message_gateway_accounts_default"):
        op.create_index(
            "uq_message_gateway_accounts_default",
            "message_gateway_accounts",
            ["channel_type", "is_default"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL AND is_default IS TRUE"),
        )

    if not _has_table(inspector, "user_message_channels"):
        op.create_table(
            "user_message_channels",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False, comment="Owner user ID"),
            sa.Column("bind_token", sa.String(length=120), nullable=True, comment="One-time token for QR/inbound binding"),
            sa.Column("channel_type", sa.String(length=30), nullable=False, comment='Channel type: "wechat" | "feishu" | "webhook"'),
            sa.Column("name", sa.String(length=100), nullable=False, comment="Display name"),
            sa.Column("target", sa.String(length=500), nullable=True, comment="Manual target, e.g. webhook URL"),
            sa.Column("external_user_id", sa.String(length=200), nullable=True, comment="External sender/user ID, e.g. WeChat from_user_id"),
            sa.Column("conversation_id", sa.String(length=200), nullable=True, comment="External conversation/session ID"),
            sa.Column("context_token", sa.Text(), nullable=True, comment="Latest conversation context token for active push/reply"),
            sa.Column("display_name", sa.String(length=100), nullable=True, comment="External display name"),
            sa.Column("avatar", sa.String(length=500), nullable=True, comment="External avatar URL"),
            sa.Column("secret", sa.String(length=500), nullable=True, comment="Optional channel secret or token"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending", comment='Status: "pending" | "active" | "disabled"'),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false(), comment="Whether this channel is selected by default"),
            sa.Column("message_types", postgresql.JSONB(astext_type=sa.Text()), server_default='["notification"]', nullable=False, comment="Subscribed message types"),
            sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True, comment="Binding completed timestamp"),
            sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True, comment="Last inbound message timestamp"),
            sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True, comment="Last successful delivery timestamp"),
            sa.Column("last_error", sa.Text(), nullable=True, comment="Last delivery error"),
            sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False, comment="Extra channel settings (JSONB)"),
            sa.PrimaryKeyConstraint("id"),
            comment="用户个人消息 Channel 绑定表",
        )

    inspector = sa.inspect(bind)
    for index_name, columns in (
        ("ix_user_message_channels_user_id", ["user_id"]),
        ("ix_user_message_channels_external_user_id", ["external_user_id"]),
        ("ix_user_message_channels_conversation_id", ["conversation_id"]),
        ("ix_user_message_channels_channel_type", ["channel_type"]),
        ("ix_user_message_channels_status", ["status"]),
        ("ix_user_message_channels_is_default", ["is_default"]),
    ):
        if not _has_index(inspector, "user_message_channels", index_name):
            op.create_index(index_name, "user_message_channels", columns, unique=False)

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "user_message_channels", "uq_user_message_channels_bind_token"):
        op.create_index(
            "uq_user_message_channels_bind_token",
            "user_message_channels",
            ["bind_token"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL AND bind_token IS NOT NULL"),
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "user_message_channels", "uq_user_message_channels_default"):
        op.create_index(
            "uq_user_message_channels_default",
            "user_message_channels",
            ["user_id", "is_default"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL AND is_default IS TRUE"),
        )

    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY user_id, channel_type
                        ORDER BY
                            CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                            id DESC
                    ) AS rn
                FROM user_message_channels
                WHERE deleted_at IS NULL
                  AND channel_type IN ('wechat', 'feishu')
                  AND status IN ('active', 'pending')
            )
            UPDATE user_message_channels AS channel
               SET bind_token = NULL,
                   last_error = '已有同类型个人 Channel，当前重复绑定请求已失效',
                   deleted_at = now(),
                   updated_at = now()
              FROM ranked
             WHERE channel.id = ranked.id
               AND ranked.rn > 1
            """
        )
    )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "user_message_channels", "uq_user_message_channels_user_gateway_type"):
        op.create_index(
            "uq_user_message_channels_user_gateway_type",
            "user_message_channels",
            ["user_id", "channel_type"],
            unique=True,
            postgresql_where=sa.text(
                "deleted_at IS NULL AND channel_type IN ('wechat', 'feishu') AND status IN ('active', 'pending')"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)
    if _has_table(inspector, "user_message_channels"):
        op.drop_table("user_message_channels")
    inspector = sa.inspect(bind)
    if _has_table(inspector, "message_gateway_accounts"):
        op.drop_table("message_gateway_accounts")
