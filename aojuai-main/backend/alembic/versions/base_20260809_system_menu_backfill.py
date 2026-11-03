"""backfill system menus and role grants for existing tenants

Revision ID: base_20260809_system_menu_backfill
Revises: base_20260808_merge_v2_heads
Create Date: 2026-08-09

三写里的第二写。`create_tenant_with_admin` 从这一版起会 reconcile 系统菜单，
但**已经建出来的租户**补不上——它们当初只拿到了 CMS 菜单。

在 `/menus/routes` 补上租户过滤之前，这些租户的超管还能靠"查询不带租户过滤"
看到 1 号租户的系统菜单；过滤补上之后就只剩 CMS 了。所以这条迁移必须和那个
过滤一起发布，否则是**功能倒退**。

和 CMS 那条一样，这里刻意把声明**内嵌成不可变历史快照**，不要改成 import
应用代码：以后声明改了，已发布的迁移不能跟着变。
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "base_20260809_system_menu_backfill"
down_revision: str | None = "base_20260808_merge_v2_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SYSTEM_MENU_SNAPSHOT: tuple[dict[str, object], ...] = (
    {'key': 'personal', 'parent': None, 'title': '个人中心', 'path': '/personal', 'component': None, 'icon': 'ep:user', 'sort_order': 0, 'menu_type': '0', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': True, 'meta': {}},
    {'key': 'personal-settings', 'parent': 'personal', 'title': '个人设置', 'path': '/personal/settings', 'component': 'views/personal/settings/index', 'icon': 'ep:setting', 'sort_order': 0, 'menu_type': '1', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'personal-notifications', 'parent': 'personal', 'title': '我的消息', 'path': '/personal/notifications', 'component': 'views/personal/notifications/index', 'icon': 'ep:bell', 'sort_order': 1, 'menu_type': '1', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'personal-credits', 'parent': 'personal', 'title': '我的积分', 'path': '/personal/credits', 'component': 'views/personal/credits/index', 'icon': 'ep:coin', 'sort_order': 2, 'menu_type': '1', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'personal-logs', 'parent': 'personal', 'title': '我的日志', 'path': '/personal/logs', 'component': 'views/personal/logs/index', 'icon': 'ep:document', 'sort_order': 3, 'menu_type': '1', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'system', 'parent': None, 'title': '系统管理', 'path': '/system', 'component': None, 'icon': 'ep:alarm-clock', 'sort_order': 2, 'menu_type': '0', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': True, 'meta': {}},
    {'key': 'system-user', 'parent': 'system', 'title': '用户管理', 'path': '/system/user', 'component': 'views/system/user/index', 'icon': 'ep:user', 'sort_order': 1, 'menu_type': '1', 'perms': 'user:list', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'user-read', 'parent': 'system-user', 'title': '查看用户', 'path': None, 'component': None, 'icon': None, 'sort_order': 1, 'menu_type': '2', 'perms': 'user:read', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '查看用户'}},
    {'key': 'user-create', 'parent': 'system-user', 'title': '新增用户', 'path': None, 'component': None, 'icon': None, 'sort_order': 2, 'menu_type': '2', 'perms': 'user:create', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '新增用户'}},
    {'key': 'user-update', 'parent': 'system-user', 'title': '编辑用户', 'path': None, 'component': None, 'icon': None, 'sort_order': 3, 'menu_type': '2', 'perms': 'user:update', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '编辑用户'}},
    {'key': 'user-delete', 'parent': 'system-user', 'title': '删除用户', 'path': None, 'component': None, 'icon': None, 'sort_order': 4, 'menu_type': '2', 'perms': 'user:delete', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '删除用户'}},
    {'key': 'user-audit', 'parent': 'system-user', 'title': '审核用户', 'path': None, 'component': None, 'icon': None, 'sort_order': 5, 'menu_type': '2', 'perms': 'user:audit', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '审核用户'}},
    {'key': 'user-reset-password', 'parent': 'system-user', 'title': '重置密码', 'path': None, 'component': None, 'icon': None, 'sort_order': 6, 'menu_type': '2', 'perms': 'user:reset-password', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '重置密码'}},
    {'key': 'system-role', 'parent': 'system', 'title': '角色管理', 'path': '/system/role', 'component': 'views/system/role/index', 'icon': 'ep:user-filled', 'sort_order': 2, 'menu_type': '1', 'perms': 'role:list', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'role-read', 'parent': 'system-role', 'title': '查看角色', 'path': None, 'component': None, 'icon': None, 'sort_order': 1, 'menu_type': '2', 'perms': 'role:read', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '查看角色'}},
    {'key': 'role-create', 'parent': 'system-role', 'title': '新增角色', 'path': None, 'component': None, 'icon': None, 'sort_order': 2, 'menu_type': '2', 'perms': 'role:create', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '新增角色'}},
    {'key': 'role-update', 'parent': 'system-role', 'title': '编辑角色', 'path': None, 'component': None, 'icon': None, 'sort_order': 3, 'menu_type': '2', 'perms': 'role:update', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '编辑角色'}},
    {'key': 'role-delete', 'parent': 'system-role', 'title': '删除角色', 'path': None, 'component': None, 'icon': None, 'sort_order': 4, 'menu_type': '2', 'perms': 'role:delete', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '删除角色'}},
    {'key': 'system-menu', 'parent': 'system', 'title': '菜单管理', 'path': '/system/menu', 'component': 'views/system/menu/index', 'icon': 'ep:menu', 'sort_order': 4, 'menu_type': '1', 'perms': 'menu:list', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'menu-read', 'parent': 'system-menu', 'title': '查看菜单', 'path': None, 'component': None, 'icon': None, 'sort_order': 1, 'menu_type': '2', 'perms': 'menu:read', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '查看菜单', 'requireSuperuser': True}},
    {'key': 'menu-create', 'parent': 'system-menu', 'title': '新增菜单', 'path': None, 'component': None, 'icon': None, 'sort_order': 2, 'menu_type': '2', 'perms': 'menu:create', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '新增菜单', 'requireSuperuser': True}},
    {'key': 'menu-update', 'parent': 'system-menu', 'title': '编辑菜单', 'path': None, 'component': None, 'icon': None, 'sort_order': 3, 'menu_type': '2', 'perms': 'menu:update', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '编辑菜单', 'requireSuperuser': True}},
    {'key': 'menu-delete', 'parent': 'system-menu', 'title': '删除菜单', 'path': None, 'component': None, 'icon': None, 'sort_order': 4, 'menu_type': '2', 'perms': 'menu:delete', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '删除菜单', 'requireSuperuser': True}},
    {'key': 'system-team-index', 'parent': 'system', 'title': '团队管理', 'path': '/system/team/index', 'component': 'views/system/team/index', 'icon': 'ep:aim', 'sort_order': 5, 'menu_type': '1', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'team-read', 'parent': 'system-team-index', 'title': '查看团队', 'path': None, 'component': None, 'icon': None, 'sort_order': 1, 'menu_type': '2', 'perms': 'team:read', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '查看团队'}},
    {'key': 'team-create', 'parent': 'system-team-index', 'title': '新增团队', 'path': None, 'component': None, 'icon': None, 'sort_order': 2, 'menu_type': '2', 'perms': 'team:create', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '新增团队'}},
    {'key': 'team-update', 'parent': 'system-team-index', 'title': '编辑团队', 'path': None, 'component': None, 'icon': None, 'sort_order': 3, 'menu_type': '2', 'perms': 'team:update', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '编辑团队'}},
    {'key': 'team-delete', 'parent': 'system-team-index', 'title': '删除团队', 'path': None, 'component': None, 'icon': None, 'sort_order': 4, 'menu_type': '2', 'perms': 'team:delete', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '删除团队'}},
    {'key': 'system-notifications', 'parent': 'system', 'title': '消息通知', 'path': '/system/notifications', 'component': 'views/system/notifications/index', 'icon': 'ep:bell', 'sort_order': 6, 'menu_type': '1', 'perms': 'notifications:read', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'notifications-send', 'parent': 'system-notifications', 'title': '发送通知', 'path': None, 'component': None, 'icon': None, 'sort_order': 1, 'menu_type': '2', 'perms': 'notifications:send', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '发送通知'}},
    {'key': 'system-credits', 'parent': 'system', 'title': '积分管理', 'path': '/system/credits', 'component': 'views/system/credits/index', 'icon': 'ep:coin', 'sort_order': 7, 'menu_type': '1', 'perms': 'credits:read', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'credits-account-init', 'parent': 'system-credits', 'title': '初始化账户', 'path': None, 'component': None, 'icon': None, 'sort_order': 1, 'menu_type': '2', 'perms': 'credits:account:init', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '初始化账户'}},
    {'key': 'credits-account-update', 'parent': 'system-credits', 'title': '冻结/解冻账户', 'path': None, 'component': None, 'icon': None, 'sort_order': 2, 'menu_type': '2', 'perms': 'credits:account:update', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '冻结/解冻账户'}},
    {'key': 'credits-recharge', 'parent': 'system-credits', 'title': '充值积分', 'path': None, 'component': None, 'icon': None, 'sort_order': 3, 'menu_type': '2', 'perms': 'credits:recharge', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '充值积分'}},
    {'key': 'credits-transaction-list', 'parent': 'system-credits', 'title': '查看积分流水', 'path': None, 'component': None, 'icon': None, 'sort_order': 4, 'menu_type': '2', 'perms': 'credits:transaction:list', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {'title': '查看积分流水'}},
    {'key': 'system-operation-logs', 'parent': 'system', 'title': '操作日志', 'path': '/system/operation-logs', 'component': 'views/system/operation-logs/index', 'icon': 'ep:document', 'sort_order': 8, 'menu_type': '1', 'perms': 'operation_logs:read', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'system-invitations', 'parent': 'system', 'title': '邀请明细', 'path': '/system/invitations', 'component': 'views/system/invitations/index', 'icon': 'ep:share', 'sort_order': 9, 'menu_type': '1', 'perms': 'invitation:admin:records', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'system-tenant-settings', 'parent': 'system', 'title': '租户设置', 'path': '/system/tenant-settings', 'component': 'views/system/tenant-settings/index', 'icon': 'ep:alarm-clock', 'sort_order': 9, 'menu_type': '1', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
    {'key': 'system-speech-settings', 'parent': 'system', 'title': '语音设置', 'path': '/system/speech-settings', 'component': 'views/system/speech/config/index', 'icon': 'ep:microphone', 'sort_order': 12, 'menu_type': '1', 'perms': 'speech:config', 'is_visible': False, 'can_to': True, 'always_show': False, 'meta': {'tenantSettingsExtension': True}},
    {'key': 'tenant', 'parent': None, 'title': '租户管理', 'path': '/tenant', 'component': None, 'icon': 'ep:office-building', 'sort_order': 3, 'menu_type': '0', 'perms': None, 'is_visible': True, 'can_to': False, 'always_show': True, 'meta': {}},
    {'key': 'tenant-list-index', 'parent': 'tenant', 'title': '租户列表', 'path': '/tenant/list/index', 'component': 'views/tenant/list/index', 'icon': 'ep:bell', 'sort_order': 1, 'menu_type': '1', 'perms': 'tenant:list', 'is_visible': True, 'can_to': False, 'always_show': False, 'meta': {}},
)

SYSTEM_ROLE_SNAPSHOT: tuple[dict[str, object], ...] = (
    {"code": 'admin', "name": 'Administrator', "description": 'System administrator with full access', "sort_order": 1, "data_range": 4, "data_permissions": 7, "menu_keys": ('credits-account-init', 'credits-account-update', 'credits-recharge', 'credits-transaction-list', 'menu-create', 'menu-delete', 'menu-read', 'menu-update', 'notifications-send', 'personal', 'personal-credits', 'personal-logs', 'personal-notifications', 'personal-settings', 'role-create', 'role-delete', 'role-read', 'role-update', 'system', 'system-credits', 'system-invitations', 'system-menu', 'system-notifications', 'system-operation-logs', 'system-role', 'system-speech-settings', 'system-team-index', 'system-tenant-settings', 'system-user', 'team-create', 'team-delete', 'team-read', 'team-update', 'tenant', 'tenant-list-index', 'user-audit', 'user-create', 'user-delete', 'user-read', 'user-reset-password', 'user-update')},
    {"code": 'tenant_admin', "name": 'Tenant Administrator', "description": 'Tenant administrator with full tenant-scoped access', "sort_order": 2, "data_range": 4, "data_permissions": 7, "menu_keys": ('credits-account-init', 'credits-account-update', 'credits-recharge', 'credits-transaction-list', 'menu-create', 'menu-delete', 'menu-read', 'menu-update', 'notifications-send', 'personal', 'personal-credits', 'personal-logs', 'personal-notifications', 'personal-settings', 'role-create', 'role-delete', 'role-read', 'role-update', 'system', 'system-credits', 'system-invitations', 'system-menu', 'system-notifications', 'system-operation-logs', 'system-role', 'system-speech-settings', 'system-team-index', 'system-tenant-settings', 'system-user', 'team-create', 'team-delete', 'team-read', 'team-update', 'tenant', 'tenant-list-index', 'user-audit', 'user-create', 'user-delete', 'user-read', 'user-reset-password', 'user-update')},
    {"code": 'user', "name": 'User', "description": 'Regular user with limited access', "sort_order": 3, "data_range": 0, "data_permissions": 1, "menu_keys": ('personal', 'personal-credits', 'personal-logs', 'personal-notifications', 'personal-settings')},
)


def _tenant_ids(conn: sa.Connection) -> list[int]:
    rows = conn.execute(sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id"))
    return [int(row[0]) for row in rows]


def _find_menu(conn: sa.Connection, *, tenant_id: int, spec: dict, parent_id: int | None) -> int | None:
    """按 (租户, 父级, 路径/权限码/标题) 定位已有行。

    不能只按 path 找：按钮类菜单没有 path，靠 perms 区分；
    目录类既没有 perms 也可能重名，最后才退到 title。
    """
    if spec["path"]:
        row = conn.execute(
            sa.text(
                "SELECT id FROM menus WHERE tenant_id=:t AND deleted_at IS NULL"
                " AND path=:path ORDER BY id LIMIT 1"
            ),
            {"t": tenant_id, "path": spec["path"]},
        ).first()
    elif spec["perms"]:
        row = conn.execute(
            sa.text(
                "SELECT id FROM menus WHERE tenant_id=:t AND deleted_at IS NULL"
                " AND perms=:perms ORDER BY id LIMIT 1"
            ),
            {"t": tenant_id, "perms": spec["perms"]},
        ).first()
    else:
        row = conn.execute(
            sa.text(
                "SELECT id FROM menus WHERE tenant_id=:t AND deleted_at IS NULL"
                " AND title=:title AND parent_id IS NOT DISTINCT FROM :parent"
                " ORDER BY id LIMIT 1"
            ),
            {"t": tenant_id, "title": spec["title"], "parent": parent_id},
        ).first()
    return int(row[0]) if row else None


def _insert_menu(conn: sa.Connection, *, tenant_id: int, spec: dict, parent_id: int | None, level: int) -> int:
    row = conn.execute(
        sa.text(
            "INSERT INTO menus (tenant_id, title, path, component, parent_id, level, icon,"
            " sort_order, menu_type, perms, is_visible, is_cache, is_frame, is_active,"
            " no_cache, breadcrumb, affix, no_tags_view, can_to, always_show, meta)"
            " VALUES (:tenant_id, :title, :path, :component, :parent_id, :level, :icon,"
            " :sort_order, :menu_type, :perms, :is_visible, false, false, true,"
            " false, true, false, false, :can_to, :always_show, cast(:meta as jsonb))"
            " RETURNING id"
        ),
        {
            "tenant_id": tenant_id,
            "title": spec["title"],
            "path": spec["path"],
            "component": spec["component"],
            "parent_id": parent_id,
            "level": level,
            "icon": spec["icon"],
            "sort_order": spec["sort_order"],
            "menu_type": spec["menu_type"],
            "perms": spec["perms"],
            "is_visible": spec["is_visible"],
            "can_to": spec["can_to"],
            "always_show": spec["always_show"],
            "meta": json.dumps(spec["meta"]),
        },
    ).first()
    return int(row[0])


def _ensure_role(conn: sa.Connection, *, tenant_id: int, role: dict) -> int:
    row = conn.execute(
        sa.text(
            "SELECT id FROM roles WHERE tenant_id=:t AND code=:code AND deleted_at IS NULL LIMIT 1"
        ),
        {"t": tenant_id, "code": role["code"]},
    ).first()
    if row:
        return int(row[0])
    created = conn.execute(
        sa.text(
            "INSERT INTO roles (tenant_id, name, code, description, sort_order, is_active,"
            " is_system, data_range, data_permissions, extra)"
            " VALUES (:t, :name, :code, :description, :sort_order, true, true,"
            " :data_range, :data_permissions, cast('{}' as jsonb)) RETURNING id"
        ),
        {
            "t": tenant_id,
            "name": role["name"],
            "code": role["code"],
            "description": role["description"],
            "sort_order": role["sort_order"],
            "data_range": role["data_range"],
            "data_permissions": role["data_permissions"],
        },
    ).first()
    return int(created[0])


def upgrade() -> None:
    conn = op.get_bind()
    levels = {spec["key"]: 1 for spec in SYSTEM_MENU_SNAPSHOT if spec["parent"] is None}
    for spec in SYSTEM_MENU_SNAPSHOT:
        if spec["parent"] is not None:
            levels[spec["key"]] = levels[spec["parent"]] + 1

    for tenant_id in _tenant_ids(conn):
        menu_ids: dict[str, int] = {}
        for spec in SYSTEM_MENU_SNAPSHOT:
            parent_id = menu_ids.get(spec["parent"]) if spec["parent"] else None
            if spec["parent"] and parent_id is None:
                # 父级没建成功就跳过整棵子树，避免挂出孤儿节点
                continue
            existing = _find_menu(conn, tenant_id=tenant_id, spec=spec, parent_id=parent_id)
            menu_ids[spec["key"]] = existing or _insert_menu(
                conn, tenant_id=tenant_id, spec=spec, parent_id=parent_id, level=levels[spec["key"]]
            )

        for role in SYSTEM_ROLE_SNAPSHOT:
            role_id = _ensure_role(conn, tenant_id=tenant_id, role=role)
            for key in role["menu_keys"]:
                menu_id = menu_ids.get(key)
                if menu_id is None:
                    continue
                conn.execute(
                    sa.text(
                        "INSERT INTO role_menus (tenant_id, role_id, menu_id)"
                        " VALUES (:t, :role_id, :menu_id) ON CONFLICT DO NOTHING"
                    ),
                    {"t": tenant_id, "role_id": role_id, "menu_id": menu_id},
                )


def downgrade() -> None:
    # 不删菜单：这条迁移之前这些菜单也可能已经存在（seed 建的），
    # 按 key 反删会误伤 default 租户的正常数据。补出来的授权同理。
    pass
