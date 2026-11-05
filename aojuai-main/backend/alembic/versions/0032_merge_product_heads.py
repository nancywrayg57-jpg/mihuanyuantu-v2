"""merge product heads after tenant-settings unify

Revision ID: 0032_merge_product_heads
Revises: 0031_product_menu_ordering, 0011_tenant_settings_tab_unify, 0006_assistant_config_add_enabled_column
Create Date: 2026-02-10

说明：
- 近期迁移演进后出现多个 head（主链 + tenant-settings 分支 + assistant 分支）。
- 为保证 `alembic upgrade head` 在标准流程中可用，需将当前 heads 合并为单一 head。
- 本迁移仅用于图合并，不做 schema/data 变更。
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0032_merge_product_heads"
down_revision: str | tuple[str, str, str] | None = (
    "0031_product_menu_ordering",
    "0011_tenant_settings_tab_unify",
    "0006_assistant_config_add_enabled_column",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Merge revision: no-op
    pass


def downgrade() -> None:
    # Merge revision: no-op
    pass
