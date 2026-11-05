"""create the sample items table

Revision ID: sample_items_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "sample_items_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cap_sample_items",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # PortablePK：PostgreSQL 用 BIGINT；SQLite 只有 INTEGER PRIMARY KEY 才是可靠的 ROWID 自增。
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Official capability sample items",
    )
    op.create_index(
        "ix_cap_sample_items_tenant_id",
        "cap_sample_items",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "uq_cap_sample_items_tenant_code_active",
        "cap_sample_items",
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_cap_sample_items_tenant_code_active",
        table_name="cap_sample_items",
    )
    op.drop_index("ix_cap_sample_items_tenant_id", table_name="cap_sample_items")
    op.drop_table("cap_sample_items")
