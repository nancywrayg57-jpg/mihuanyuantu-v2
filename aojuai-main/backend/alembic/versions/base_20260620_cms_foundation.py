"""cms foundation: pages, posts, navigation, site settings, contact submissions

Revision ID: base_20260620_cms_foundation
Revises: base_20260426_merge_speech_and_message_heads
Create Date: 2026-06-20

Creates the tenant-scoped CMS content tables. Menu/permission/content seeding
for existing tenants lives in the companion data migration; fresh installs are
seeded by scripts/seed_data.py.
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "base_20260620_cms_foundation"
down_revision: Union[str, None] = "base_20260426_merge_speech_and_message_heads"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "cms_pages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        *_timestamps(),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("blocks", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("seo", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("sort_order", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_cms_pages_tenant_slug"),
    )
    op.create_index("ix_cms_pages_tenant_id", "cms_pages", ["tenant_id"])
    op.create_index("ix_cms_pages_slug", "cms_pages", ["slug"])

    op.create_table(
        "cms_posts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        *_timestamps(),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("excerpt", sa.String(length=500), nullable=True),
        sa.Column("cover_image", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("seo", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_cms_posts_tenant_slug"),
    )
    op.create_index("ix_cms_posts_tenant_id", "cms_posts", ["tenant_id"])
    op.create_index("ix_cms_posts_slug", "cms_posts", ["slug"])

    op.create_table(
        "cms_navigations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        *_timestamps(),
        sa.Column("location", sa.String(length=20), nullable=False),
        sa.Column("items", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.UniqueConstraint("tenant_id", "location", name="uq_cms_nav_tenant_location"),
    )
    op.create_index("ix_cms_navigations_tenant_id", "cms_navigations", ["tenant_id"])
    op.create_index("ix_cms_navigations_location", "cms_navigations", ["location"])

    op.create_table(
        "cms_site_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        *_timestamps(),
        sa.Column("settings", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_cms_site_settings_tenant"),
    )
    op.create_index("ix_cms_site_settings_tenant_id", "cms_site_settings", ["tenant_id"])

    op.create_table(
        "cms_contact_submissions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        *_timestamps(),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=False),
        sa.Column("company", sa.String(length=160), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_page", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="new", nullable=False),
        sa.Column("meta", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("handled_by", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_cms_contact_tenant_id", "cms_contact_submissions", ["tenant_id"])
    op.create_index("ix_cms_contact_email", "cms_contact_submissions", ["email"])


def downgrade() -> None:
    op.drop_table("cms_contact_submissions")
    op.drop_table("cms_site_settings")
    op.drop_table("cms_navigations")
    op.drop_table("cms_posts")
    op.drop_table("cms_pages")
