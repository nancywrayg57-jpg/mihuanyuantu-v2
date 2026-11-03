"""compat placeholder: product menu ordering

Revision ID: 0031_product_menu_ordering
Revises: 0001_initial_schema
Create Date: 2026-02-14

说明：
- nextjs-base 分支不承载 product 完整菜单迁移链。
- 该占位迁移仅用于补齐 alembic 图，供 0032_merge_product_heads 引用。
"""

from __future__ import annotations

from typing import Sequence, Union


revision: str = "0031_product_menu_ordering"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
