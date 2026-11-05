"""api keys: machine credentials for local sync clients

Revision ID: base_20260827_api_keys
Revises: base_20260827_credit_price_cache_write
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "base_20260827_api_keys"
down_revision: str | None = "base_20260827_credit_price_cache_write"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    if _table_exists("api_keys"):
        return
    op.create_table(
        "api_keys",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="属主用户ID"),
        sa.Column("name", sa.String(200), nullable=False, comment="用途名称"),
        sa.Column("key_prefix", sa.String(16), nullable=False, comment="明文前缀"),
        sa.Column("key_hash", sa.String(64), nullable=False, comment="SHA-256(明文key)"),
        sa.Column(
            "scopes", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False,
            server_default="[]", comment="允许的 API 路径前缀列表",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="过期时间"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True, comment="最近使用"),
        comment="API Key 表",
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index(
        "uq_api_keys_key_hash",
        "api_keys",
        ["key_hash"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_api_keys_tenant_user", "api_keys", ["tenant_id", "user_id"])


def downgrade() -> None:
    if _table_exists("api_keys"):
        op.drop_table("api_keys")
