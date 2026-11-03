"""cms ai config: per-tenant content-management AI override

Revision ID: base_20260622_cms_ai_config
Revises: base_20260622_cms_locale
Create Date: 2026-06-22

Adds an `ai_config` JSONB column to cms_site_settings. This is intentionally a
SEPARATE column from the publicly-served `settings` blob so the (encrypted) API
key is never exposed on the public site endpoint.
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "base_20260622_cms_ai_config"
down_revision: Union[str, None] = "base_20260622_cms_locale"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cms_site_settings",
        sa.Column("ai_config", postgresql.JSONB(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("cms_site_settings", "ai_config")
