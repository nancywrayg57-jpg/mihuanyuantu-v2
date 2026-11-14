"""Platform Gemini pass-score KV and detection-report snapshot column.

Revision ID: realphotos_0005
Revises: realphotos_0004

Idempotent: safe on DBs that already used create_all.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

from alembic import op

revision: str = "realphotos_0005"
down_revision: str | None = "realphotos_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _has_table(table: str) -> bool:
    return sa_inspect(op.get_bind()).has_table(table)


def _has_column(table: str, column: str) -> bool:
    cols = {str(c["name"]) for c in sa_inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_table("cap_realphotos_platform_settings"):
        op.create_table(
            "cap_realphotos_platform_settings",
            sa.Column("id", _PK, autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("setting_key", sa.String(64), nullable=False),
            sa.Column("setting_value", sa.String(64), nullable=False),
            sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            comment="realphotos platform key-value settings",
        )
        op.create_index(
            "ix_cap_realphotos_platform_settings_tenant_id",
            "cap_realphotos_platform_settings",
            ["tenant_id"],
        )
    if _has_table("cap_realphotos_platform_settings"):
        existing = {i["name"] for i in sa_inspect(op.get_bind()).get_indexes("cap_realphotos_platform_settings")}
        if "uq_cap_realphotos_platform_setting_key" not in existing:
            op.create_index(
                "uq_cap_realphotos_platform_setting_key",
                "cap_realphotos_platform_settings",
                ["setting_key"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
                sqlite_where=sa.text("deleted_at IS NULL"),
            )

    if _has_table("cap_realphotos_detection_results") and not _has_column(
        "cap_realphotos_detection_results", "pass_score_threshold"
    ):
        op.add_column(
            "cap_realphotos_detection_results",
            sa.Column("pass_score_threshold", sa.Integer(), nullable=False, server_default="75"),
        )


def downgrade() -> None:
    # Non-destructive: keep the setting row and historical report snapshots.
    pass
