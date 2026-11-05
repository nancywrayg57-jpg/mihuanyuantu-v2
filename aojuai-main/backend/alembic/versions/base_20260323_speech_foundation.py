"""base speech foundation

Revision ID: base_20260323_speech_foundation
Revises: 0032_merge_product_heads
Create Date: 2026-03-23

Goals:
- add `speech_tenant_configs` to `nextjs-base`
- enforce tenant singleton with soft-delete-aware unique index
- add hidden system speech settings menu for tenant settings extension flow
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

from alembic import op

revision: str = "base_20260323_speech_foundation"
down_revision: str | None = "0032_merge_product_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE_NAME = "speech_tenant_configs"
LOOKUP_INDEX_NAME = "ix_speech_tenant_configs_tenant_id"
ACTIVE_UNIQUE_INDEX_NAME = "uq_speech_tenant_configs_tenant"
LEGACY_UNIQUE_NAME = "uq_speech_tenant_configs_tenant_id"
SPEECH_SETTINGS_PATH = "/system/speech-settings"
LEGACY_CONFIG_PATH = "/system/speech/config"
LEGACY_DEMO_PATH = "/system/speech/demo"


def _has_index(inspector: Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {item["name"] for item in inspector.get_indexes(table_name)}


def _has_unique(inspector: Inspector, table_name: str, unique_name: str) -> bool:
    return unique_name in {item["name"] for item in inspector.get_unique_constraints(table_name)}


def _find_menu_id(conn: sa.Connection, *, tenant_id: int, path: str) -> int | None:
    result = conn.execute(
        sa.text(
            """
            SELECT id
            FROM menus
            WHERE tenant_id = :tenant_id
              AND deleted_at IS NULL
              AND path = :path
            ORDER BY id
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id, "path": path},
    ).scalar()
    return int(result) if result else None


def _get_system_menu_id(conn: sa.Connection, *, tenant_id: int) -> int | None:
    result = conn.execute(
        sa.text(
            """
            SELECT id
            FROM menus
            WHERE tenant_id = :tenant_id
              AND deleted_at IS NULL
              AND path = '/system'
            ORDER BY id
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id},
    ).scalar()
    return int(result) if result else None


def _get_admin_role_id(conn: sa.Connection, *, tenant_id: int) -> int | None:
    result = conn.execute(
        sa.text(
            """
            SELECT id
            FROM roles
            WHERE tenant_id = :tenant_id
              AND deleted_at IS NULL
              AND code = 'admin'
            ORDER BY id
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id},
    ).scalar()
    return int(result) if result else None


def _assign_menu_to_admin(conn: sa.Connection, *, tenant_id: int, role_id: int, menu_id: int) -> None:
    exists = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM role_menus
            WHERE tenant_id = :tenant_id
              AND role_id = :role_id
              AND menu_id = :menu_id
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id, "role_id": role_id, "menu_id": menu_id},
    ).scalar()
    if exists:
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO role_menus (tenant_id, role_id, menu_id)
            VALUES (:tenant_id, :role_id, :menu_id)
            """
        ),
        {"tenant_id": tenant_id, "role_id": role_id, "menu_id": menu_id},
    )


def _upsert_speech_menu(conn: sa.Connection, *, tenant_id: int, parent_id: int) -> int | None:
    menu_id = _find_menu_id(conn, tenant_id=tenant_id, path=SPEECH_SETTINGS_PATH)
    if not menu_id:
        menu_id = _find_menu_id(conn, tenant_id=tenant_id, path=LEGACY_CONFIG_PATH)

    payload = {
        "title": "语音设置",
        "path": SPEECH_SETTINGS_PATH,
        "component": "views/system/speech/config/index",
        "icon": "ep:microphone",
        "sort_order": 12,
        "menu_type": "1",
        "perms": "speech:config",
        "is_visible": False,
        "can_to": True,
        "meta": json.dumps({"tenantSettingsExtension": True}),
        "parent_id": parent_id,
    }

    if menu_id:
        conn.execute(
            sa.text(
                """
                UPDATE menus
                SET title = :title,
                    path = :path,
                    component = :component,
                    parent_id = :parent_id,
                    level = 2,
                    icon = :icon,
                    sort_order = :sort_order,
                    menu_type = :menu_type,
                    perms = :perms,
                    is_visible = :is_visible,
                    is_active = true,
                    can_to = :can_to,
                    meta = cast(:meta as jsonb)
                WHERE id = :menu_id
                """
            ),
            {**payload, "menu_id": menu_id},
        )
        return menu_id

    result = conn.execute(
        sa.text(
            """
            INSERT INTO menus (
                tenant_id, title, path, component, parent_id, level, icon, sort_order,
                menu_type, perms, is_visible, is_cache, is_frame, is_active, no_cache,
                breadcrumb, affix, no_tags_view, can_to, always_show, meta
            )
            VALUES (
                :tenant_id, :title, :path, :component, :parent_id, 2, :icon, :sort_order,
                :menu_type, :perms, :is_visible, false, false, true, false,
                true, false, false, :can_to, false, cast(:meta as jsonb)
            )
            RETURNING id
            """
        ),
        {**payload, "tenant_id": tenant_id},
    ).scalar()
    return int(result) if result else None


def _hide_legacy_demo_menu(conn: sa.Connection, *, tenant_id: int) -> None:
    menu_id = _find_menu_id(conn, tenant_id=tenant_id, path=LEGACY_DEMO_PATH)
    if not menu_id:
        return

    conn.execute(
        sa.text(
            """
            UPDATE menus
            SET title = '语音演示（已合并）',
                perms = 'speech:config',
                is_visible = false,
                is_active = true,
                meta = cast(:meta as jsonb)
            WHERE id = :menu_id
            """
        ),
        {"menu_id": menu_id, "meta": json.dumps({"tenantSettingsExtension": True})},
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="active",
                comment="Operational status: active | degraded | error | disabled",
            ),
            sa.Column(
                "config",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="{}",
                comment="Non-secret configuration (JSONB)",
            ),
            sa.Column(
                "secrets",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="{}",
                comment="Secret configuration (JSONB)",
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
                comment="Legacy availability mirror; synced from canonical enabled/status contract",
            ),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
            sa.PrimaryKeyConstraint("id"),
            comment="租户语音配置表（TTS/STT Provider 配置与密钥）",
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, TABLE_NAME, LOOKUP_INDEX_NAME):
        op.create_index(LOOKUP_INDEX_NAME, TABLE_NAME, ["tenant_id"], unique=False)

    inspector = sa.inspect(bind)
    if _has_unique(inspector, TABLE_NAME, LEGACY_UNIQUE_NAME):
        op.drop_constraint(LEGACY_UNIQUE_NAME, TABLE_NAME, type_="unique")

    inspector = sa.inspect(bind)
    if not _has_index(inspector, TABLE_NAME, ACTIVE_UNIQUE_INDEX_NAME):
        op.create_index(
            ACTIVE_UNIQUE_INDEX_NAME,
            TABLE_NAME,
            ["tenant_id"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )

    tenant_ids = list(bind.execute(sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id")).scalars().all())
    for tenant_id_raw in tenant_ids:
        tenant_id = int(tenant_id_raw)
        system_menu_id = _get_system_menu_id(bind, tenant_id=tenant_id)
        if not system_menu_id:
            continue

        menu_id = _upsert_speech_menu(bind, tenant_id=tenant_id, parent_id=system_menu_id)
        if menu_id:
            admin_role_id = _get_admin_role_id(bind, tenant_id=tenant_id)
            if admin_role_id:
                _assign_menu_to_admin(bind, tenant_id=tenant_id, role_id=admin_role_id, menu_id=menu_id)

        _hide_legacy_demo_menu(bind, tenant_id=tenant_id)


def downgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)

    if inspector.has_table("menus"):
        bind.execute(
            sa.text(
                """
                DELETE FROM role_menus
                WHERE menu_id IN (
                    SELECT id FROM menus WHERE path = :speech_path
                )
                """
            ),
            {"speech_path": SPEECH_SETTINGS_PATH},
        )
        bind.execute(
            sa.text(
                """
                DELETE FROM menus
                WHERE path = :speech_path
                """
            ),
            {"speech_path": SPEECH_SETTINGS_PATH},
        )

    inspector = sa.inspect(bind)
    if inspector.has_table(TABLE_NAME):
        if _has_index(inspector, TABLE_NAME, ACTIVE_UNIQUE_INDEX_NAME):
            op.drop_index(ACTIVE_UNIQUE_INDEX_NAME, table_name=TABLE_NAME)

        inspector = sa.inspect(bind)
        if _has_index(inspector, TABLE_NAME, LOOKUP_INDEX_NAME):
            op.drop_index(LOOKUP_INDEX_NAME, table_name=TABLE_NAME)

        op.drop_table(TABLE_NAME)
