"""
AOJU Backend - Demo Roles Seed Script

预设角色体系：
1. 租户管理员 (tenant_admin) - 管理本租户所有数据
2. 团队主管 (team_manager) - 管理本团队及下级团队
3. 团队成员 (team_member) - 仅操作本团队数据
4. 普通员工 (staff) - 仅操作自己的数据
5. 访客 (guest) - 只读权限

数据权限范围 (DataRange):
- SELF_ONLY = 0    仅本人数据
- OWN_TEAM = 1     本团队数据
- TEAM_AND_BELOW = 2  本团队及以下
- CUSTOM_TEAMS = 3    自定义团队
- ALL = 4             全部数据

数据操作权限 (DataPermission):
- READ = 1   只读
- EDIT = 2   编辑
- DELETE = 4 删除
- 组合: 1=只读, 3=读+编辑, 7=读+编辑+删除
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.menus.models import Menu
from app.domain.roles.models import Role, RoleMenu
from app.infrastructure.database.session import async_session_factory

# Demo 角色定义
DEMO_ROLES = [
    {
        "code": "tenant_admin",
        "name": "租户管理员",
        "description": "管理本租户所有用户、角色、团队，拥有全部数据权限",
        "data_range": 4,  # ALL
        "data_permissions": 7,  # READ + EDIT + DELETE
        "is_system": True,
        "menu_perms": [
            "user:list", "user:read", "user:create", "user:update", "user:delete",
            "user:audit", "user:reset-password",
            "role:list", "role:read", "role:create", "role:update", "role:delete",
            "menu:list", "menu:read",
            "team:list", "team:read", "team:create", "team:update", "team:delete",
        ],
    },
    {
        "code": "team_manager",
        "name": "团队主管",
        "description": "管理本团队及下级团队的用户和数据",
        "data_range": 2,  # TEAM_AND_BELOW
        "data_permissions": 7,  # READ + EDIT + DELETE
        "is_system": False,
        "menu_perms": [
            "user:list", "user:read", "user:create", "user:update",
            "team:list", "team:read", "team:create", "team:update",
        ],
    },
    {
        "code": "team_member",
        "name": "团队成员",
        "description": "查看和编辑本团队数据，不能删除",
        "data_range": 1,  # OWN_TEAM
        "data_permissions": 3,  # READ + EDIT
        "is_system": False,
        "menu_perms": [
            "user:list", "user:read",
            "team:list", "team:read",
        ],
    },
    {
        "code": "staff",
        "name": "普通员工",
        "description": "仅操作自己创建的数据",
        "data_range": 0,  # SELF_ONLY
        "data_permissions": 3,  # READ + EDIT
        "is_system": False,
        "menu_perms": [
            "user:read",
        ],
    },
    {
        "code": "guest",
        "name": "访客",
        "description": "只读权限，仅查看自己相关的数据",
        "data_range": 0,  # SELF_ONLY
        "data_permissions": 1,  # READ only
        "is_system": False,
        "menu_perms": [],
    },
]


async def get_menu_ids_by_perms(db: AsyncSession, tenant_id: int, perms: list[str]) -> list[int]:
    """根据权限码获取菜单ID列表"""
    if not perms:
        return []

    stmt = select(Menu.id).where(
        Menu.tenant_id == tenant_id,
        Menu.perms.in_(perms),
        Menu.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def seed_demo_roles(db: AsyncSession, tenant_id: int = 1):
    """创建 demo 角色"""
    print(f"\n=== 为租户 {tenant_id} 创建 Demo 角色 ===\n")

    created_count = 0
    updated_count = 0

    for role_data in DEMO_ROLES:
        # 检查角色是否已存在
        stmt = select(Role).where(
            Role.tenant_id == tenant_id,
            Role.code == role_data["code"],
            Role.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        existing_role = result.scalar_one_or_none()

        if existing_role:
            # 更新现有角色
            existing_role.name = role_data["name"]
            existing_role.description = role_data["description"]
            existing_role.data_range = role_data["data_range"]
            existing_role.data_permissions = role_data["data_permissions"]
            existing_role.is_system = role_data["is_system"]
            role = existing_role
            updated_count += 1
            print(f"  [更新] {role_data['code']:15} - {role_data['name']}")
        else:
            # 创建新角色
            role = Role(
                tenant_id=tenant_id,
                code=role_data["code"],
                name=role_data["name"],
                description=role_data["description"],
                data_range=role_data["data_range"],
                data_permissions=role_data["data_permissions"],
                is_system=role_data["is_system"],
                is_active=True,
            )
            db.add(role)
            created_count += 1
            print(f"  [创建] {role_data['code']:15} - {role_data['name']}")

        await db.flush()

        # 关联菜单权限
        menu_ids = await get_menu_ids_by_perms(db, tenant_id, role_data["menu_perms"])

        # 删除旧的菜单关联
        await db.execute(
            text("DELETE FROM role_menus WHERE role_id = :role_id"),
            {"role_id": role.id}
        )

        # 创建新的菜单关联
        for menu_id in menu_ids:
            role_menu = RoleMenu(role_id=role.id, menu_id=menu_id, tenant_id=tenant_id)
            db.add(role_menu)

        print(f"         关联菜单: {len(menu_ids)} 个")

    await db.commit()

    print("\n=== 完成 ===")
    print(f"  创建: {created_count} 个角色")
    print(f"  更新: {updated_count} 个角色")


async def show_roles_summary(db: AsyncSession, tenant_id: int = 1):
    """显示角色汇总"""
    print(f"\n=== 租户 {tenant_id} 角色列表 ===\n")

    stmt = select(Role).where(
        Role.tenant_id == tenant_id,
        Role.deleted_at.is_(None),
    ).order_by(Role.id)

    result = await db.execute(stmt)
    roles = result.scalars().all()

    data_range_names = {
        0: "仅本人",
        1: "本团队",
        2: "团队及下级",
        3: "自定义团队",
        4: "全部数据",
    }

    perm_names = {
        1: "只读",
        3: "读+编辑",
        7: "读+编辑+删除",
    }

    print(f"{'ID':>3} | {'代码':15} | {'名称':12} | {'数据范围':12} | {'操作权限':12}")
    print("-" * 70)

    for role in roles:
        dr = data_range_names.get(role.data_range, str(role.data_range))
        dp = perm_names.get(role.data_permissions, str(role.data_permissions))
        print(f"{role.id:>3} | {role.code:15} | {role.name:12} | {dr:12} | {dp:12}")


async def main():
    async with async_session_factory() as db:
        await seed_demo_roles(db, tenant_id=1)
        await show_roles_summary(db, tenant_id=1)


if __name__ == "__main__":
    asyncio.run(main())
