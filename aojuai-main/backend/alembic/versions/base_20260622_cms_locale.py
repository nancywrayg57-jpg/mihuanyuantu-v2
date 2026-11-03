"""cms multi-language: add locale to pages and posts

Revision ID: base_20260622_cms_locale
Revises: base_20260620_cms_foundation
Create Date: 2026-06-22

Adds a `locale` column so the same slug can have per-language content. The
unique key becomes (tenant_id, slug, locale). Existing rows default to 'default'.
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "base_20260622_cms_locale"
down_revision: Union[str, None] = "base_20260620_cms_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, uq in (("cms_pages", "uq_cms_pages_tenant_slug"), ("cms_posts", "uq_cms_posts_tenant_slug")):
        op.add_column(
            table,
            sa.Column("locale", sa.String(length=12), nullable=False, server_default="default"),
        )
        op.drop_constraint(uq, table, type_="unique")
        op.create_unique_constraint(uq.replace("_slug", "_slug_locale"), table, ["tenant_id", "slug", "locale"])
        op.create_index(f"ix_{table}_locale", table, ["locale"])


def downgrade() -> None:
    for table, uq in (("cms_pages", "uq_cms_pages_tenant_slug"), ("cms_posts", "uq_cms_posts_tenant_slug")):
        op.drop_index(f"ix_{table}_locale", table)
        op.drop_constraint(uq.replace("_slug", "_slug_locale"), table, type_="unique")
        op.create_unique_constraint(uq, table, ["tenant_id", "slug"])
        op.drop_column(table, "locale")
