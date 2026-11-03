"""credit_price_items 增加 cache_write_points_per_1k（缓存写入价，NULL=按输入价）

Revision ID: base_20260827_credit_price_cache_write
Revises: base_20260827_credits_pricing_mode_perm
Create Date: 2026-08-26

计量层已把缓存拆成命中/写入两段（Anthropic cache_creation、网关 input_tokens_details.cache_write_tokens），
费率项需要能为写入单独定价；缺省 NULL 按输入价计，与 pricing.PriceItem.effective_cache_write_per_1k 一致。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "base_20260827_credit_price_cache_write"
down_revision: str | Sequence[str] | None = "base_20260827_credits_pricing_mode_perm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "credit_price_items"
COLUMN = "cache_write_points_per_1k"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE in set(inspector.get_table_names()) and COLUMN not in {c["name"] for c in inspector.get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(COLUMN, sa.Numeric(18, 6), nullable=True, comment="缓存写入价；NULL=按输入价"))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE in set(inspector.get_table_names()) and COLUMN in {c["name"] for c in inspector.get_columns(TABLE)}:
        op.drop_column(TABLE, COLUMN)
