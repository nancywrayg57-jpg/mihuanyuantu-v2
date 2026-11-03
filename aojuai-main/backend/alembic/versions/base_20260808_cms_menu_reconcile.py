"""reconcile CMS menus and role grants for existing tenants

Revision ID: base_20260808_cms_menu_reconcile
Revises: base_20260622_cms_languages
Create Date: 2026-08-08

This data migration intentionally embeds the CMS declaration as an immutable
historical snapshot.  Do not replace it with an import from application code:
later declaration edits must not change an already-published migration.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "base_20260808_cms_menu_reconcile"
down_revision: str | None = "base_20260622_cms_languages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# key, parent_key, title, path, component, icon, sort_order, menu_type, perms, is_visible
CMS_MENU_SNAPSHOT = (
    ("cms", None, "内容管理", "/cms", None, "ep:management", 1, "0", None, True),
    (
        "cms-pages",
        "cms",
        "页面管理",
        "/cms/pages",
        "views/cms/pages/index",
        "ep:document",
        0,
        "1",
        "cms:page:read",
        True,
    ),
    ("cms-page-create", "cms-pages", "新建页面", None, None, None, 0, "2", "cms:page:create", False),
    ("cms-page-update", "cms-pages", "编辑页面", None, None, None, 1, "2", "cms:page:update", False),
    ("cms-page-delete", "cms-pages", "删除页面", None, None, None, 2, "2", "cms:page:delete", False),
    ("cms-page-publish", "cms-pages", "发布页面", None, None, None, 3, "2", "cms:page:publish", False),
    (
        "cms-posts",
        "cms",
        "博客文章",
        "/cms/posts",
        "views/cms/posts/index",
        "ep:notebook",
        1,
        "1",
        "cms:post:read",
        True,
    ),
    ("cms-post-create", "cms-posts", "新建文章", None, None, None, 0, "2", "cms:post:create", False),
    ("cms-post-update", "cms-posts", "编辑文章", None, None, None, 1, "2", "cms:post:update", False),
    ("cms-post-delete", "cms-posts", "删除文章", None, None, None, 2, "2", "cms:post:delete", False),
    ("cms-post-publish", "cms-posts", "发布文章", None, None, None, 3, "2", "cms:post:publish", False),
    (
        "cms-navigation",
        "cms",
        "导航管理",
        "/cms/navigation",
        "views/cms/navigation/index",
        "ep:guide",
        2,
        "1",
        "cms:nav:read",
        True,
    ),
    ("cms-nav-update", "cms-navigation", "更新导航", None, None, None, 0, "2", "cms:nav:update", False),
    (
        "cms-languages",
        "cms",
        "语言管理",
        "/cms/languages",
        "views/cms/languages/index",
        "ep:guide",
        3,
        "1",
        "cms:settings:read",
        True,
    ),
    (
        "cms-settings",
        "cms",
        "站点设置",
        "/cms/settings",
        "views/cms/settings/index",
        "ep:setting",
        4,
        "1",
        "cms:settings:read",
        True,
    ),
    ("cms-settings-update", "cms-settings", "更新设置", None, None, None, 0, "2", "cms:settings:update", False),
    (
        "cms-messages",
        "cms",
        "客户留言",
        "/cms/messages",
        "views/cms/messages/index",
        "ep:message",
        5,
        "1",
        "cms:contact:read",
        True,
    ),
    ("cms-contact-update", "cms-messages", "处理留言", None, None, None, 0, "2", "cms:contact:update", False),
)

CMS_ALL_KEYS = tuple(row[0] for row in CMS_MENU_SNAPSHOT)
CMS_ROLE_GRANTS_SNAPSHOT = (
    ("admin", CMS_ALL_KEYS),
    ("tenant_admin", CMS_ALL_KEYS),
    (
        "content_editor",
        (
            "cms-pages",
            "cms-page-create",
            "cms-page-update",
            "cms-posts",
            "cms-post-create",
            "cms-post-update",
            "cms-messages",
        ),
    ),
)


def _tenant_ids(conn: sa.Connection) -> list[int]:
    rows = conn.execute(sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id")).scalars().all()
    return [int(tenant_id) for tenant_id in rows]


def _menu_values(row: tuple[object, ...], *, parent_id: int | None, level: int) -> dict[str, object]:
    _key, _parent_key, title, path, component, icon, sort_order, menu_type, perms, is_visible = row
    return {
        "title": title,
        "path": path,
        "component": component,
        "redirect": None,
        "parent_id": parent_id,
        "level": level,
        "icon": icon,
        "sort_order": sort_order,
        "menu_type": menu_type,
        "perms": perms,
        "is_visible": is_visible,
        "is_cache": False,
        "is_frame": False,
        "frame_src": None,
        "is_active": True,
        "no_cache": False,
        "breadcrumb": True,
        "affix": False,
        "no_tags_view": False,
        "can_to": False,
        "always_show": False,
        "meta": json.dumps({}),
    }


def _find_candidates(
    conn: sa.Connection,
    *,
    tenant_id: int,
    parent_id: int | None,
    title: str,
    path: str | None,
    menu_type: str,
    perms: str | None,
) -> list[int]:
    rows = (
        conn.execute(
            sa.text(
                "SELECT id, parent_id, title, path, perms FROM menus "
                "WHERE tenant_id=:tenant_id AND deleted_at IS NULL AND menu_type=:menu_type ORDER BY id"
            ),
            {"tenant_id": tenant_id, "menu_type": menu_type},
        )
        .mappings()
        .all()
    )
    candidates: list[tuple[int, int]] = []
    for current in rows:
        score: int | None = None
        if path is not None and current["path"] == path:
            score = 0
        elif menu_type == "2" and perms is not None and current["perms"] == perms:
            score = 1
        elif current["parent_id"] == parent_id and current["title"] == title:
            score = 2
        if score is not None:
            candidates.append((score, int(current["id"])))
    candidates.sort()
    return [menu_id for _score, menu_id in candidates]


def _merge_duplicate(
    conn: sa.Connection,
    *,
    tenant_id: int,
    duplicate_id: int,
    canonical_id: int,
) -> None:
    conn.execute(
        sa.text("UPDATE menus SET parent_id=:canonical_id, updated_at=now() WHERE parent_id=:duplicate_id"),
        {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
    )
    conn.execute(
        sa.text(
            "INSERT INTO role_menus (tenant_id, role_id, menu_id) "
            "SELECT :tenant_id, role_id, :canonical_id FROM role_menus "
            "WHERE tenant_id=:tenant_id AND menu_id=:duplicate_id "
            "ON CONFLICT (role_id, menu_id) DO NOTHING"
        ),
        {"tenant_id": tenant_id, "canonical_id": canonical_id, "duplicate_id": duplicate_id},
    )
    conn.execute(
        sa.text("DELETE FROM role_menus WHERE tenant_id=:tenant_id AND menu_id=:duplicate_id"),
        {"tenant_id": tenant_id, "duplicate_id": duplicate_id},
    )
    conn.execute(
        sa.text(
            "UPDATE menus SET is_active=false, deleted_at=coalesce(deleted_at, now()), updated_at=now() "
            "WHERE tenant_id=:tenant_id AND id=:duplicate_id"
        ),
        {"tenant_id": tenant_id, "duplicate_id": duplicate_id},
    )


def _upsert_menu(
    conn: sa.Connection,
    *,
    tenant_id: int,
    row: tuple[object, ...],
    parent_id: int | None,
    level: int,
) -> int:
    _key, _parent_key, title, path, _component, _icon, _sort, menu_type, perms, _visible = row
    values = _menu_values(row, parent_id=parent_id, level=level)
    candidates = _find_candidates(
        conn,
        tenant_id=tenant_id,
        parent_id=parent_id,
        title=str(title),
        path=str(path) if path is not None else None,
        menu_type=str(menu_type),
        perms=str(perms) if perms is not None else None,
    )
    if candidates:
        menu_id = candidates[0]
        for duplicate_id in candidates[1:]:
            _merge_duplicate(
                conn,
                tenant_id=tenant_id,
                duplicate_id=duplicate_id,
                canonical_id=menu_id,
            )
        conn.execute(
            sa.text(
                "UPDATE menus SET title=:title, path=:path, component=:component, redirect=:redirect, "
                "parent_id=:parent_id, level=:level, icon=:icon, sort_order=:sort_order, "
                "menu_type=:menu_type, perms=:perms, is_visible=:is_visible, is_cache=:is_cache, "
                "is_frame=:is_frame, frame_src=:frame_src, is_active=:is_active, no_cache=:no_cache, "
                "breadcrumb=:breadcrumb, affix=:affix, no_tags_view=:no_tags_view, can_to=:can_to, "
                "always_show=:always_show, meta=cast(:meta as jsonb), updated_at=now() WHERE id=:menu_id AND "
                "(title, path, component, redirect, parent_id, level, icon, sort_order, menu_type, perms, "
                "is_visible, is_cache, is_frame, frame_src, is_active, no_cache, breadcrumb, affix, "
                "no_tags_view, can_to, always_show, meta) IS DISTINCT FROM "
                "(:title, :path, :component, :redirect, :parent_id, :level, :icon, :sort_order, :menu_type, "
                ":perms, :is_visible, :is_cache, :is_frame, :frame_src, :is_active, :no_cache, :breadcrumb, "
                ":affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))"
            ),
            {**values, "menu_id": menu_id},
        )
        return menu_id

    menu_id = conn.execute(
        sa.text(
            "INSERT INTO menus (tenant_id, title, path, component, redirect, parent_id, level, icon, "
            "sort_order, menu_type, perms, is_visible, is_cache, is_frame, frame_src, is_active, "
            "no_cache, breadcrumb, affix, no_tags_view, can_to, always_show, meta) VALUES "
            "(:tenant_id, :title, :path, :component, :redirect, :parent_id, :level, :icon, "
            ":sort_order, :menu_type, :perms, :is_visible, :is_cache, :is_frame, :frame_src, :is_active, "
            ":no_cache, :breadcrumb, :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb)) "
            "RETURNING id"
        ),
        {**values, "tenant_id": tenant_id},
    ).scalar_one()
    return int(menu_id)


def _role_id(conn: sa.Connection, *, tenant_id: int, code: str) -> int | None:
    value = conn.execute(
        sa.text(
            "SELECT id FROM roles WHERE tenant_id=:tenant_id AND code=:code AND deleted_at IS NULL ORDER BY id LIMIT 1"
        ),
        {"tenant_id": tenant_id, "code": code},
    ).scalar()
    return int(value) if value is not None else None


def _ensure_content_editor(conn: sa.Connection, *, tenant_id: int) -> int:
    existing = _role_id(conn, tenant_id=tenant_id, code="content_editor")
    if existing is not None:
        return existing
    role_id = conn.execute(
        sa.text(
            "INSERT INTO roles (tenant_id, name, code, description, sort_order, is_active, is_system, "
            "data_range, data_permissions, extra) VALUES "
            "(:tenant_id, '内容编辑', 'content_editor', :description, 4, true, true, 0, 3, '{}'::jsonb) "
            "RETURNING id"
        ),
        {"tenant_id": tenant_id, "description": "可编辑页面与文章草稿，不能发布或修改站点设置"},
    ).scalar_one()
    return int(role_id)


def _with_parent_closure(keys: Sequence[str], parents: dict[str, str | None]) -> set[str]:
    closed = set(keys)
    pending = list(keys)
    while pending:
        parent_key = parents[pending.pop()]
        if parent_key is not None and parent_key not in closed:
            closed.add(parent_key)
            pending.append(parent_key)
    return closed


def upgrade() -> None:
    conn = op.get_bind()
    parents = {str(row[0]): str(row[1]) if row[1] is not None else None for row in CMS_MENU_SNAPSHOT}
    levels: dict[str, int] = {}
    for key, parent_key in parents.items():
        levels[key] = 1 if parent_key is None else levels[parent_key] + 1

    for tenant_id in _tenant_ids(conn):
        menu_ids: dict[str, int] = {}
        for row in CMS_MENU_SNAPSHOT:
            key = str(row[0])
            parent_key = str(row[1]) if row[1] is not None else None
            menu_ids[key] = _upsert_menu(
                conn,
                tenant_id=tenant_id,
                row=row,
                parent_id=menu_ids[parent_key] if parent_key is not None else None,
                level=levels[key],
            )

        role_ids = {
            "admin": _role_id(conn, tenant_id=tenant_id, code="admin"),
            "tenant_admin": _role_id(conn, tenant_id=tenant_id, code="tenant_admin"),
            "content_editor": _ensure_content_editor(conn, tenant_id=tenant_id),
        }
        for role_code, declared_keys in CMS_ROLE_GRANTS_SNAPSHOT:
            role_id = role_ids[role_code]
            if role_id is None:
                continue
            for menu_key in _with_parent_closure(declared_keys, parents):
                conn.execute(
                    sa.text(
                        "INSERT INTO role_menus (tenant_id, role_id, menu_id) "
                        "VALUES (:tenant_id, :role_id, :menu_id) "
                        "ON CONFLICT (role_id, menu_id) DO NOTHING"
                    ),
                    {"tenant_id": tenant_id, "role_id": role_id, "menu_id": menu_ids[menu_key]},
                )


def downgrade() -> None:
    # Additive/repair data migrations are not safely reversible: some rows may
    # have existed before this revision and must not be deleted on downgrade.
    pass
