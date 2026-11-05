"""add personal message channels menu

Revision ID: base_20260827_personal_channels_menu
Revises: base_20260827_api_keys
Create Date: 2026-05-05
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "base_20260827_personal_channels_menu"
down_revision: str | None = "base_20260827_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sql(statement: str) -> str:
    """双方言：SQLite 的 JSON 列就是 TEXT、时间用 CURRENT_TIMESTAMP；PG 保持原样。"""
    if op.get_bind().dialect.name == "sqlite":
        return statement.replace("CAST(:meta AS jsonb)", ":meta").replace("now()", "CURRENT_TIMESTAMP")
    return statement


def _fetch_scalar(conn: sa.Connection, sql: str, params: dict[str, Any] | None = None) -> Any:
    return conn.execute(sa.text(sql), params or {}).scalar()


def _ensure_personal_root(conn: sa.Connection, tenant_id: int) -> int:
    existing_id = _fetch_scalar(
        conn,
        """
        SELECT id
        FROM menus
        WHERE tenant_id = :tenant_id
          AND deleted_at IS NULL
          AND path = '/personal'
        ORDER BY id
        LIMIT 1
        """,
        {"tenant_id": tenant_id},
    )
    if existing_id is not None:
        return int(existing_id)
    return int(
        conn.execute(
            sa.text(
                _sql("""
                INSERT INTO menus (
                    tenant_id, title, path, component, parent_id, level, icon,
                    sort_order, menu_type, perms, is_visible, is_cache, is_frame,
                    is_active, no_cache, breadcrumb, affix, no_tags_view, can_to,
                    always_show, meta, created_at
                )
                VALUES (
                    :tenant_id, '个人中心', '/personal', NULL, NULL, 1, 'ep:user',
                    1, '0', NULL, true, false, false,
                    true, false, true, false, false, false,
                    true, CAST(:meta AS jsonb), now()
                )
                RETURNING id
                """)
            ),
            {"tenant_id": tenant_id, "meta": json.dumps({"devBaseLayer": "personal"}, ensure_ascii=False)},
        ).scalar_one()
    )


def _ensure_channels_menu(conn: sa.Connection, *, tenant_id: int, personal_id: int) -> int:
    conn.execute(
        sa.text(
            _sql("""
            UPDATE menus
            SET sort_order = CASE path
                  WHEN '/personal/scheduled-jobs' THEN 4
                  WHEN '/personal/logs' THEN 5
                  ELSE sort_order
                END,
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND parent_id = :personal_id
              AND deleted_at IS NULL
              AND path IN ('/personal/scheduled-jobs', '/personal/logs')
            """)
        ),
        {"tenant_id": tenant_id, "personal_id": personal_id},
    )
    existing_id = _fetch_scalar(
        conn,
        """
        SELECT id
        FROM menus
        WHERE tenant_id = :tenant_id
          AND deleted_at IS NULL
          AND path = '/personal/channels'
        ORDER BY id
        LIMIT 1
        """,
        {"tenant_id": tenant_id},
    )
    params = {
        "tenant_id": tenant_id,
        "title": "消息 Channel",
        "path": "/personal/channels",
        "component": "views/personal/channels/index",
        "parent_id": personal_id,
        "level": 2,
        "icon": "ep:connection",
        "sort_order": 3,
        "meta": json.dumps({"devBaseLayer": "personal"}, ensure_ascii=False),
    }
    if existing_id is not None:
        menu_id = int(existing_id)
        conn.execute(
            sa.text(
                _sql("""
                UPDATE menus
                SET title = :title,
                    component = :component,
                    parent_id = :parent_id,
                    level = :level,
                    icon = :icon,
                    sort_order = :sort_order,
                    menu_type = '1',
                    perms = NULL,
                    is_visible = true,
                    is_active = true,
                    always_show = false,
                    meta = CAST(:meta AS jsonb),
                    updated_at = now()
                WHERE id = :menu_id
                """)
            ),
            {**params, "menu_id": menu_id},
        )
        return menu_id
    return int(
        conn.execute(
            sa.text(
                _sql("""
                INSERT INTO menus (
                    tenant_id, title, path, component, parent_id, level, icon,
                    sort_order, menu_type, perms, is_visible, is_cache, is_frame,
                    is_active, no_cache, breadcrumb, affix, no_tags_view, can_to,
                    always_show, meta, created_at
                )
                VALUES (
                    :tenant_id, :title, :path, :component, :parent_id, :level, :icon,
                    :sort_order, '1', NULL, true, false, false,
                    true, false, true, false, false, false,
                    false, CAST(:meta AS jsonb), now()
                )
                RETURNING id
                """)
            ),
            params,
        ).scalar_one()
    )


def _grant_role_menu(conn: sa.Connection, *, tenant_id: int, role_id: int, menu_id: int) -> None:
    conn.execute(
        sa.text(
            _sql("""
            INSERT INTO role_menus (tenant_id, role_id, menu_id)
            VALUES (:tenant_id, :role_id, :menu_id)
            ON CONFLICT (role_id, menu_id) DO NOTHING
            """)
        ),
        {"tenant_id": tenant_id, "role_id": role_id, "menu_id": menu_id},
    )


def upgrade() -> None:
    conn = op.get_bind()
    tenant_ids = [
        int(value)
        for value in conn.execute(sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id")).scalars()
        if value is not None
    ]
    for tenant_id in tenant_ids:
        personal_id = _ensure_personal_root(conn, tenant_id)
        channels_id = _ensure_channels_menu(conn, tenant_id=tenant_id, personal_id=personal_id)
        role_ids = [
            int(value)
            for value in conn.execute(
                sa.text(
                    _sql("""
                    SELECT DISTINCT r.id
                    FROM roles r
                    LEFT JOIN role_menus rm
                      ON rm.role_id = r.id
                     AND rm.tenant_id = r.tenant_id
                    WHERE r.tenant_id = :tenant_id
                      AND r.deleted_at IS NULL
                      AND r.is_active IS TRUE
                      AND (
                        r.code IN ('admin', 'tenant_admin', 'user')
                        OR rm.menu_id = :personal_id
                      )
                    """)
                ),
                {"tenant_id": tenant_id, "personal_id": personal_id},
            ).scalars()
            if value is not None
        ]
        for role_id in role_ids:
            _grant_role_menu(conn, tenant_id=tenant_id, role_id=role_id, menu_id=personal_id)
            _grant_role_menu(conn, tenant_id=tenant_id, role_id=role_id, menu_id=channels_id)


def downgrade() -> None:
    return None
