"""make business uniqueness soft-delete aware

Revision ID: base_20260808_soft_delete_unique_indexes
Revises: base_20260622_cms_languages
Create Date: 2026-08-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "base_20260808_soft_delete_unique_indexes"
down_revision: str | None = "base_20260622_cms_languages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_active_index(name: str, table: str, columns: list[str]) -> None:
    op.create_index(
        name,
        table,
        columns,
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def upgrade() -> None:
    op.drop_index("ix_tenants_code", table_name="tenants")
    _create_active_index("ix_tenants_code", "tenants", ["code"])

    op.drop_constraint("uq_invite_codes_code", "invite_codes", type_="unique")
    _create_active_index("uq_invite_codes_code", "invite_codes", ["code"])

    op.drop_constraint(
        "uq_invite_registrations_invited_user_id",
        "invite_registrations",
        type_="unique",
    )
    _create_active_index(
        "uq_invite_registrations_invited_user_id",
        "invite_registrations",
        ["invited_user_id"],
    )

    for table, name, columns in (
        ("cms_pages", "uq_cms_pages_tenant_slug_locale", ["tenant_id", "slug", "locale"]),
        ("cms_posts", "uq_cms_posts_tenant_slug_locale", ["tenant_id", "slug", "locale"]),
        ("cms_navigations", "uq_cms_nav_tenant_location", ["tenant_id", "location"]),
        ("cms_site_settings", "uq_cms_site_settings_tenant", ["tenant_id"]),
        ("cms_languages", "uq_cms_languages_tenant_code", ["tenant_id", "code"]),
    ):
        op.drop_constraint(name, table, type_="unique")
        _create_active_index(name, table, columns)


def downgrade() -> None:
    for table, name, columns in (
        ("cms_languages", "uq_cms_languages_tenant_code", ["tenant_id", "code"]),
        ("cms_site_settings", "uq_cms_site_settings_tenant", ["tenant_id"]),
        ("cms_navigations", "uq_cms_nav_tenant_location", ["tenant_id", "location"]),
        ("cms_posts", "uq_cms_posts_tenant_slug_locale", ["tenant_id", "slug", "locale"]),
        ("cms_pages", "uq_cms_pages_tenant_slug_locale", ["tenant_id", "slug", "locale"]),
    ):
        op.drop_index(name, table_name=table)
        op.create_unique_constraint(name, table, columns)

    op.drop_index("uq_invite_registrations_invited_user_id", table_name="invite_registrations")
    op.create_unique_constraint(
        "uq_invite_registrations_invited_user_id",
        "invite_registrations",
        ["invited_user_id"],
    )

    op.drop_index("uq_invite_codes_code", table_name="invite_codes")
    op.create_unique_constraint("uq_invite_codes_code", "invite_codes", ["code"])

    op.drop_index("ix_tenants_code", table_name="tenants")
    op.create_index("ix_tenants_code", "tenants", ["code"], unique=True)
