"""tenant-level AI outbound redaction policies (versioned, per scope)

Revision ID: base_20260828_tenant_redaction_policies
Revises: base_20260827_user_import_menu

双方言：JSON 走 with_variant，缺省值不用 PostgreSQL 专有 cast / now()。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "base_20260828_tenant_redaction_policies"
down_revision: str | Sequence[str] | None = "base_20260827_user_import_menu"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "tenant_redaction_policies"


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table(TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False, server_default="*"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rules", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("approved_by", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="租户级 AI 出站脱敏策略（按 scope 版本化）",
    )
    op.create_index("ix_tenant_redaction_policies_tenant_id", TABLE, ["tenant_id"])
    op.create_index(
        "uq_tenant_redaction_policies_version",
        TABLE,
        ["tenant_id", "scope", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_tenant_redaction_policies_active", TABLE, ["tenant_id", "scope", "is_active"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
