"""allow enterprise wechat personal message channels

Revision ID: base_20260827_wecom_channel_unique_index
Revises: base_20260821_channel_gateway_owner
Create Date: 2026-05-05

Documents the base-level personal Channel extension for Enterprise WeChat.
The channel type is stored in existing varchar fields, so no schema rewrite is
required; the partial uniqueness contract must include wecom.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op

revision: str = "base_20260827_wecom_channel_unique_index"
down_revision: str | None = "base_20260821_channel_gateway_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(inspector: Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {item["name"] for item in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)
    if not _has_table(inspector, "user_message_channels"):
        return

    if _has_index(inspector, "user_message_channels", "uq_user_message_channels_user_gateway_type"):
        op.drop_index("uq_user_message_channels_user_gateway_type", table_name="user_message_channels")

    op.create_index(
        "uq_user_message_channels_user_gateway_type",
        "user_message_channels",
        ["user_id", "channel_type"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND channel_type IN ('wechat', 'feishu', 'wecom') AND status IN ('active', 'pending')"
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)
    if not _has_table(inspector, "user_message_channels"):
        return

    if _has_index(inspector, "user_message_channels", "uq_user_message_channels_user_gateway_type"):
        op.drop_index("uq_user_message_channels_user_gateway_type", table_name="user_message_channels")

    op.create_index(
        "uq_user_message_channels_user_gateway_type",
        "user_message_channels",
        ["user_id", "channel_type"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND channel_type IN ('wechat', 'feishu') AND status IN ('active', 'pending')"
        ),
    )
