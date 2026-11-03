"""
AOJUAI Backend - Initial Data Seeder

Run this script to create initial data:
- Default tenant
- Admin user (username: admin, password: Admin@123456)
- Test user (username: test, password: Test@123456)
- Complete menu structure with permissions
- Roles with menu assignments

If tenants already exist, the script performs an idempotent role/menu backfill
instead of recreating the base tenant and users.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infrastructure.database.portable_sql import ptext
from app.core.security import hash_password
from app.infrastructure.database import get_db_context
from scripts.seed_cms import seed_cms_for_tenant


async def _find_top_level_menu_id(db, *, tenant_id: int, path: str) -> int | None:
    result = await db.execute(
        ptext(
            """
            SELECT id
            FROM menus
            WHERE tenant_id = :tenant_id
              AND path = :path
              AND parent_id IS NULL
              AND deleted_at IS NULL
            ORDER BY id
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id, "path": path},
    )
    menu_id = result.scalar()
    return int(menu_id) if menu_id else None


async def _find_role_id(db, *, tenant_id: int, code: str) -> int | None:
    result = await db.execute(
        ptext(
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
    )
    role_id = result.scalar()
    return int(role_id) if role_id else None


async def _sync_admin_like_role_menus(
    db,
    *,
    tenant_id: int,
    admin_role_id: int,
    tenant_admin_role_id: int | None,
    system_root_id: int | None,
) -> None:
    if tenant_admin_role_id:
        await db.execute(
            ptext(
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

    if not system_root_id:
        return

    role_ids = [admin_role_id]
    if tenant_admin_role_id:
        role_ids.append(tenant_admin_role_id)

    for role_id in role_ids:
        await db.execute(
            ptext(
                """
                WITH RECURSIVE system_tree AS (
                    SELECT id
                    FROM menus
                    WHERE id = :system_root_id

                    UNION ALL

                    SELECT m.id
                    FROM menus m
                    JOIN system_tree st ON m.parent_id = st.id
                    WHERE m.deleted_at IS NULL
                      AND m.is_active IS TRUE
                )
                INSERT INTO role_menus (tenant_id, role_id, menu_id)
                SELECT :tenant_id, :role_id, id
                FROM system_tree
                WHERE true
                ON CONFLICT (role_id, menu_id) DO NOTHING
                """
            ),
            {
                "tenant_id": tenant_id,
                "role_id": role_id,
                "system_root_id": system_root_id,
            },
        )


async def _backfill_existing_installation(db) -> dict[str, int]:
    tenant_ids_result = await db.execute(
        ptext(
            """
            SELECT id
            FROM tenants
            WHERE deleted_at IS NULL
            ORDER BY id
            """
        )
    )
    tenant_ids = [int(row_id) for row_id in tenant_ids_result.scalars().all() if row_id is not None]

    synced_admin_role_count = 0
    synced_tenant_admin_count = 0
    for tenant_id in tenant_ids:
        admin_role_id = await _find_role_id(db, tenant_id=tenant_id, code="admin")
        if admin_role_id is None:
            continue

        tenant_admin_role_id = await _find_role_id(db, tenant_id=tenant_id, code="tenant_admin")
        system_root_id = await _find_top_level_menu_id(db, tenant_id=tenant_id, path="/system")
        await _sync_admin_like_role_menus(
            db,
            tenant_id=tenant_id,
            admin_role_id=admin_role_id,
            tenant_admin_role_id=tenant_admin_role_id,
            system_root_id=system_root_id,
        )
        synced_admin_role_count += 1
        if tenant_admin_role_id is not None:
            synced_tenant_admin_count += 1

        # CMS backfill for existing tenants (idempotent).
        await seed_cms_for_tenant(
            db,
            tenant_id=tenant_id,
            role_ids={"admin": admin_role_id, "tenant_admin": tenant_admin_role_id},
        )

    return {
        "tenant_count": len(tenant_ids),
        "synced_admin_role_count": synced_admin_role_count,
        "synced_tenant_admin_count": synced_tenant_admin_count,
    }


async def seed_initial_data():
    """Seed a fresh database or reconcile admin role/menu grants on an existing one."""
    async with get_db_context() as db:
        # Check if data already exists
        result = await db.execute(ptext("SELECT COUNT(*) FROM tenants"))
        count = result.scalar()
        if count and count > 0:
            print("Data already exists, running idempotent role/menu backfill.")
            backfill_result = await _backfill_existing_installation(db)
            await db.commit()
            print(
                "✓ Existing installation backfill completed: "
                f"tenants={backfill_result.get('tenant_count', 0)}, "
                f"synced_admin_role_count={backfill_result.get('synced_admin_role_count', 0)}, "
                f"synced_tenant_admin_count={backfill_result.get('synced_tenant_admin_count', 0)}"
            )
            return

        # ============== Create Default Tenant ==============
        tenant_result = await db.execute(
            ptext("""
                INSERT INTO tenants (name, code, domain, description, is_active, config, quota)
                VALUES (:name, :code, :domain, :description, :is_active, cast(:config as jsonb), cast(:quota as jsonb))
                RETURNING id
            """),
            {
                "name": "Default Tenant",
                "code": "default",
                "domain": "localhost",
                "description": "Default tenant for development",
                "is_active": True,
                "config": json.dumps({
                    "theme": "default",
                    "assistant": {
                        "enabled": False
                    },
                    "seo": {
                        "title": "AOJUAI",
                        "keywords": "",
                        "description": ""
                    },
                    "features": ["user", "role", "permission", "menu", "team"],
                    "registration": {
                        "enabled": True,
                        "requireAudit": True,
                        "defaultRole": "user"
                    },
                    "verification": {
                        "sms": {"enabled": True},
                        "email": {"enabled": True}
                    },
                    "feature_switches": {
                        "modules": {
                            "speech": True
                        },
                        "capabilities": {
                            "verification_sms": True,
                            "verification_email": True
                        }
                    }
                }),
                "quota": json.dumps({"max_users": 100, "max_ai_apps": 10}),
            }
        )
        tenant_id = tenant_result.scalar()
        print(f"✓ Created tenant: Default Tenant (id={tenant_id})")

        # ============== Create Default Team ==============
        default_team_result = await db.execute(
            ptext("""
                INSERT INTO teams (tenant_id, name, code, status, sort_order, description)
                VALUES (:tenant_id, :name, :code, :status, :sort_order, :description)
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "name": "默认团队",
                "code": "__default__",
                "status": 1,
                "sort_order": 0,
                "description": "系统默认团队（未分组用户）",
            }
        )
        default_team_id = default_team_result.scalar()
        print(f"✓ Created default team: 默认团队 (id={default_team_id})")

        # ============== Create Roles ==============
        # Admin role
        admin_role_result = await db.execute(
            ptext("""
                INSERT INTO roles (tenant_id, name, code, description, sort_order, is_active, is_system, data_range, data_permissions, extra)
                VALUES (:tenant_id, :name, :code, :description, :sort_order, :is_active, :is_system, :data_range, :data_permissions, cast('{}' as jsonb))
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "name": "Administrator",
                "code": "admin",
                "description": "System administrator with full access",
                "sort_order": 1,
                "is_active": True,
                "is_system": True,
                "data_range": 4,  # ALL
                "data_permissions": 7,  # READ | EDIT | DELETE
            }
        )
        admin_role_id = admin_role_result.scalar()

        tenant_admin_role_result = await db.execute(
            ptext("""
                INSERT INTO roles (tenant_id, name, code, description, sort_order, is_active, is_system, data_range, data_permissions, extra)
                VALUES (:tenant_id, :name, :code, :description, :sort_order, :is_active, :is_system, :data_range, :data_permissions, cast('{}' as jsonb))
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "name": "Tenant Administrator",
                "code": "tenant_admin",
                "description": "Tenant administrator with full tenant-scoped access",
                "sort_order": 2,
                "is_active": True,
                "is_system": True,
                "data_range": 4,  # ALL
                "data_permissions": 7,  # READ | EDIT | DELETE
            }
        )
        tenant_admin_role_id = tenant_admin_role_result.scalar()

        # User role
        user_role_result = await db.execute(
            ptext("""
                INSERT INTO roles (tenant_id, name, code, description, sort_order, is_active, is_system, data_range, data_permissions, extra)
                VALUES (:tenant_id, :name, :code, :description, :sort_order, :is_active, :is_system, :data_range, :data_permissions, cast('{}' as jsonb))
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "name": "User",
                "code": "user",
                "description": "Regular user with limited access",
                "sort_order": 3,
                "is_active": True,
                "is_system": True,
                "data_range": 0,  # SELF_ONLY
                "data_permissions": 1,  # READ only
            }
        )
        user_role_id = user_role_result.scalar()
        print(
            f"✓ Created roles: admin (id={admin_role_id}), "
            f"tenant_admin (id={tenant_admin_role_id}), user (id={user_role_id})"
        )

        # ============== Create Complete Menu Structure ==============
        menu_ids = {}
        
        # Level 1: Top-level directories
        # 系统管理
        existing_system_root_id = await _find_top_level_menu_id(db, tenant_id=tenant_id, path="/system")
        if existing_system_root_id:
            menu_ids["system"] = existing_system_root_id
            print(f"✓ Reused existing system root menu: 系统管理 (id={existing_system_root_id})")
        else:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, path, parent_id, level, icon, sort_order, menu_type,
                                       is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb, affix,
                                       no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :path, :parent_id, :level, :icon, :sort_order, :menu_type,
                            :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb, :affix,
                            :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": "系统管理", "path": "/system", "parent_id": None,
                    "level": 1, "icon": "ep:alarm-clock", "sort_order": 2, "menu_type": "0",
                    "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                    "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                    "can_to": False, "always_show": True, "meta": json.dumps({})
                }
            )
            menu_ids["system"] = result.scalar()

        # 个人中心 (Personal Center - for all users, no permission required)
        result = await db.execute(
            ptext("""
                INSERT INTO menus (tenant_id, title, path, parent_id, level, icon, sort_order, menu_type,
                                   is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb, affix,
                                   no_tags_view, can_to, always_show, meta)
                VALUES (:tenant_id, :title, :path, :parent_id, :level, :icon, :sort_order, :menu_type,
                        :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb, :affix,
                        :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                RETURNING id
            """),
            {
                "tenant_id": tenant_id, "title": "个人中心", "path": "/personal", "parent_id": None,
                "level": 1, "icon": "ep:user", "sort_order": 0, "menu_type": "0",
                "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                "can_to": False, "always_show": True, "meta": json.dumps({})
            }
        )
        menu_ids["personal"] = result.scalar()

        # 租户管理
        result = await db.execute(
            ptext("""
                INSERT INTO menus (tenant_id, title, path, parent_id, level, icon, sort_order, menu_type,
                                   is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb, affix,
                                   no_tags_view, can_to, always_show, meta)
                VALUES (:tenant_id, :title, :path, :parent_id, :level, :icon, :sort_order, :menu_type,
                        :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb, :affix,
                        :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                RETURNING id
            """),
            {
                "tenant_id": tenant_id, "title": "租户管理", "path": "/tenant", "parent_id": None,
                "level": 1, "icon": "ep:office-building", "sort_order": 3, "menu_type": "0",
                "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                "can_to": False, "always_show": True, "meta": json.dumps({})
            }
        )
        menu_ids["tenant"] = result.scalar()

        # Level 2: System sub-menus
        system_menus = [
            ("user", "用户管理", "/system/user", "views/system/user/index", "ep:user", 1, "1", "user:list"),
            ("role", "角色管理", "/system/role", "views/system/role/index", "ep:user-filled", 2, "1", "role:list"),
            ("menu", "菜单管理", "/system/menu", "views/system/menu/index", "ep:menu", 4, "1", "menu:list"),
            ("team", "团队管理", "/system/team/index", "views/system/team/index", "ep:aim", 5, "1", None),
            ("notifications", "消息通知", "/system/notifications", "views/system/notifications/index", "ep:bell", 6, "1", "notifications:read"),
            ("credits", "积分管理", "/system/credits", "views/system/credits/index", "ep:coin", 7, "1", "credits:read"),
            ("operation-logs", "操作日志", "/system/operation-logs", "views/system/operation-logs/index", "ep:document", 8, "1", "operation_logs:read"),
            ("tenant-settings", "租户设置", "/system/tenant-settings", "views/system/tenant-settings/index", "ep:alarm-clock", 9, "1", None),
            ("user-import", "批量导入用户", "/system/user-import", "views/system/user-import/index", "ep:upload", 10, "1", "user:create"),
        ]

        for name, title, path, component, icon, sort_order, menu_type, perms in system_menus:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, path, component, parent_id, level, icon, sort_order,
                                       menu_type, perms, is_visible, is_cache, is_frame, is_active, no_cache,
                                       breadcrumb, affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :path, :component, :parent_id, :level, :icon, :sort_order,
                            :menu_type, :perms, :is_visible, :is_cache, :is_frame, :is_active, :no_cache,
                            :breadcrumb, :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "path": path, "component": component,
                    "parent_id": menu_ids["system"], "level": 2, "icon": icon, "sort_order": sort_order,
                    "menu_type": menu_type, "perms": perms, "is_visible": True, "is_cache": False,
                    "is_frame": False, "is_active": True, "no_cache": False, "breadcrumb": True,
                    "affix": False, "no_tags_view": False, "can_to": False, "always_show": False,
                    "meta": json.dumps({})
                }
            )
            menu_ids[name] = result.scalar()

        speech_settings_result = await db.execute(
            ptext("""
                INSERT INTO menus (tenant_id, title, path, component, parent_id, level, icon, sort_order,
                                   menu_type, perms, is_visible, is_cache, is_frame, is_active, no_cache,
                                   breadcrumb, affix, no_tags_view, can_to, always_show, meta)
                VALUES (:tenant_id, :title, :path, :component, :parent_id, :level, :icon, :sort_order,
                        :menu_type, :perms, :is_visible, :is_cache, :is_frame, :is_active, :no_cache,
                        :breadcrumb, :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "title": "语音设置",
                "path": "/system/speech-settings",
                "component": "views/system/speech/config/index",
                "parent_id": menu_ids["system"],
                "level": 2,
                "icon": "ep:microphone",
                "sort_order": 12,
                "menu_type": "1",
                "perms": "speech:config",
                "is_visible": False,
                "is_cache": False,
                "is_frame": False,
                "is_active": True,
                "no_cache": False,
                "breadcrumb": True,
                "affix": False,
                "no_tags_view": False,
                "can_to": True,
                "always_show": False,
                "meta": json.dumps({"tenantSettingsExtension": True}),
            },
        )
        menu_ids["speech-settings"] = speech_settings_result.scalar()

        # Level 2: Tenant sub-menus
        tenant_menus = [
            ("tenant-list", "租户列表", "/tenant/list/index", "views/tenant/list/index", "ep:bell", 1, "tenant:list"),
        ]

        for name, title, path, component, icon, sort_order, perms in tenant_menus:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, path, component, parent_id, level, icon, sort_order,
                                       menu_type, perms, is_visible, is_cache, is_frame, is_active, no_cache,
                                       breadcrumb, affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :path, :component, :parent_id, :level, :icon, :sort_order,
                            :menu_type, :perms, :is_visible, :is_cache, :is_frame, :is_active, :no_cache,
                            :breadcrumb, :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "path": path, "component": component,
                    "parent_id": menu_ids["tenant"], "level": 2, "icon": icon, "sort_order": sort_order,
                    "menu_type": "1", "perms": perms, "is_visible": True, "is_cache": False,
                    "is_frame": False, "is_active": True, "no_cache": False, "breadcrumb": True,
                    "affix": False, "no_tags_view": False, "can_to": False, "always_show": False,
                    "meta": json.dumps({})
                }
            )
            menu_ids[name] = result.scalar()

        # Level 2: Personal Center sub-menus (no permission required - uses /my endpoints)
        personal_menus = [
            ("my-settings", "个人设置", "/personal/settings", "views/personal/settings/index", "ep:setting", 0),
            ("my-channels", "消息 Channel", "/personal/channels", "views/personal/channels/index", "ep:chat-dot-round", 1),
            ("my-notifications", "我的消息", "/personal/notifications", "views/personal/notifications/index", "ep:bell", 1),
            ("my-credits", "我的积分", "/personal/credits", "views/personal/credits/index", "ep:coin", 2),
            ("my-logs", "我的日志", "/personal/logs", "views/personal/logs/index", "ep:document", 3),
        ]

        for name, title, path, component, icon, sort_order in personal_menus:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, path, component, parent_id, level, icon, sort_order,
                                       menu_type, perms, is_visible, is_cache, is_frame, is_active, no_cache,
                                       breadcrumb, affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :path, :component, :parent_id, :level, :icon, :sort_order,
                            :menu_type, :perms, :is_visible, :is_cache, :is_frame, :is_active, :no_cache,
                            :breadcrumb, :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "path": path, "component": component,
                    "parent_id": menu_ids["personal"], "level": 2, "icon": icon, "sort_order": sort_order,
                    "menu_type": "1", "perms": None, "is_visible": True, "is_cache": False,
                    "is_frame": False, "is_active": True, "no_cache": False, "breadcrumb": True,
                    "affix": False, "no_tags_view": False, "can_to": False, "always_show": False,
                    "meta": json.dumps({})
                }
            )
            menu_ids[name] = result.scalar()

        # Level 3: Button permissions for User Management
        user_buttons = [
            ("user:read", "查看用户", 1),
            ("user:create", "新增用户", 2),
            ("user:update", "编辑用户", 3),
            ("user:delete", "删除用户", 4),
            ("user:audit", "审核用户", 5),
            ("user:reset-password", "重置密码", 6),
        ]

        for perms, title, sort_order in user_buttons:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, parent_id, level, sort_order, menu_type, perms,
                                       is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb,
                                       affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :parent_id, :level, :sort_order, :menu_type, :perms,
                            :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb,
                            :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "parent_id": menu_ids["user"],
                    "level": 3, "sort_order": sort_order, "menu_type": "2", "perms": perms,
                    "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                    "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                    "can_to": False, "always_show": False, "meta": json.dumps({"title": title})
                }
            )
            menu_ids[f"user-{perms}"] = result.scalar()

        # Level 3: Button permissions for Role Management
        role_buttons = [
            ("role:read", "查看角色", 1),
            ("role:create", "新增角色", 2),
            ("role:update", "编辑角色", 3),
            ("role:delete", "删除角色", 4),
        ]

        for perms, title, sort_order in role_buttons:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, parent_id, level, sort_order, menu_type, perms,
                                       is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb,
                                       affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :parent_id, :level, :sort_order, :menu_type, :perms,
                            :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb,
                            :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "parent_id": menu_ids["role"],
                    "level": 3, "sort_order": sort_order, "menu_type": "2", "perms": perms,
                    "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                    "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                    "can_to": False, "always_show": False, "meta": json.dumps({"title": title})
                }
            )
            menu_ids[f"role-{perms}"] = result.scalar()

        # Level 3: Button permissions for Menu Management
        menu_buttons = [
            ("menu:read", "查看菜单", 1),
            ("menu:create", "新增菜单", 2),
            ("menu:update", "编辑菜单", 3),
            ("menu:delete", "删除菜单", 4),
        ]

        for perms, title, sort_order in menu_buttons:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, parent_id, level, sort_order, menu_type, perms,
                                       is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb,
                                       affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :parent_id, :level, :sort_order, :menu_type, :perms,
                            :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb,
                            :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "parent_id": menu_ids["menu"],
                    "level": 3, "sort_order": sort_order, "menu_type": "2", "perms": perms,
                    "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                    "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                    "can_to": False, "always_show": False, "meta": json.dumps({"title": title, "requireSuperuser": True})
                }
            )
            menu_ids[f"menu-{perms}"] = result.scalar()

        # Level 3: Button permissions for Team Management
        team_buttons = [
            ("team:read", "查看团队", 1),
            ("team:create", "新增团队", 2),
            ("team:update", "编辑团队", 3),
            ("team:delete", "删除团队", 4),
        ]

        for perms, title, sort_order in team_buttons:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, parent_id, level, sort_order, menu_type, perms,
                                       is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb,
                                       affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :parent_id, :level, :sort_order, :menu_type, :perms,
                            :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb,
                            :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "parent_id": menu_ids["team"],
                    "level": 3, "sort_order": sort_order, "menu_type": "2", "perms": perms,
                    "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                    "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                    "can_to": False, "always_show": False, "meta": json.dumps({"title": title})
                }
            )
            menu_ids[f"team-{perms}"] = result.scalar()

        # Level 3: Button permissions for Credits
        credits_buttons = [
            ("credits:account:init", "初始化账户", 1),
            ("credits:account:update", "冻结/解冻账户", 2),
            ("credits:recharge", "充值积分", 3),
            ("credits:transaction:list", "查看积分流水", 4),
            ("credits:pricing:update", "配置计费模式与费率", 5),
        ]

        for perms, title, sort_order in credits_buttons:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, parent_id, level, sort_order, menu_type, perms,
                                       is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb,
                                       affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :parent_id, :level, :sort_order, :menu_type, :perms,
                            :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb,
                            :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "parent_id": menu_ids["credits"],
                    "level": 3, "sort_order": sort_order, "menu_type": "2", "perms": perms,
                    "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                    "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                    "can_to": False, "always_show": False, "meta": json.dumps({"title": title})
                }
            )
            menu_ids[f"credits-{perms}"] = result.scalar()

        # Level 3: Button permissions for Notifications
        notification_buttons = [
            ("notifications:send", "发送通知", 1),
        ]

        for perms, title, sort_order in notification_buttons:
            result = await db.execute(
                ptext("""
                    INSERT INTO menus (tenant_id, title, parent_id, level, sort_order, menu_type, perms,
                                       is_visible, is_cache, is_frame, is_active, no_cache, breadcrumb,
                                       affix, no_tags_view, can_to, always_show, meta)
                    VALUES (:tenant_id, :title, :parent_id, :level, :sort_order, :menu_type, :perms,
                            :is_visible, :is_cache, :is_frame, :is_active, :no_cache, :breadcrumb,
                            :affix, :no_tags_view, :can_to, :always_show, cast(:meta as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": tenant_id, "title": title, "parent_id": menu_ids["notifications"],
                    "level": 3, "sort_order": sort_order, "menu_type": "2", "perms": perms,
                    "is_visible": True, "is_cache": False, "is_frame": False, "is_active": True,
                    "no_cache": False, "breadcrumb": True, "affix": False, "no_tags_view": False,
                    "can_to": False, "always_show": False, "meta": json.dumps({"title": title})
                }
            )
            menu_ids[f"notifications-{perms}"] = result.scalar()

        print(f"✓ Created {len(menu_ids)} menus with hierarchical structure")

        # ============== Assign Menus to Roles ==============
        # 硬规则：personal_menus 里创建的每一项菜单都必须同时出现在 admin 与 user 的授权列表，
        # 否则新装环境会出现"菜单存在但所有角色不可见"的静默缺口（2026-06 审计教训）。
        # Admin role gets all menus
        admin_menu_assignments = [
            # Personal Center
            menu_ids["personal"],
            menu_ids["my-settings"],
            menu_ids["my-channels"],
            menu_ids["my-notifications"],
            menu_ids["my-credits"],
            menu_ids["my-logs"],
            # System Management
            menu_ids["system"],
            menu_ids["user"],
            menu_ids["role"],
            menu_ids["menu"],
            menu_ids["team"],
            menu_ids["notifications"],
            menu_ids["credits"],
            menu_ids["operation-logs"],
            menu_ids["tenant"],
            menu_ids["tenant-list"],
            menu_ids["tenant-settings"],
            # User permissions
            menu_ids["user-user:read"],
            menu_ids["user-user:create"],
            menu_ids["user-user:update"],
            menu_ids["user-user:delete"],
            menu_ids["user-user:audit"],
            menu_ids["user-user:reset-password"],
            # Role permissions
            menu_ids["role-role:read"],
            menu_ids["role-role:create"],
            menu_ids["role-role:update"],
            menu_ids["role-role:delete"],
            # Menu permissions
            menu_ids["menu-menu:read"],
            menu_ids["menu-menu:create"],
            menu_ids["menu-menu:update"],
            menu_ids["menu-menu:delete"],
            # Team permissions
            menu_ids["team-team:read"],
            menu_ids["team-team:create"],
            menu_ids["team-team:update"],
            menu_ids["team-team:delete"],
            # Credits permissions
            menu_ids["credits-credits:account:init"],
            menu_ids["credits-credits:account:update"],
            menu_ids["credits-credits:recharge"],
            menu_ids["credits-credits:transaction:list"],
            # Notifications permissions
            menu_ids["notifications-notifications:send"],
        ]

        for menu_id in admin_menu_assignments:
            await db.execute(
                ptext("""
                    INSERT INTO role_menus (tenant_id, role_id, menu_id)
                    VALUES (:tenant_id, :role_id, :menu_id)
                """),
                {"tenant_id": tenant_id, "role_id": admin_role_id, "menu_id": menu_id}
            )

        # User role gets ONLY personal center menus (no system management access)
        user_menu_assignments = [
            # Personal Center only
            menu_ids["personal"],
            menu_ids["my-settings"],
            menu_ids["my-channels"],
            menu_ids["my-notifications"],
            menu_ids["my-credits"],
            menu_ids["my-logs"],
        ]

        for menu_id in user_menu_assignments:
            await db.execute(
                ptext("""
                    INSERT INTO role_menus (tenant_id, role_id, menu_id)
                    VALUES (:tenant_id, :role_id, :menu_id)
                """),
                {"tenant_id": tenant_id, "role_id": user_role_id, "menu_id": menu_id}
            )

        print(f"✓ Assigned {len(admin_menu_assignments)} menus to admin role")
        print(f"✓ Assigned {len(user_menu_assignments)} menus to user role")

        # ============== Create Admin User ==============
        password_hash = hash_password("Admin@123456")
        admin_user_result = await db.execute(
            ptext("""
                INSERT INTO users (tenant_id, username, password_hash, nickname, email, status, is_superuser, sex, failed_login_count, register_source, extra)
                VALUES (:tenant_id, :username, :password_hash, :nickname, :email, :status, :is_superuser, :sex, :failed_login_count, :register_source, cast('{}' as jsonb))
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "username": "admin",
                "password_hash": password_hash,
                "nickname": "Administrator",
                "email": "admin@aoju.ai",
                "status": 1,
                "is_superuser": True,
                "sex": 0,
                "failed_login_count": 0,
                "register_source": "admin",
            }
        )
        admin_user_id = admin_user_result.scalar()
        print(f"✓ Created admin user: admin (id={admin_user_id})")

        # Assign admin role to admin user
        await db.execute(
            ptext("""
                INSERT INTO user_roles (tenant_id, user_id, role_id)
                VALUES (:tenant_id, :user_id, :role_id)
            """),
            {"tenant_id": tenant_id, "user_id": admin_user_id, "role_id": admin_role_id}
        )
        print("✓ Assigned admin role to admin user")

        # Assign admin user to default team
        await db.execute(
            ptext("""
                INSERT INTO user_teams (tenant_id, user_id, team_id)
                VALUES (:tenant_id, :user_id, :team_id)
            """),
            {
                "tenant_id": tenant_id,
                "user_id": admin_user_id,
                "team_id": default_team_id,
            }
        )
        print("✓ Assigned admin user to default team")

        # ============== Create Test User ==============
        test_password_hash = hash_password("Test@123456")
        test_user_result = await db.execute(
            ptext("""
                INSERT INTO users (tenant_id, username, password_hash, nickname, email, status, is_superuser, sex, failed_login_count, register_source, extra)
                VALUES (:tenant_id, :username, :password_hash, :nickname, :email, :status, :is_superuser, :sex, :failed_login_count, :register_source, cast('{}' as jsonb))
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "username": "test",
                "password_hash": test_password_hash,
                "nickname": "测试用户",
                "email": "test@aoju.ai",
                "status": 1,
                "is_superuser": False,
                "sex": 0,
                "failed_login_count": 0,
                "register_source": "admin",
            }
        )
        test_user_id = test_user_result.scalar()
        print(f"✓ Created test user: test (id={test_user_id})")

        # Assign user role to test user
        await db.execute(
            ptext("""
                INSERT INTO user_roles (tenant_id, user_id, role_id)
                VALUES (:tenant_id, :user_id, :role_id)
            """),
            {"tenant_id": tenant_id, "user_id": test_user_id, "role_id": user_role_id}
        )
        print("✓ Assigned user role to test user")

        # Assign test user to default team
        await db.execute(
            ptext("""
                INSERT INTO user_teams (tenant_id, user_id, team_id)
                VALUES (:tenant_id, :user_id, :team_id)
            """),
            {
                "tenant_id": tenant_id,
                "user_id": test_user_id,
                "team_id": default_team_id,
            }
        )
        print("✓ Assigned test user to default team")
        await _sync_admin_like_role_menus(
            db,
            tenant_id=tenant_id,
            admin_role_id=admin_role_id,
            tenant_admin_role_id=tenant_admin_role_id,
            system_root_id=menu_ids["system"],
        )

        # CMS: menus, permissions, content_editor role and default content.
        await seed_cms_for_tenant(
            db,
            tenant_id=tenant_id,
            role_ids={"admin": admin_role_id, "tenant_admin": tenant_admin_role_id},
        )
        print("✓ Seeded CMS menus, permissions and default content")

        await db.commit()
        print("\n" + "="*60)
        print("🎉 Initial data seeded successfully!")
        print("="*60)
        print("\n📋 Summary:")
        print(f"  • Tenant: Default Tenant (id={tenant_id})")
        print(f"  • Roles: 3 (admin, tenant_admin, user)")
        print(f"  • Menus: {len(menu_ids)} (with hierarchical structure)")
        print(f"  • Users: admin (id={admin_user_id}), test (id={test_user_id})")
        print("\n🔐 Login Credentials:")
        print("  Admin:  admin / Admin@123456")
        print("  User:   test / Test@123456")
        print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed_initial_data())
