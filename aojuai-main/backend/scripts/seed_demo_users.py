"""
AOJU Backend - Demo Users & Teams Seed Script

创建演示用的团队结构和用户：

团队结构:
├── 总部 (headquarters)
│   ├── 技术部 (tech_dept)
│   │   ├── 前端组 (frontend_team)
│   │   └── 后端组 (backend_team)
│   └── 产品部 (product_dept)
│       └── 设计组 (design_team)

用户分配:
- 张总 (zhang_admin) - 租户管理员 - 总部
- 李经理 (li_manager) - 团队主管 - 技术部
- 王组长 (wang_leader) - 团队主管 - 前端组
- 赵工 (zhao_dev) - 团队成员 - 前端组
- 钱工 (qian_dev) - 普通员工 - 后端组
- 孙访客 (sun_guest) - 访客 - 总部
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import async_session_factory
from app.domain.teams.models import Team
from app.domain.users.models import User, UserTeam, UserRole
from app.domain.roles.models import Role
from app.core.security import hash_password


# Demo 团队结构
DEMO_TEAMS = [
    {"code": "headquarters", "name": "总部", "parent_code": None, "sort": 1},
    {"code": "tech_dept", "name": "技术部", "parent_code": "headquarters", "sort": 1},
    {"code": "product_dept", "name": "产品部", "parent_code": "headquarters", "sort": 2},
    {"code": "frontend_team", "name": "前端组", "parent_code": "tech_dept", "sort": 1},
    {"code": "backend_team", "name": "后端组", "parent_code": "tech_dept", "sort": 2},
    {"code": "design_team", "name": "设计组", "parent_code": "product_dept", "sort": 1},
]

# Demo 用户
DEMO_USERS = [
    {
        "username": "zhang_admin",
        "nickname": "张总",
        "email": "zhang@demo.com",
        "role_code": "tenant_admin",
        "team_code": "headquarters",
        "password": "Demo@123",
    },
    {
        "username": "li_manager",
        "nickname": "李经理",
        "email": "li@demo.com",
        "role_code": "team_manager",
        "team_code": "tech_dept",
        "password": "Demo@123",
    },
    {
        "username": "wang_leader",
        "nickname": "王组长",
        "email": "wang@demo.com",
        "role_code": "team_manager",
        "team_code": "frontend_team",
        "password": "Demo@123",
    },
    {
        "username": "zhao_dev",
        "nickname": "赵工",
        "email": "zhao@demo.com",
        "role_code": "team_member",
        "team_code": "frontend_team",
        "password": "Demo@123",
    },
    {
        "username": "qian_dev",
        "nickname": "钱工",
        "email": "qian@demo.com",
        "role_code": "staff",
        "team_code": "backend_team",
        "password": "Demo@123",
    },
    {
        "username": "sun_guest",
        "nickname": "孙访客",
        "email": "sun@demo.com",
        "role_code": "guest",
        "team_code": "headquarters",
        "password": "Demo@123",
    },
]


async def seed_demo_teams(db: AsyncSession, tenant_id: int) -> dict[str, int]:
    """创建 demo 团队，返回 code -> id 映射"""
    print("\n=== 创建 Demo 团队 ===\n")

    team_map: dict[str, int] = {}

    for team_data in DEMO_TEAMS:
        # 检查是否已存在
        stmt = select(Team).where(
            Team.tenant_id == tenant_id,
            Team.code == team_data["code"],
            Team.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            team_map[team_data["code"]] = existing.id
            print(f"  [已存在] {team_data['name']}")
            continue

        # 获取父级ID
        parent_id = None
        if team_data["parent_code"]:
            parent_id = team_map.get(team_data["parent_code"])

        team = Team(
            tenant_id=tenant_id,
            code=team_data["code"],
            name=team_data["name"],
            parent_id=parent_id,
            sort_order=team_data["sort"],
            status=1,  # ENABLED
        )
        db.add(team)
        await db.flush()

        team_map[team_data["code"]] = team.id
        indent = "  " if parent_id else ""
        print(f"  [创建] {indent}{team_data['name']}")

    await db.commit()
    return team_map


async def seed_demo_users(
    db: AsyncSession, tenant_id: int, team_map: dict[str, int]
) -> None:
    """创建 demo 用户"""
    print("\n=== 创建 Demo 用户 ===\n")

    # 获取角色映射
    stmt = select(Role).where(
        Role.tenant_id == tenant_id,
        Role.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    roles = result.scalars().all()
    role_map = {r.code: r.id for r in roles}

    for user_data in DEMO_USERS:
        # 检查是否已存在
        stmt = select(User).where(
            User.tenant_id == tenant_id,
            User.username == user_data["username"],
            User.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  [已存在] {user_data['nickname']} ({user_data['username']})")
            continue

        # 创建用户
        user = User(
            tenant_id=tenant_id,
            username=user_data["username"],
            nickname=user_data["nickname"],
            email=user_data["email"],
            password_hash=hash_password(user_data["password"]),
            status=1,  # ENABLED
        )
        db.add(user)
        await db.flush()

        # 关联角色
        role_id = role_map.get(user_data["role_code"])
        if role_id:
            user_role = UserRole(
                user_id=user.id,
                role_id=role_id,
                tenant_id=tenant_id,
            )
            db.add(user_role)

        # 关联团队
        team_id = team_map.get(user_data["team_code"])
        if team_id:
            user_team = UserTeam(
                user_id=user.id,
                team_id=team_id,
                tenant_id=tenant_id,
            )
            db.add(user_team)

        role_name = user_data["role_code"]
        team_name = user_data["team_code"]
        print(f"  [创建] {user_data['nickname']:6} | {role_name:15} | {team_name}")

    await db.commit()


async def show_summary(db: AsyncSession, tenant_id: int) -> None:
    """显示汇总"""
    print("\n" + "=" * 60)
    print("Demo 数据创建完成")
    print("=" * 60)

    print("\n登录账号 (密码统一: Demo@123):")
    print("-" * 50)
    print(f"{'用户名':15} | {'姓名':8} | {'角色':12} | {'数据范围'}")
    print("-" * 50)

    accounts = [
        ("zhang_admin", "张总", "租户管理员", "全部数据"),
        ("li_manager", "李经理", "团队主管", "技术部及下级"),
        ("wang_leader", "王组长", "团队主管", "前端组及下级"),
        ("zhao_dev", "赵工", "团队成员", "前端组"),
        ("qian_dev", "钱工", "普通员工", "仅自己"),
        ("sun_guest", "孙访客", "访客", "仅自己(只读)"),
    ]

    for username, name, role, scope in accounts:
        print(f"{username:15} | {name:8} | {role:12} | {scope}")


async def main():
    async with async_session_factory() as db:
        tenant_id = 1

        team_map = await seed_demo_teams(db, tenant_id)
        await seed_demo_users(db, tenant_id, team_map)
        await show_summary(db, tenant_id)


if __name__ == "__main__":
    asyncio.run(main())
