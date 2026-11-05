"""add idempotency key for credit transactions

Revision ID: base_20260411_credit_transaction_idempotency
Revises: base_20260402_fix_system_root_and_tenant_admin_grants
Create Date: 2026-04-11

Goals:
- support opt-in idempotent credit deduction without changing existing transaction semantics
- keep legacy rows untouched by using a nullable column
- enforce tenant-scoped uniqueness only when idempotency_key is present
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op

revision: str = "base_20260411_credit_transaction_idempotency"
down_revision: str | None = "base_20260402_fix_system_root_and_tenant_admin_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {item["name"] for item in inspector.get_columns(table_name)}


def _has_index(inspector: Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {item["name"] for item in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)

    if not _has_column(inspector, "credit_transactions", "idempotency_key"):
        op.add_column(
            "credit_transactions",
            sa.Column("idempotency_key", sa.String(length=120), nullable=True, comment="幂等扣费键，同租户内唯一（为空表示不启用幂等）"),
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "credit_transactions", "uq_credit_transactions_tenant_idempotency_key"):
        op.create_index(
            "uq_credit_transactions_tenant_idempotency_key",
            "credit_transactions",
            ["tenant_id", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)

    if _has_index(inspector, "credit_transactions", "uq_credit_transactions_tenant_idempotency_key"):
        op.drop_index("uq_credit_transactions_tenant_idempotency_key", table_name="credit_transactions")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "credit_transactions", "idempotency_key"):
        op.drop_column("credit_transactions", "idempotency_key")
