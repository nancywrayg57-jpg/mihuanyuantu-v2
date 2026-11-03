"""harden inbound message gateway authentication

Revision ID: base_20260820_gateway_auth
Revises: base_20260809_system_menu_backfill
Create Date: 2026-08-20

The nonce table makes replay rejection consistent across API workers.  The
binding guard table keeps failed-code counters consistent across workers too.
All stored identifiers are one-way digests; gateway secrets remain in the
existing encrypted column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op

revision: str = "base_20260820_gateway_auth"
down_revision: str | None = "base_20260809_system_menu_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NONCE_TABLE = "message_gateway_inbound_nonces"
_BIND_GUARD_TABLE = "message_channel_bind_guards"


def _inspector() -> Inspector:
    return sa.inspect(op.get_bind())


def _has_table(inspector: Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: Inspector, table_name: str, index_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(item["name"] == index_name for item in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = _inspector()
    if not _has_table(inspector, _NONCE_TABLE):
        op.create_table(
            _NONCE_TABLE,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("gateway_account_id", sa.BigInteger(), nullable=False),
            sa.Column("nonce_digest", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            comment="消息网关入站签名 nonce 防重放表",
        )

    inspector = _inspector()
    if not _has_index(
        inspector,
        _NONCE_TABLE,
        "uq_message_gateway_inbound_nonces_account_digest",
    ):
        op.create_index(
            "uq_message_gateway_inbound_nonces_account_digest",
            _NONCE_TABLE,
            ["gateway_account_id", "nonce_digest"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )
    if not _has_index(inspector, _NONCE_TABLE, "ix_message_gateway_inbound_nonces_expires_at"):
        op.create_index(
            "ix_message_gateway_inbound_nonces_expires_at",
            _NONCE_TABLE,
            ["expires_at"],
        )

    inspector = _inspector()
    if not _has_table(inspector, _BIND_GUARD_TABLE):
        op.create_table(
            _BIND_GUARD_TABLE,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("guard_key", sa.String(length=64), nullable=False),
            sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            comment="消息 Channel 关联码失败计数与限流表",
        )

    inspector = _inspector()
    if not _has_index(inspector, _BIND_GUARD_TABLE, "uq_message_channel_bind_guards_key"):
        op.create_index(
            "uq_message_channel_bind_guards_key",
            _BIND_GUARD_TABLE,
            ["guard_key"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )
    if not _has_index(inspector, _BIND_GUARD_TABLE, "ix_message_channel_bind_guards_expires_at"):
        op.create_index(
            "ix_message_channel_bind_guards_expires_at",
            _BIND_GUARD_TABLE,
            ["expires_at"],
        )

    # These legacy values were stored as plain JSON and are no longer part of
    # inbound authentication.  The expression is idempotent on repeated runs.
    if _has_table(_inspector(), "message_gateway_accounts"):
        op.execute(
            """
            UPDATE message_gateway_accounts
            SET extra = extra - 'verificationToken' - 'encryptKey'
            WHERE extra ? 'verificationToken' OR extra ? 'encryptKey'
            """
        )


def downgrade() -> None:
    inspector = _inspector()
    if _has_table(inspector, _BIND_GUARD_TABLE):
        op.drop_table(_BIND_GUARD_TABLE)
    inspector = _inspector()
    if _has_table(inspector, _NONCE_TABLE):
        op.drop_table(_NONCE_TABLE)
    # Scrubbed plaintext callback values are intentionally not restored.
