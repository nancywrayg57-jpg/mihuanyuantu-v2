"""cms language taxonomy + migrate 'default' content to real default language

Revision ID: base_20260622_cms_languages
Revises: base_20260622_cms_ai_config
Create Date: 2026-06-22

Introduces a first-class per-tenant language registry (cms_languages) and
migrates legacy content stored under the placeholder locale 'default' to the
real default language code (zh-CN). After this, every content row is keyed by a
genuine language code; there is no magic 'default' value.
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "base_20260622_cms_languages"
down_revision: Union[str, None] = "base_20260622_cms_ai_config"
branch_labels = None
depends_on = None

DEFAULT_CODE = "zh-CN"
SEED = [("zh-CN", "简体中文", True, 0), ("en-US", "English", False, 1)]


def upgrade() -> None:
    op.create_table(
        "cms_languages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_cms_languages_tenant_code"),
    )
    op.create_index("ix_cms_languages_tenant_id", "cms_languages", ["tenant_id"])

    bind = op.get_bind()
    # Migrate legacy 'default' content to the real default language.
    bind.execute(sa.text("UPDATE cms_pages SET locale=:c WHERE locale='default'"), {"c": DEFAULT_CODE})
    bind.execute(sa.text("UPDATE cms_posts SET locale=:c WHERE locale='default'"), {"c": DEFAULT_CODE})

    # Seed the language registry for every existing tenant (idempotent).
    tenants = bind.execute(sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL")).scalars().all()
    for tid in tenants:
        for code, name, is_default, sort_order in SEED:
            exists = bind.execute(
                sa.text("SELECT 1 FROM cms_languages WHERE tenant_id=:t AND code=:c"),
                {"t": tid, "c": code},
            ).scalar()
            if exists:
                continue
            bind.execute(
                sa.text(
                    "INSERT INTO cms_languages (tenant_id, code, name, is_default, is_active, sort_order) "
                    "VALUES (:t, :c, :n, :d, true, :s)"
                ),
                {"t": tid, "c": code, "n": name, "d": is_default, "s": sort_order},
            )


def downgrade() -> None:
    op.drop_table("cms_languages")
