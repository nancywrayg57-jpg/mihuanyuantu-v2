"""merge base v2 heads: soft-delete uniqueness + cms menu reconcile

Revision ID: base_20260808_merge_v2_heads
Revises: base_20260808_soft_delete_unique_indexes, base_20260808_cms_menu_reconcile
Create Date: 2026-08-08

两条迁移在同一轮里并行做出来，各自都挂在 base_20260622_cms_languages 上：
一条改 schema（软删除唯一约束改 partial index），一条补数据（老租户的 CMS 菜单与授权）。
它们之间没有依赖关系，所以不改各自的 down_revision（那会破坏"迁移不可事后改写"的约束，
也会打破断言快照来源的契约测试），按本仓既有做法用 merge revision 收回单 head。
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "base_20260808_merge_v2_heads"
down_revision: tuple[str, ...] = (
    "base_20260808_soft_delete_unique_indexes",
    "base_20260808_cms_menu_reconcile",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge-only revision: no schema or data change."""


def downgrade() -> None:
    """Merge-only revision: no schema or data change."""
