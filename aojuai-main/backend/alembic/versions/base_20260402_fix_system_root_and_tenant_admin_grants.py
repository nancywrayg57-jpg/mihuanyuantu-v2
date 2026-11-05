"""fix duplicate system roots and tenant admin grants

Revision ID: base_20260402_fix_system_root_and_tenant_admin_grants
Revises: base_20260331_assistant_foundation
Create Date: 2026-04-02

Goals:
- collapse duplicated `/system` top-level menus created by migration + seed ordering
- ensure a dedicated `tenant_admin` role exists for each tenant
- ensure `admin` / `tenant_admin` roles can see the full system-management subtree
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "base_20260402_fix_system_root_and_tenant_admin_grants"
down_revision: str | None = "base_20260331_assistant_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_tenant_ids(conn: sa.Connection) -> list[int]:
    rows = conn.execute(
        sa.text(
            """
            SELECT id
            FROM tenants
            WHERE deleted_at IS NULL
            ORDER BY id
            """
        )
    ).all()
    return [int(row[0]) for row in rows if row and row[0]]


def _get_role_id(conn: sa.Connection, *, tenant_id: int, code: str) -> int | None:
    role_id = conn.execute(
        sa.text(
            """
            SELECT id
            FROM roles
            WHERE tenant_id = :tenant_id
              AND code = :code
              AND deleted_at IS NULL
            ORDER BY id
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id, "code": code},
    ).scalar()
    return int(role_id) if role_id else None


def _ensure_tenant_admin_role(conn: sa.Connection, *, tenant_id: int) -> int | None:
    existing_role_id = _get_role_id(conn, tenant_id=tenant_id, code="tenant_admin")
    if existing_role_id:
        return existing_role_id

    admin_row = conn.execute(
        sa.text(
            """
            SELECT sort_order, is_active, is_system, data_range, data_permissions
            FROM roles
            WHERE tenant_id = :tenant_id
              AND code = 'admin'
              AND deleted_at IS NULL
            ORDER BY id
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id},
    ).first()

    if not admin_row:
        return None

    role_id = conn.execute(
        sa.text(
            """
            INSERT INTO roles (
                tenant_id, name, code, description, sort_order, is_active, is_system,
                data_range, data_permissions, extra
            )
            VALUES (
                :tenant_id, :name, 'tenant_admin', :description, :sort_order, :is_active, :is_system,
                :data_range, :data_permissions, cast('{}' as jsonb)
            )
            RETURNING id
            """
        ),
        {
            "tenant_id": tenant_id,
            "name": "Tenant Administrator",
            "description": "Tenant administrator with full tenant-scoped access",
            "sort_order": int(admin_row[0]) + 1,
            "is_active": bool(admin_row[1]),
            "is_system": bool(admin_row[2]),
            "data_range": int(admin_row[3] or 4),
            "data_permissions": int(admin_row[4] or 7),
        },
    ).scalar()
    return int(role_id) if role_id else None


def _get_system_root_ids(conn: sa.Connection, *, tenant_id: int) -> list[int]:
    rows = conn.execute(
        sa.text(
            """
            SELECT id
            FROM menus
            WHERE tenant_id = :tenant_id
              AND path = '/system'
              AND parent_id IS NULL
              AND deleted_at IS NULL
            ORDER BY id
            """
        ),
        {"tenant_id": tenant_id},
    ).all()
    return [int(row[0]) for row in rows if row and row[0]]


def _normalize_system_root(conn: sa.Connection, *, tenant_id: int, root_id: int) -> None:
    conn.execute(
        sa.text(
            """
            UPDATE menus
            SET title = '系统管理',
                path = '/system',
                parent_id = NULL,
                level = 1,
                icon = 'ep:alarm-clock',
                sort_order = 2,
                menu_type = '0',
                is_visible = TRUE,
                is_cache = FALSE,
                is_frame = FALSE,
                is_active = TRUE,
                no_cache = FALSE,
                breadcrumb = TRUE,
                affix = FALSE,
                no_tags_view = FALSE,
                can_to = FALSE,
                always_show = TRUE,
                meta = '{}'::jsonb,
                updated_at = NOW()
            WHERE tenant_id = :tenant_id
              AND id = :root_id
            """
        ),
        {"tenant_id": tenant_id, "root_id": root_id},
    )


def _consolidate_system_roots(conn: sa.Connection, *, tenant_id: int) -> int | None:
    root_ids = _get_system_root_ids(conn, tenant_id=tenant_id)
    if not root_ids:
        return None

    canonical_root_id = root_ids[0]
    _normalize_system_root(conn, tenant_id=tenant_id, root_id=canonical_root_id)

    for duplicate_root_id in root_ids[1:]:
        conn.execute(
            sa.text(
                """
                UPDATE menus
                SET parent_id = :canonical_root_id,
                    updated_at = NOW()
                WHERE tenant_id = :tenant_id
                  AND parent_id = :duplicate_root_id
                  AND deleted_at IS NULL
                """
            ),
            {
                "tenant_id": tenant_id,
                "canonical_root_id": canonical_root_id,
                "duplicate_root_id": duplicate_root_id,
            },
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO role_menus (tenant_id, role_id, menu_id)
                SELECT :tenant_id, role_id, :canonical_root_id
                FROM role_menus
                WHERE tenant_id = :tenant_id
                  AND menu_id = :duplicate_root_id
                ON CONFLICT (role_id, menu_id) DO NOTHING
                """
            ),
            {
                "tenant_id": tenant_id,
                "canonical_root_id": canonical_root_id,
                "duplicate_root_id": duplicate_root_id,
            },
        )
        conn.execute(
            sa.text(
                """
                DELETE FROM role_menus
                WHERE tenant_id = :tenant_id
                  AND menu_id = :duplicate_root_id
                """
            ),
            {"tenant_id": tenant_id, "duplicate_root_id": duplicate_root_id},
        )
        conn.execute(
            sa.text(
                """
                UPDATE menus
                SET is_active = FALSE,
                    deleted_at = COALESCE(deleted_at, NOW()),
                    updated_at = NOW()
                WHERE tenant_id = :tenant_id
                  AND id = :duplicate_root_id
                """
            ),
            {"tenant_id": tenant_id, "duplicate_root_id": duplicate_root_id},
        )

    return canonical_root_id


def _clone_admin_grants_to_tenant_admin(
    conn: sa.Connection,
    *,
    tenant_id: int,
    admin_role_id: int | None,
    tenant_admin_role_id: int | None,
) -> None:
    if not admin_role_id or not tenant_admin_role_id:
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO role_menus (tenant_id, role_id, menu_id)
            SELECT :tenant_id, :tenant_admin_role_id, rm.menu_id
            FROM role_menus rm
            WHERE rm.tenant_id = :tenant_id
              AND rm.role_id = :admin_role_id
            ON CONFLICT (role_id, menu_id) DO NOTHING
            """
        ),
        {
            "tenant_id": tenant_id,
            "tenant_admin_role_id": tenant_admin_role_id,
            "admin_role_id": admin_role_id,
        },
    )


def _grant_system_subtree(conn: sa.Connection, *, tenant_id: int, role_id: int, system_root_id: int) -> None:
    conn.execute(
        sa.text(
            """
            WITH RECURSIVE system_tree AS (
                SELECT id
                FROM menus
                WHERE id = :system_root_id

                UNION ALL

                SELECT m.id
                FROM menus m
                JOIN system_tree st ON m.parent_id = st.id
                WHERE m.tenant_id = :tenant_id
                  AND m.deleted_at IS NULL
                  AND m.is_active IS TRUE
            )
            INSERT INTO role_menus (tenant_id, role_id, menu_id)
            SELECT :tenant_id, :role_id, id
            FROM system_tree
            ON CONFLICT (role_id, menu_id) DO NOTHING
            """
        ),
        {
            "tenant_id": tenant_id,
            "role_id": role_id,
            "system_root_id": system_root_id,
        },
    )


def upgrade() -> None:
    conn = op.get_bind()

    for tenant_id in _get_tenant_ids(conn):
        system_root_id = _consolidate_system_roots(conn, tenant_id=tenant_id)
        if not system_root_id:
            continue

        admin_role_id = _get_role_id(conn, tenant_id=tenant_id, code="admin")
        tenant_admin_role_id = _ensure_tenant_admin_role(conn, tenant_id=tenant_id)
        _clone_admin_grants_to_tenant_admin(
            conn,
            tenant_id=tenant_id,
            admin_role_id=admin_role_id,
            tenant_admin_role_id=tenant_admin_role_id,
        )

        for role_code in ("admin", "tenant_admin"):
            role_id = _get_role_id(conn, tenant_id=tenant_id, code=role_code)
            if role_id:
                _grant_system_subtree(conn, tenant_id=tenant_id, role_id=role_id, system_root_id=system_root_id)


def downgrade() -> None:
    pass
