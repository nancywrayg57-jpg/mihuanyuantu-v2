"""S0 foundation tables for realphotos

Revision ID: realphotos_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "realphotos_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "cap_realphotos_merchant_profiles",
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("pre_review_frozen", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos merchant profiles",
    )
    op.create_index(
        "ix_cap_realphotos_merchant_profiles_tenant_id",
        "cap_realphotos_merchant_profiles",
        ["tenant_id"],
    )
    op.create_index(
        "ix_cap_realphotos_merchant_profiles_user_id",
        "cap_realphotos_merchant_profiles",
        ["user_id"],
    )
    op.create_index(
        "uq_cap_realphotos_merchant_profiles_tenant_user",
        "cap_realphotos_merchant_profiles",
        ["tenant_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "cap_realphotos_auth_challenges",
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("challenge_public_id", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("client_key", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos login captcha challenges",
    )
    op.create_index(
        "ix_cap_realphotos_auth_challenges_challenge_public_id",
        "cap_realphotos_auth_challenges",
        ["challenge_public_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_cap_realphotos_auth_challenges_expires_at",
        "cap_realphotos_auth_challenges",
        ["expires_at"],
    )
    op.create_index(
        "ix_cap_realphotos_auth_challenges_client_key",
        "cap_realphotos_auth_challenges",
        ["client_key"],
    )

    op.create_table(
        "cap_realphotos_auth_guards",
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("username_normalized", sa.String(length=64), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos login failure guards",
    )
    op.create_index(
        "uq_cap_realphotos_auth_guards_username",
        "cap_realphotos_auth_guards",
        ["username_normalized"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "cap_realphotos_credit_accounts",
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("available_integer", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("reserved_integer", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos integer credit accounts",
    )
    op.create_index(
        "ix_cap_realphotos_credit_accounts_tenant_id",
        "cap_realphotos_credit_accounts",
        ["tenant_id"],
    )
    op.create_index(
        "uq_cap_realphotos_credit_accounts_tenant",
        "cap_realphotos_credit_accounts",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "cap_realphotos_credit_ledger_entries",
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("delta_available", sa.BigInteger(), nullable=False),
        sa.Column("delta_reserved", sa.BigInteger(), nullable=False),
        sa.Column("before_available", sa.BigInteger(), nullable=False),
        sa.Column("after_available", sa.BigInteger(), nullable=False),
        sa.Column("before_reserved", sa.BigInteger(), nullable=False),
        sa.Column("after_reserved", sa.BigInteger(), nullable=False),
        sa.Column("operator_user_id", sa.BigInteger(), nullable=True),
        sa.Column("target_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reference", _JSON, server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos integer credit ledger",
    )
    op.create_index(
        "ix_cap_realphotos_credit_ledger_entries_tenant_id",
        "cap_realphotos_credit_ledger_entries",
        ["tenant_id"],
    )
    op.create_index(
        "uq_cap_realphotos_credit_ledger_tenant_event",
        "cap_realphotos_credit_ledger_entries",
        ["tenant_id", "event_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_cap_realphotos_credit_ledger_tenant_created",
        "cap_realphotos_credit_ledger_entries",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "cap_realphotos_execution_jobs",
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("job_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("claimed_by", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_epoch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("dispatch_no", sa.Integer(), server_default="0", nullable=False),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", _JSON, server_default="{}", nullable=False),
        sa.Column("result", _JSON, server_default="{}", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos durable execution jobs",
    )
    op.create_index(
        "ix_cap_realphotos_execution_jobs_tenant_id",
        "cap_realphotos_execution_jobs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_cap_realphotos_execution_jobs_job_kind",
        "cap_realphotos_execution_jobs",
        ["job_kind"],
    )
    op.create_index(
        "ix_cap_realphotos_execution_jobs_status",
        "cap_realphotos_execution_jobs",
        ["status"],
    )
    op.create_index(
        "ix_cap_realphotos_execution_jobs_claim",
        "cap_realphotos_execution_jobs",
        ["status", "available_at", "created_at"],
    )
    op.create_index(
        "ix_cap_realphotos_execution_jobs_tenant_status",
        "cap_realphotos_execution_jobs",
        ["tenant_id", "status"],
    )

    op.create_table(
        "cap_realphotos_outbox",
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", _JSON, server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos outbox events",
    )
    op.create_index(
        "ix_cap_realphotos_outbox_tenant_id",
        "cap_realphotos_outbox",
        ["tenant_id"],
    )
    op.create_index(
        "uq_cap_realphotos_outbox_tenant_event",
        "cap_realphotos_outbox",
        ["tenant_id", "event_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("cap_realphotos_outbox")
    op.drop_table("cap_realphotos_execution_jobs")
    op.drop_table("cap_realphotos_credit_ledger_entries")
    op.drop_table("cap_realphotos_credit_accounts")
    op.drop_table("cap_realphotos_auth_guards")
    op.drop_table("cap_realphotos_auth_challenges")
    op.drop_table("cap_realphotos_merchant_profiles")
