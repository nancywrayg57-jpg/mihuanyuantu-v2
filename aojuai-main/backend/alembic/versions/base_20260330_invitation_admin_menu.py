"""add system menu: invitation records

Revision ID: base_20260330_invitation_admin_menu
Revises: base_20260329_invitation_foundation
Create Date: 2026-03-30

Data migration:
- add a dedicated tenant-admin visible menu entry under "系统管理" for invitation records
- grant the menu to roles: admin / tenant_admin
"""

from typing import Sequence, Union

from alembic import op


revision: str = "base_20260330_invitation_admin_menu"
down_revision: Union[str, None] = "base_20260329_invitation_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH existing_root AS (
            SELECT id, tenant_id, level
            FROM menus
            WHERE deleted_at IS NULL
              AND is_active IS TRUE
              AND title = '系统管理'
              AND parent_id IS NULL
            ORDER BY id
            LIMIT 1
        ),
        inserted_root AS (
            INSERT INTO menus (
                tenant_id, title, path, component, redirect, parent_id, level, icon, sort_order,
                menu_type, perms, is_visible, is_cache, is_frame, frame_src, is_active, no_cache,
                breadcrumb, affix, no_tags_view, can_to, always_show, meta
            )
            SELECT
                COALESCE((SELECT tenant_id FROM roles WHERE deleted_at IS NULL ORDER BY id LIMIT 1), 1),
                '系统管理',
                '/system',
                NULL,
                NULL,
                NULL,
                1,
                'ep:alarm-clock',
                2,
                '0',
                NULL,
                TRUE,
                FALSE,
                FALSE,
                NULL,
                TRUE,
                FALSE,
                TRUE,
                FALSE,
                FALSE,
                FALSE,
                TRUE,
                '{}'::jsonb
            WHERE (SELECT id FROM existing_root) IS NULL
            RETURNING id, tenant_id, level
        ),
        system_root AS (
            SELECT id, tenant_id, level FROM existing_root
            UNION ALL
            SELECT id, tenant_id, level FROM inserted_root
        ),
        existing_menu AS (
            SELECT m.id
            FROM system_root sr
            JOIN menus m ON TRUE
            WHERE m.deleted_at IS NULL
              AND m.is_active IS TRUE
              AND m.menu_type = '1'
              AND m.path = '/system/invitations'
            ORDER BY m.id
            LIMIT 1
        ),
        inserted_menu AS (
            INSERT INTO menus (
                tenant_id, title, path, component, redirect, parent_id, level, icon, sort_order,
                menu_type, perms, is_visible, is_cache, is_frame, frame_src, is_active, no_cache,
                breadcrumb, affix, no_tags_view, can_to, always_show, meta
            )
            SELECT
                sr.tenant_id,
                '邀请明细',
                '/system/invitations',
                'views/system/invitations/index',
                NULL,
                sr.id,
                sr.level + 1,
                'ep:share',
                9,
                '1',
                'invitation:admin:records',
                TRUE,
                FALSE,
                FALSE,
                NULL,
                TRUE,
                FALSE,
                TRUE,
                FALSE,
                FALSE,
                FALSE,
                FALSE,
                '{}'::jsonb
            FROM system_root sr
            WHERE (SELECT id FROM existing_menu) IS NULL
            RETURNING id
        ),
        target_menu AS (
            SELECT id FROM inserted_menu
            UNION ALL
            SELECT id FROM existing_menu
        ),
        updated_menu AS (
            UPDATE menus
            SET tenant_id = (SELECT tenant_id FROM system_root),
                title = '邀请明细',
                path = '/system/invitations',
                component = 'views/system/invitations/index',
                parent_id = (SELECT id FROM system_root),
                level = (SELECT level FROM system_root) + 1,
                icon = 'ep:share',
                sort_order = 9,
                menu_type = '1',
                perms = 'invitation:admin:records',
                is_visible = TRUE,
                is_cache = FALSE,
                is_frame = FALSE,
                frame_src = NULL,
                is_active = TRUE,
                no_cache = FALSE,
                breadcrumb = TRUE,
                affix = FALSE,
                no_tags_view = FALSE,
                can_to = FALSE,
                always_show = FALSE,
                meta = '{}'::jsonb,
                updated_at = NOW()
            WHERE id = (SELECT id FROM target_menu LIMIT 1)
              AND (SELECT id FROM system_root) IS NOT NULL
            RETURNING id
        )
        INSERT INTO role_menus (tenant_id, role_id, menu_id)
        SELECT r.tenant_id, r.id, granted.menu_id
        FROM roles r
        CROSS JOIN (
            SELECT id AS menu_id FROM system_root
            UNION ALL
            SELECT id AS menu_id FROM updated_menu
        ) granted
        WHERE r.deleted_at IS NULL
          AND r.is_active IS TRUE
          AND r.code IN ('admin', 'tenant_admin')
        ON CONFLICT (role_id, menu_id) DO NOTHING
        """
    )


def downgrade() -> None:
    pass
