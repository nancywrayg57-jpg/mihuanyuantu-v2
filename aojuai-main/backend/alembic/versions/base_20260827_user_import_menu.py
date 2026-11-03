"""add system user-import page menu for existing tenants

Revision ID: base_20260827_user_import_menu
Revises: base_20260827_personal_channels_menu

菜单三写之三：seed（新装）与 core/system_menus（新租户）已声明 `/system/user-import`，
这里补存量租户：在 `/system` 根下插入页面，并授给所有已拥有「用户管理」页的角色。
"""

from __future__ import annotations

from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "base_20260827_user_import_menu"
down_revision: Union[str, None] = "base_20260827_personal_channels_menu"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PAGE = {
    "title": "批量导入用户",
    "path": "/system/user-import",
    "component": "views/system/user-import/index",
    "icon": "ep:upload",
    "sort_order": 10,
    "perms": "user:create",
}


def _scalar(conn: sa.Connection, sql: str, params: dict[str, Any]) -> Any:
    return conn.execute(sa.text(sql), params).scalar()


def upgrade() -> None:
    conn = op.get_bind()
    if not sa.inspect(conn).has_table("menus"):
        return
    tenant_ids = [int(r[0]) for r in conn.execute(sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id")).all()]
    for tenant_id in tenant_ids:
        root_id = _scalar(
            conn,
            "SELECT id FROM menus WHERE tenant_id = :t AND deleted_at IS NULL AND path = '/system' ORDER BY id LIMIT 1",
            {"t": tenant_id},
        )
        if root_id is None:
            continue
        page_id = _scalar(
            conn,
            "SELECT id FROM menus WHERE tenant_id = :t AND deleted_at IS NULL AND path = :path ORDER BY id LIMIT 1",
            {"t": tenant_id, "path": PAGE["path"]},
        )
        if page_id is None:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO menus (
                      tenant_id, title, path, component, parent_id, level, icon, sort_order, menu_type, perms,
                      is_visible, is_cache, is_frame, is_active, no_cache, created_at
                    ) VALUES (
                      :t, :title, :path, :component, :parent_id, 2, :icon, :sort_order, '1', :perms,
                      true, false, false, true, false, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"t": tenant_id, "parent_id": int(root_id), **PAGE},
            )
            page_id = _scalar(
                conn,
                "SELECT id FROM menus WHERE tenant_id = :t AND deleted_at IS NULL AND path = :path ORDER BY id LIMIT 1",
                {"t": tenant_id, "path": PAGE["path"]},
            )
        # 授权：拥有「用户管理」页（/system/user）的角色同样拿到导入页；API 本身仍由 user:create 把守
        conn.execute(
            sa.text(
                """
                INSERT INTO role_menus (tenant_id, role_id, menu_id)
                SELECT rm.tenant_id, rm.role_id, :page_id
                FROM role_menus rm
                JOIN menus m ON m.id = rm.menu_id
                WHERE rm.tenant_id = :t AND m.deleted_at IS NULL AND m.path = '/system/user'
                  AND NOT EXISTS (
                    SELECT 1 FROM role_menus x WHERE x.role_id = rm.role_id AND x.menu_id = :page_id
                  )
                """
            ),
            {"t": tenant_id, "page_id": int(page_id)},
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not sa.inspect(conn).has_table("menus"):
        return
    conn.execute(
        sa.text(
            "DELETE FROM role_menus WHERE menu_id IN (SELECT id FROM menus WHERE path = :path)"
        ),
        {"path": PAGE["path"]},
    )
    conn.execute(sa.text("DELETE FROM menus WHERE path = :path"), {"path": PAGE["path"]})
