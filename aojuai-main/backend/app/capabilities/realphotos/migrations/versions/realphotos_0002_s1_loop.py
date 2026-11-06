"""S1 single-image loop tables.

Revision ID: realphotos_0002
Revises: realphotos_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "realphotos_0002"
down_revision: str | None = "realphotos_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _tenant_pk() -> list[sa.Column]:
    return [
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
    ]


def _times() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _tenant_index(table: str) -> None:
    op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def upgrade() -> None:
    op.create_table(
        "cap_realphotos_assets",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("origin_kind", sa.String(length=32), nullable=False, server_default="local_upload"),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos source assets",
    )
    _tenant_index("cap_realphotos_assets")
    op.create_index(
        "ix_cap_realphotos_assets_tenant_owner",
        "cap_realphotos_assets",
        ["tenant_id", "owner_account_id"],
    )

    op.create_table(
        "cap_realphotos_batches",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("image_count", sa.Integer(), nullable=False),
        sa.Column("preset_code", sa.String(length=64), nullable=False),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos processing batches",
    )
    _tenant_index("cap_realphotos_batches")

    op.create_table(
        "cap_realphotos_task_chains",
        *_tenant_pk(),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("round_no", sa.Integer(), server_default="1", nullable=False),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos task chains",
    )
    _tenant_index("cap_realphotos_task_chains")

    op.create_table(
        "cap_realphotos_image_tasks",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("preset_code", sa.String(length=64), nullable=False),
        sa.Column("preset_snapshot", _JSON, server_default="{}", nullable=False),
        sa.Column("pre_review_mode", sa.String(length=16), nullable=False, server_default="pass"),
        sa.Column("detection_mode", sa.String(length=16), nullable=False, server_default="pass"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("output_object_key", sa.String(length=255), nullable=True),
        sa.Column("output_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("output_byte_size", sa.BigInteger(), nullable=True),
        sa.Column("failure_class", sa.String(length=32), nullable=True),
        sa.Column("credit_disposition", sa.String(length=64), nullable=True),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False, server_default="stub-s1"),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos image processing tasks",
    )
    _tenant_index("cap_realphotos_image_tasks")
    op.create_index(
        "uq_cap_realphotos_image_tasks_idem",
        "cap_realphotos_image_tasks",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_cap_realphotos_image_tasks_asset",
        "cap_realphotos_image_tasks",
        ["tenant_id", "asset_id", "status"],
    )

    op.create_table(
        "cap_realphotos_task_snapshots",
        *_tenant_pk(),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot", _JSON, server_default="{}", nullable=False),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos preset snapshots",
    )
    _tenant_index("cap_realphotos_task_snapshots")
    op.create_index("ix_cap_realphotos_task_snapshots_task_id", "cap_realphotos_task_snapshots", ["task_id"])

    op.create_table(
        "cap_realphotos_stage_results",
        *_tenant_pk(),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("stage_code", sa.String(length=8), nullable=False),
        sa.Column("stage_status", sa.String(length=32), nullable=False),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos placeholder stage results",
    )
    _tenant_index("cap_realphotos_stage_results")
    op.create_index("ix_cap_realphotos_stage_results_task_id", "cap_realphotos_stage_results", ["task_id"])

    op.create_table(
        "cap_realphotos_detection_results",
        *_tenant_pk(),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("noise", sa.Integer(), nullable=False),
        sa.Column("depth_of_field", sa.Integer(), nullable=False),
        sa.Column("lighting", sa.Integer(), nullable=False),
        sa.Column("color_realism", sa.Integer(), nullable=False),
        sa.Column("overall_realism", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("detector", sa.String(length=32), nullable=False, server_default="fixture"),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos fixture detection results",
    )
    _tenant_index("cap_realphotos_detection_results")
    op.create_index(
        "ix_cap_realphotos_detection_results_task_id",
        "cap_realphotos_detection_results",
        ["task_id"],
    )

    op.create_table(
        "cap_realphotos_credit_reservations",
        *_tenant_pk(),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("operator_user_id", sa.BigInteger(), nullable=False),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos credit reservations",
    )
    _tenant_index("cap_realphotos_credit_reservations")
    op.create_index(
        "ix_cap_realphotos_credit_reservations_task_id",
        "cap_realphotos_credit_reservations",
        ["task_id"],
    )

    op.create_table(
        "cap_realphotos_recharge_orders",
        *_tenant_pk(),
        sa.Column("requester_user_id", sa.BigInteger(), nullable=False),
        sa.Column("tier_yuan", sa.Integer(), nullable=False),
        sa.Column("credit_points", sa.BigInteger(), nullable=False),
        sa.Column("price_formula", sa.String(length=80), nullable=False),
        sa.Column("voucher_note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("confirmed_by_user_id", sa.BigInteger(), nullable=True),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos manual recharge orders",
    )
    _tenant_index("cap_realphotos_recharge_orders")
    op.create_index(
        "uq_cap_realphotos_recharge_idem",
        "cap_realphotos_recharge_orders",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "cap_realphotos_inbox_messages",
        *_tenant_pk(),
        sa.Column("recipient_user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        *_times(),
        sa.PrimaryKeyConstraint("id"),
        comment="realphotos inbox messages",
    )
    _tenant_index("cap_realphotos_inbox_messages")
    op.create_index(
        "ix_cap_realphotos_inbox_messages_recipient_user_id",
        "cap_realphotos_inbox_messages",
        ["recipient_user_id"],
    )
    op.create_index(
        "uq_cap_realphotos_inbox_event",
        "cap_realphotos_inbox_messages",
        ["tenant_id", "event_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("cap_realphotos_inbox_messages")
    op.drop_table("cap_realphotos_recharge_orders")
    op.drop_table("cap_realphotos_credit_reservations")
    op.drop_table("cap_realphotos_detection_results")
    op.drop_table("cap_realphotos_stage_results")
    op.drop_table("cap_realphotos_task_snapshots")
    op.drop_table("cap_realphotos_image_tasks")
    op.drop_table("cap_realphotos_task_chains")
    op.drop_table("cap_realphotos_batches")
    op.drop_table("cap_realphotos_assets")
