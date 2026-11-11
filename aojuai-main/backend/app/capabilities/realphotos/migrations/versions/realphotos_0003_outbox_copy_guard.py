"""Outbox delivery columns + copy execution guard (REMAIN-GAP R3/R4 path A).

Revision ID: realphotos_0003
Revises: realphotos_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "realphotos_0003"
down_revision: str | None = "realphotos_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {str(c["name"]) for c in sa_inspect(bind).get_columns(table)}
    return column in cols


def _has_table(table: str) -> bool:
    return sa_inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if _has_table("cap_realphotos_outbox"):
        if not _has_column("cap_realphotos_outbox", "recipient_user_id"):
            op.add_column(
                "cap_realphotos_outbox",
                sa.Column("recipient_user_id", sa.BigInteger(), nullable=True),
            )
        if not _has_column("cap_realphotos_outbox", "attempt_count"):
            op.add_column(
                "cap_realphotos_outbox",
                sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
            )
        if not _has_column("cap_realphotos_outbox", "next_attempt_at"):
            op.add_column(
                "cap_realphotos_outbox",
                sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not _has_column("cap_realphotos_outbox", "last_error"):
            op.add_column(
                "cap_realphotos_outbox",
                sa.Column("last_error", sa.Text(), nullable=True),
            )
        # claim index（幂等创建）
        bind = op.get_bind()
        indexes = {str(ix["name"]) for ix in sa_inspect(bind).get_indexes("cap_realphotos_outbox")}
        if "ix_cap_realphotos_outbox_claim" not in indexes:
            op.create_index(
                "ix_cap_realphotos_outbox_claim",
                "cap_realphotos_outbox",
                ["status", "next_attempt_at", "created_at"],
            )

    if _has_table("cap_realphotos_merchant_profiles"):
        if not _has_column("cap_realphotos_merchant_profiles", "copy_latch_batch_id"):
            op.add_column(
                "cap_realphotos_merchant_profiles",
                sa.Column("copy_latch_batch_id", sa.BigInteger(), nullable=True),
            )
        if not _has_column("cap_realphotos_merchant_profiles", "copy_latch_active"):
            op.add_column(
                "cap_realphotos_merchant_profiles",
                sa.Column(
                    "copy_latch_active",
                    sa.Boolean(),
                    server_default="false",
                    nullable=False,
                ),
            )

    if not _has_table("cap_realphotos_copy_execution_guards"):
        op.create_table(
            "cap_realphotos_copy_execution_guards",
            sa.Column("id", _PK, autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
            sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("guard_epoch", sa.Integer(), server_default="1", nullable=False),
            sa.Column("state", sa.String(length=32), server_default="active", nullable=False),
            sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            comment="realphotos copy execution guards (AD-005)",
        )
        op.create_index(
            "ix_cap_realphotos_copy_execution_guards_tenant_id",
            "cap_realphotos_copy_execution_guards",
            ["tenant_id"],
        )
        op.create_index(
            "ix_cap_realphotos_copy_execution_guards_owner_account_id",
            "cap_realphotos_copy_execution_guards",
            ["owner_account_id"],
        )
        op.create_index(
            "ix_cap_realphotos_copy_guard_batch",
            "cap_realphotos_copy_execution_guards",
            ["tenant_id", "batch_id"],
        )
        op.create_index(
            "uq_cap_realphotos_copy_guard_active_owner",
            "cap_realphotos_copy_execution_guards",
            ["tenant_id", "owner_account_id"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL AND state = 'active'"),
            sqlite_where=sa.text("deleted_at IS NULL AND state = 'active'"),
        )

    # 将历史 copy_latch_* 迁入 guard 表（仅 active）
    if _has_table("cap_realphotos_merchant_profiles") and _has_table(
        "cap_realphotos_copy_execution_guards"
    ):
        if _has_column("cap_realphotos_merchant_profiles", "copy_latch_active"):
            op.execute(
                sa.text(
                    """
                    INSERT INTO cap_realphotos_copy_execution_guards
                        (tenant_id, owner_account_id, batch_id, guard_epoch, state, version, created_at)
                    SELECT
                        p.tenant_id,
                        p.user_id,
                        COALESCE(p.copy_latch_batch_id, 0),
                        1,
                        'active',
                        1,
                        CURRENT_TIMESTAMP
                    FROM cap_realphotos_merchant_profiles p
                    WHERE p.deleted_at IS NULL
                      AND COALESCE(p.copy_latch_active, false) = true
                      AND p.copy_latch_batch_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM cap_realphotos_copy_execution_guards g
                        WHERE g.tenant_id = p.tenant_id
                          AND g.owner_account_id = p.user_id
                          AND g.state = 'active'
                          AND g.deleted_at IS NULL
                      )
                    """
                )
            )


def downgrade() -> None:
    if _has_table("cap_realphotos_copy_execution_guards"):
        op.drop_table("cap_realphotos_copy_execution_guards")
    # 不回撤 outbox / copy_latch 列：生产已写数据，前向兼容。
    _ = postgresql  # keep dialect import used for review tooling symmetry
