"""credit_price_items：租户级积分费率覆盖表（平台默认价来自代码内版本化 pricebook）

Revision ID: base_20260827_credit_price_items
Revises: base_20260827_wecom_channel_unique_index
Create Date: 2026-08-26

方案：devdocs/plans/UNIFIED_CREDIT_PRICING_PLAN_20260826.md §4.2（codex 评审后修订）。
- 平台默认费率不落库：随代码发布的 credits/default_price_items.json（内容 SHA 即 priceVersion）。
- 本表只存租户覆盖差异项，tenant_id 非空，走 TenantBaseModel 隔离约束。
- 只按模型名/件名匹配（glob），不做模型目录、不做授权、不存凭据。
- 不删除 credit_rules：先移除代码引用，确认生产无数据并备份后，隔一个版本再 drop。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "base_20260827_credit_price_items"
down_revision: str | Sequence[str] | None = "base_20260827_wecom_channel_unique_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "credit_price_items"
def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if TABLE not in tables:
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户覆盖项所属租户"),
            sa.Column("item_type", sa.String(length=20), nullable=False, comment="llm/image/tool_call/tts/asr/flat"),
            sa.Column("match_key", sa.String(length=200), nullable=False, comment="模型名或 glob；image 模型[/size/quality]；tool 键[@模型]"),
            sa.Column("input_points_per_1k", sa.Numeric(18, 6), nullable=False, server_default="0"),
            sa.Column("output_points_per_1k", sa.Numeric(18, 6), nullable=False, server_default="0"),
            sa.Column("cached_points_per_1k", sa.Numeric(18, 6), nullable=True, comment="NULL=输入价×10%"),
            sa.Column("points_per_unit", sa.Numeric(18, 6), nullable=False, server_default="0"),
            sa.Column("unit_divisor", sa.Numeric(18, 6), nullable=True, comment="tts 默认 1000 字符、asr 默认 60 秒"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("remark", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("extra", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_credit_price_items_tenant_id", TABLE, ["tenant_id"])
        op.create_index("ix_credit_price_items_type", TABLE, ["item_type"])
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_price_items_scope_key "
                f"ON {TABLE} (tenant_id, item_type, match_key) WHERE deleted_at IS NULL"
            )
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE in set(inspector.get_table_names()):
        op.drop_table(TABLE)
