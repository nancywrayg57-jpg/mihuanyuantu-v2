"""S3/S5/S6 + asset/task column gaps (AUDIT-REMAIN B1).

Revision ID: realphotos_0004
Revises: realphotos_0003

Idempotent: safe on DBs that already used create_all / partial ensures.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "realphotos_0004"
down_revision: str | None = "realphotos_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _has_table(table: str) -> bool:
    return sa_inspect(op.get_bind()).has_table(table)


def _has_column(table: str, column: str) -> bool:
    cols = {str(c["name"]) for c in sa_inspect(op.get_bind()).get_columns(table)}
    return column in cols


def _times() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _tenant_pk() -> list[sa.Column]:
    return [
        sa.Column("id", _PK, autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
    ]


def _create(table: str, *columns: sa.Column, comment: str) -> None:
    if _has_table(table):
        return
    op.create_table(table, *columns, sa.PrimaryKeyConstraint("id"), comment=comment)
    op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def upgrade() -> None:
    # --- column gaps on existing S1 tables ---
    if _has_table("cap_realphotos_assets"):
        for name, col in [
            ("meta_name", sa.Column("meta_name", sa.String(255), nullable=True)),
            ("meta_seller", sa.Column("meta_seller", sa.String(255), nullable=True)),
            ("meta_sku", sa.Column("meta_sku", sa.String(128), nullable=True)),
            ("meta_asn", sa.Column("meta_asn", sa.String(128), nullable=True)),
            ("meta_price", sa.Column("meta_price", sa.String(64), nullable=True)),
            ("meta_website", sa.Column("meta_website", sa.String(255), nullable=True)),
            ("meta_url", sa.Column("meta_url", sa.String(512), nullable=True)),
            ("requested_width", sa.Column("requested_width", sa.Integer(), nullable=True)),
            ("requested_height", sa.Column("requested_height", sa.Integer(), nullable=True)),
        ]:
            if not _has_column("cap_realphotos_assets", name):
                op.add_column("cap_realphotos_assets", col)

    if _has_table("cap_realphotos_image_tasks"):
        if not _has_column("cap_realphotos_image_tasks", "copied_from_task_id"):
            op.add_column(
                "cap_realphotos_image_tasks",
                sa.Column("copied_from_task_id", sa.BigInteger(), nullable=True),
            )
        if not _has_column("cap_realphotos_image_tasks", "billing_mode"):
            op.add_column(
                "cap_realphotos_image_tasks",
                sa.Column("billing_mode", sa.String(32), server_default="normal", nullable=False),
            )

    # --- S3 ---
    _create(
        "cap_realphotos_redo_settings",
        *_tenant_pk(),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("score_threshold", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("extra_rounds", sa.Integer(), nullable=False, server_default="1"),
        *_times(),
        comment="realphotos auto redo settings",
    )
    if _has_table("cap_realphotos_redo_settings"):
        # unique index may already exist from create_all
        bind = op.get_bind()
        existing = {i["name"] for i in sa_inspect(bind).get_indexes("cap_realphotos_redo_settings")}
        if "uq_cap_realphotos_redo_tenant" not in existing:
            op.create_index(
                "uq_cap_realphotos_redo_tenant",
                "cap_realphotos_redo_settings",
                ["tenant_id"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
                sqlite_where=sa.text("deleted_at IS NULL"),
            )

    _create(
        "cap_realphotos_chain_policies",
        *_tenant_pk(),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("score_threshold", sa.Integer(), nullable=False),
        sa.Column("extra_rounds", sa.Integer(), nullable=False),
        sa.Column("execution_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_task_id", sa.BigInteger(), nullable=True),
        sa.Column("origin", sa.String(32), nullable=False, server_default="submit"),
        *_times(),
        comment="realphotos chain redo snapshots",
    )
    if _has_table("cap_realphotos_chain_policies"):
        idxs = {i["name"] for i in sa_inspect(op.get_bind()).get_indexes("cap_realphotos_chain_policies")}
        if "ix_cap_realphotos_chain_policies_chain_id" not in idxs:
            op.create_index(
                "ix_cap_realphotos_chain_policies_chain_id",
                "cap_realphotos_chain_policies",
                ["chain_id"],
            )

    # --- S5 ---
    _create(
        "cap_realphotos_generation_tasks",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("positive_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("template_id", sa.BigInteger(), nullable=True),
        sa.Column("requested_seed", sa.String(64), nullable=True),
        sa.Column("supplier_trace", _JSON, nullable=False, server_default="{}"),
        *_times(),
        comment="realphotos generation tasks",
    )
    if _has_table("cap_realphotos_generation_tasks"):
        idxs = {i["name"] for i in sa_inspect(op.get_bind()).get_indexes("cap_realphotos_generation_tasks")}
        if "uq_cap_realphotos_generation_idem" not in idxs:
            op.create_index(
                "uq_cap_realphotos_generation_idem",
                "cap_realphotos_generation_tasks",
                ["tenant_id", "idempotency_key"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
                sqlite_where=sa.text("deleted_at IS NULL"),
            )

    _create(
        "cap_realphotos_generation_items",
        *_tenant_pk(),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=True),
        sa.Column("credits_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_width", sa.Integer(), nullable=True),
        sa.Column("actual_height", sa.Integer(), nullable=True),
        *_times(),
        comment="realphotos generation items",
    )

    _create(
        "cap_realphotos_prompt_templates",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("positive_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("scope", sa.String(16), nullable=False),
        *_times(),
        comment="realphotos prompt templates",
    )

    _create(
        "cap_realphotos_prompt_optimizations",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("optimized_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("provider", sa.String(32), nullable=False),
        *_times(),
        comment="realphotos prompt optimizations",
    )

    _create(
        "cap_realphotos_provider_contracts",
        *_tenant_pk(),
        sa.Column("duty", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("config_version", sa.String(32), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("credential_ref", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(200), nullable=False),
        sa.Column("capabilities", _JSON, nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("gap_note", sa.Text(), nullable=False, server_default=""),
        *_times(),
        comment="realphotos supplier contracts without secrets",
    )
    if _has_table("cap_realphotos_provider_contracts"):
        idxs = {i["name"] for i in sa_inspect(op.get_bind()).get_indexes("cap_realphotos_provider_contracts")}
        if "uq_cap_realphotos_provider_duty" not in idxs:
            op.create_index(
                "uq_cap_realphotos_provider_duty",
                "cap_realphotos_provider_contracts",
                ["duty"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
                sqlite_where=sa.text("deleted_at IS NULL"),
            )

    _create(
        "cap_realphotos_provider_usage",
        *_tenant_pk(),
        sa.Column("duty", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("config_version", sa.String(32), nullable=False, server_default=""),
        sa.Column("trace_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("request_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("units", sa.Numeric(18, 6), nullable=False, server_default="1"),
        sa.Column("unit_name", sa.String(32), nullable=False, server_default="call"),
        sa.Column("unit_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("amount", sa.Numeric(18, 8), nullable=True),
        sa.Column("cost_status", sa.String(16), nullable=False, server_default="unavailable"),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        *_times(),
        comment="realphotos upstream usage/cost ledger",
    )
    if _has_table("cap_realphotos_provider_usage"):
        idxs = {i["name"] for i in sa_inspect(op.get_bind()).get_indexes("cap_realphotos_provider_usage")}
        if "ix_cap_realphotos_provider_usage_duty_created" not in idxs:
            op.create_index(
                "ix_cap_realphotos_provider_usage_duty_created",
                "cap_realphotos_provider_usage",
                ["duty", "created_at"],
            )

    # --- S6 ---
    _create(
        "cap_realphotos_content_reviews",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("subject", sa.String(16), nullable=False),
        sa.Column("image_identity", sa.String(64), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("counts_for_streak", sa.Boolean(), nullable=False, server_default="false"),
        *_times(),
        comment="realphotos content review audit",
    )

    _create(
        "cap_realphotos_image_locks",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("image_identity", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        *_times(),
        comment="realphotos locked image identities",
    )
    if _has_table("cap_realphotos_image_locks"):
        idxs = {i["name"] for i in sa_inspect(op.get_bind()).get_indexes("cap_realphotos_image_locks")}
        if "uq_cap_realphotos_image_lock" not in idxs:
            op.create_index(
                "uq_cap_realphotos_image_lock",
                "cap_realphotos_image_locks",
                ["tenant_id", "owner_account_id", "image_identity"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
                sqlite_where=sa.text("deleted_at IS NULL"),
            )

    _create(
        "cap_realphotos_review_streaks",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("identities", _JSON, nullable=False, server_default="[]"),
        *_times(),
        comment="consecutive distinct content-review failures",
    )
    if _has_table("cap_realphotos_review_streaks"):
        idxs = {i["name"] for i in sa_inspect(op.get_bind()).get_indexes("cap_realphotos_review_streaks")}
        if "uq_cap_realphotos_review_streak_user" not in idxs:
            op.create_index(
                "uq_cap_realphotos_review_streak_user",
                "cap_realphotos_review_streaks",
                ["tenant_id", "owner_account_id"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
                sqlite_where=sa.text("deleted_at IS NULL"),
            )

    _create(
        "cap_realphotos_support_tickets",
        *_tenant_pk(),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolution_outcome", sa.String(32), nullable=False, server_default=""),
        *_times(),
        comment="realphotos tech-support tickets",
    )

    _create(
        "cap_realphotos_account_logs",
        *_tenant_pk(),
        sa.Column("operator_user_id", sa.BigInteger(), nullable=False),
        sa.Column("target_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("before_state", _JSON, nullable=False, server_default="{}"),
        sa.Column("after_state", _JSON, nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("result", sa.String(16), nullable=False, server_default="success"),
        *_times(),
        comment="realphotos account change log",
    )

    _create(
        "cap_realphotos_device_presets",
        *_tenant_pk(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("device_type", sa.String(32), nullable=False),
        sa.Column("brand", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("iso", sa.String(32), nullable=False, server_default=""),
        sa.Column("shutter", sa.String(32), nullable=False, server_default=""),
        sa.Column("aperture", sa.String(32), nullable=False, server_default=""),
        sa.Column("focal_length", sa.String(32), nullable=False, server_default=""),
        sa.Column("gps_mode", sa.String(32), nullable=False, server_default="none"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(16), nullable=False, server_default="admin"),
        sa.Column("ai_positive_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("ai_negative_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("maker_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("legacy_source_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("legacy_template_ref", sa.String(120), nullable=False, server_default=""),
        sa.Column("legacy_visibility", sa.String(32), nullable=False, server_default=""),
        sa.Column("legacy_review_bucket", sa.String(64), nullable=False, server_default=""),
        *_times(),
        comment="realphotos device preset overrides and admin presets",
    )
    if _has_table("cap_realphotos_device_presets"):
        idxs = {i["name"] for i in sa_inspect(op.get_bind()).get_indexes("cap_realphotos_device_presets")}
        if "uq_cap_realphotos_device_preset_code" not in idxs:
            op.create_index(
                "uq_cap_realphotos_device_preset_code",
                "cap_realphotos_device_presets",
                ["code"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
                sqlite_where=sa.text("deleted_at IS NULL"),
            )

    _create(
        "cap_realphotos_preset_versions",
        *_tenant_pk(),
        sa.Column("preset_code", sa.String(64), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("snapshot", _JSON, nullable=False, server_default="{}"),
        *_times(),
        comment="preset version snapshots",
    )

    # B2 companion: clear legacy merchant copy_latch mirror values (columns kept for history).
    if _has_table("cap_realphotos_merchant_profiles") and _has_column(
        "cap_realphotos_merchant_profiles", "copy_latch_active"
    ):
        op.execute(
            sa.text(
                "UPDATE cap_realphotos_merchant_profiles "
                "SET copy_latch_active = false, copy_latch_batch_id = NULL "
                "WHERE COALESCE(copy_latch_active, false) = true"
            )
        )


def downgrade() -> None:
    # Non-destructive downgrade: keep tables (may hold production-like data on shared DBs).
    pass
