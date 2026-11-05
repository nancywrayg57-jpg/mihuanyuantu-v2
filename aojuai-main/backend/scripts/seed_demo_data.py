"""
AOJU Backend - Demo Data Seeder

Creates demo data for testing multi-tenant features:
- Multiple tenants with different configurations
- System admin, tenant admins, and regular users
- Different roles and permissions

Run: python -m scripts.seed_demo_data
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import create_invite_code, hash_password
from app.infrastructure.database import get_db_context
from app.infrastructure.database.portable_sql import ptext


async def seed_demo_data():
    """Seed demo data for testing"""
    async with get_db_context() as db:
        print("\n=== Creating Demo Data ===\n")

        # Get existing default tenant
        result = await db.execute(
            ptext("SELECT id FROM tenants WHERE code = 'default'")
        )
        default_tenant_id = result.scalar()

        if not default_tenant_id:
            print("Default tenant not found. Please run seed_data.py first.")
            return

        # Get admin role ID
        result = await db.execute(
            ptext("SELECT id FROM roles WHERE code = 'admin' AND tenant_id = :tid"),
            {"tid": default_tenant_id}
        )
        admin_role_id = result.scalar()

        # Get user role ID
        result = await db.execute(
            ptext("SELECT id FROM roles WHERE code = 'user' AND tenant_id = :tid"),
            {"tid": default_tenant_id}
        )
        user_role_id = result.scalar()

        # ==================== Create Second Tenant (Acme Corp) ====================
        print("Creating Acme Corp tenant...")

        result = await db.execute(
            ptext("SELECT id FROM tenants WHERE code = 'acme'")
        )
        acme_tenant_id = result.scalar()

        if not acme_tenant_id:
            result = await db.execute(
                ptext("""
                    INSERT INTO tenants (name, code, domain, description, is_active, config, quota)
                    VALUES (:name, :code, :domain, :description, :is_active, cast(:config as jsonb), cast(:quota as jsonb))
                    RETURNING id
                """),
                {
                    "name": "Acme Corporation",
                    "code": "acme",
                    "domain": "acme.example.com",
                    "description": "Demo tenant for Acme Corporation",
                    "is_active": True,
                    "config": json.dumps({
                        "theme": "blue",
                        "assistant": {
                            "enabled": False
                        },
                        "registration": {
                            "enabled": True,
                            "requireAudit": False,  # No audit required
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
                    "quota": json.dumps({"max_users": 50, "max_ai_apps": 5}),
                }
            )
            acme_tenant_id = result.scalar()
            print(f"  Created Acme Corp tenant (id={acme_tenant_id})")

            # Create roles for Acme
            await db.execute(
                ptext("""
                    INSERT INTO roles (tenant_id, name, code, description, sort_order, is_active, is_system, extra)
                    VALUES (:tenant_id, 'Administrator', 'admin', 'Tenant administrator', 1, true, true, cast('{}' as jsonb))
                """),
                {"tenant_id": acme_tenant_id}
            )
            await db.execute(
                ptext("""
                    INSERT INTO roles (tenant_id, name, code, description, sort_order, is_active, is_system, extra)
                    VALUES (:tenant_id, 'User', 'user', 'Regular user', 2, true, true, cast('{}' as jsonb))
                """),
                {"tenant_id": acme_tenant_id}
            )

            # Get Acme role IDs
            result = await db.execute(
                ptext("SELECT id FROM roles WHERE code = 'admin' AND tenant_id = :tid"),
                {"tid": acme_tenant_id}
            )
            acme_admin_role_id = result.scalar()

            result = await db.execute(
                ptext("SELECT id FROM roles WHERE code = 'user' AND tenant_id = :tid"),
                {"tid": acme_tenant_id}
            )
            acme_user_role_id = result.scalar()
        else:
            print(f"  Acme Corp tenant already exists (id={acme_tenant_id})")
            result = await db.execute(
                ptext("SELECT id FROM roles WHERE code = 'admin' AND tenant_id = :tid"),
                {"tid": acme_tenant_id}
            )
            acme_admin_role_id = result.scalar()
            result = await db.execute(
                ptext("SELECT id FROM roles WHERE code = 'user' AND tenant_id = :tid"),
                {"tid": acme_tenant_id}
            )
            acme_user_role_id = result.scalar()

        # ==================== Create Demo Users ====================
        print("\nCreating demo users...")

        demo_users = [
            # Default Tenant Users
            {
                "tenant_id": default_tenant_id,
                "username": "tenant_admin",
                "password": "test123",
                "nickname": "Tenant Admin",
                "email": "tenant_admin@default.local",
                "is_superuser": False,
                "role_id": admin_role_id,
                "description": "Default tenant admin (has admin role)"
            },
            {
                "tenant_id": default_tenant_id,
                "username": "user1",
                "password": "test123",
                "nickname": "Regular User 1",
                "email": "user1@default.local",
                "is_superuser": False,
                "role_id": user_role_id,
                "description": "Regular user in default tenant"
            },
            # Acme Tenant Users
            {
                "tenant_id": acme_tenant_id,
                "username": "acme_admin",
                "password": "test123",
                "nickname": "Acme Admin",
                "email": "admin@acme.local",
                "is_superuser": False,
                "role_id": acme_admin_role_id,
                "description": "Acme tenant admin"
            },
            {
                "tenant_id": acme_tenant_id,
                "username": "acme_user",
                "password": "test123",
                "nickname": "Acme User",
                "email": "user@acme.local",
                "is_superuser": False,
                "role_id": acme_user_role_id,
                "description": "Regular user in Acme tenant"
            },
        ]

        for user_data in demo_users:
            # Check if user exists
            result = await db.execute(
                ptext("SELECT id FROM users WHERE username = :username AND tenant_id = :tid"),
                {"username": user_data["username"], "tid": user_data["tenant_id"]}
            )
            existing_user_id = result.scalar()

            if existing_user_id:
                print(f"  User '{user_data['username']}' already exists, skipping")
                continue

            password_hash = hash_password(user_data["password"])
            result = await db.execute(
                ptext("""
                    INSERT INTO users (tenant_id, username, password_hash, nickname, email, status, is_superuser, sex, failed_login_count, register_source, extra)
                    VALUES (:tenant_id, :username, :password_hash, :nickname, :email, 1, :is_superuser, 0, 0, 'admin', cast('{}' as jsonb))
                    RETURNING id
                """),
                {
                    "tenant_id": user_data["tenant_id"],
                    "username": user_data["username"],
                    "password_hash": password_hash,
                    "nickname": user_data["nickname"],
                    "email": user_data["email"],
                    "is_superuser": user_data["is_superuser"],
                }
            )
            user_id = result.scalar()

            # Assign role
            await db.execute(
                ptext("""
                    INSERT INTO user_roles (tenant_id, user_id, role_id)
                    VALUES (:tenant_id, :user_id, :role_id)
                """),
                {
                    "tenant_id": user_data["tenant_id"],
                    "user_id": user_id,
                    "role_id": user_data["role_id"],
                }
            )
            print(f"  Created user: {user_data['username']} ({user_data['description']})")

        await db.commit()

        # Generate invite codes
        print("\n=== Generating Invite Codes ===\n")
        default_invite = create_invite_code("default", 30)
        acme_invite = create_invite_code("acme", 30)

        print("=== Demo Data Created Successfully! ===\n")
        print("Test Accounts:\n")
        print("┌─────────────────────────────────────────────────────────────────────────┐")
        print("│ Role             │ Username      │ Password  │ Tenant          │ Notes │")
        print("├─────────────────────────────────────────────────────────────────────────┤")
        print("│ System Admin     │ admin         │ Admin@123456 │ Default Tenant  │ Can manage all tenants │")
        print("│ Tenant Admin     │ tenant_admin  │ test123   │ Default Tenant  │ Can manage own tenant  │")
        print("│ Regular User     │ user1         │ test123   │ Default Tenant  │ Limited access         │")
        print("├─────────────────────────────────────────────────────────────────────────┤")
        print("│ Tenant Admin     │ acme_admin    │ test123   │ Acme Corp       │ Can manage Acme tenant │")
        print("│ Regular User     │ acme_user     │ test123   │ Acme Corp       │ Limited access         │")
        print("└─────────────────────────────────────────────────────────────────────────┘")
        print("")
        print("Tenant Registration Settings:")
        print("  - Default Tenant: Registration enabled, requires audit")
        print("  - Acme Corp: Registration enabled, NO audit required (auto-approve)")
        print("")
        print("Invite Links (for registration without entering tenant code):")
        print(f"  - Default Tenant: /register?invite={default_invite}")
        print(f"  - Acme Corp: /register?invite={acme_invite}")
        print("")
        print("Or register with tenant code:")
        print("  - Default Tenant code: default")
        print("  - Acme Corp code: acme")
        print("")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
