"""S0 RBAC + demo account bootstrap (separate from menu seed reconciler).

架构 seed.py 禁止演示业务数据；本模块供脚本 / 测试显式调用，幂等创建：
商家×2、订单客服 A、管理员、第二租户商家。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.models import RealphotosMerchantProfile
from app.capabilities.realphotos.permissions import (
    ROLE_ADMIN,
    ROLE_MERCHANT,
    ROLE_ORDER_SUPPORT,
    ROLE_TECH_SUPPORT,
)
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.core.security import hash_password
from app.domain.auth.models import Tenant
from app.domain.roles.models import Role
from app.domain.users.models import User, UserRole, UserStatus

DEFAULT_PASSWORD = "S0Test@123456"


@dataclass(frozen=True, slots=True)
class SeedAccount:
    username: str
    role_code: str
    tenant_code: str
    tenant_name: str
    nickname: str


S0_ACCOUNTS: tuple[SeedAccount, ...] = (
    SeedAccount("rp_merchant_a1", ROLE_MERCHANT, "rp-tenant-1", "蜜獾演示租户一", "商家甲"),
    SeedAccount("rp_merchant_a2", ROLE_MERCHANT, "rp-tenant-1", "蜜獾演示租户一", "商家乙"),
    SeedAccount(
        "rp_order_support", ROLE_ORDER_SUPPORT, "rp-platform", "平台运营租户", "订单客服A"
    ),
    SeedAccount("rp_admin", ROLE_ADMIN, "rp-platform", "平台运营租户", "平台管理员"),
    SeedAccount("rp_merchant_b1", ROLE_MERCHANT, "rp-tenant-2", "蜜獾演示租户二", "第二租户商家"),
)

ROLE_DEFS: tuple[tuple[str, str, str], ...] = (
    (ROLE_MERCHANT, "商家", "蜜獾原图商家岗位"),
    (ROLE_ORDER_SUPPORT, "订单客服A", "充值确认/拒单，不解冻不看业务原图"),
    (ROLE_ADMIN, "平台管理员", "蜜獾原图平台管理员"),
    (ROLE_TECH_SUPPORT, "技术客服", "S6 完整台；S0 仅登记角色码"),
)


def _with_realphotos_enabled(config: dict | None) -> dict:
    merged = dict(config or {})
    switches = dict(merged.get("feature_switches") or {})
    modules = dict(switches.get("modules") or {})
    modules["realphotos"] = True
    switches["modules"] = modules
    merged["feature_switches"] = switches
    return merged


async def _ensure_tenant(db: AsyncSession, *, code: str, name: str) -> Tenant:
    result = await db.execute(
        select(Tenant).where(Tenant.code == code, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(name=name, code=code, is_active=True, config=_with_realphotos_enabled({}))
        db.add(tenant)
        await db.flush()
    else:
        tenant.config = _with_realphotos_enabled(tenant.config if isinstance(tenant.config, dict) else {})
        await db.flush()
    return tenant


async def _ensure_role(db: AsyncSession, *, tenant_id: int, code: str, name: str, description: str) -> Role:
    result = await db.execute(
        select(Role).where(
            Role.tenant_id == int(tenant_id),
            Role.code == code,
            Role.deleted_at.is_(None),
        )
    )
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(
            tenant_id=int(tenant_id),
            code=code,
            name=name,
            description=description,
            is_system=True,
            is_active=True,
            data_range=4,
            data_permissions=7,
        )
        db.add(role)
        await db.flush()
    return role


async def _ensure_user(
    db: AsyncSession,
    *,
    tenant_id: int,
    username: str,
    nickname: str,
    role: Role,
) -> User:
    result = await db.execute(
        select(User).where(User.username == username, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            tenant_id=int(tenant_id),
            username=username,
            password_hash=hash_password(DEFAULT_PASSWORD),
            nickname=nickname,
            status=int(UserStatus.ENABLED),
        )
        db.add(user)
        await db.flush()
    else:
        user.tenant_id = int(tenant_id)
        user.status = int(UserStatus.ENABLED)
        await db.flush()

    link = await db.execute(
        select(UserRole).where(
            UserRole.user_id == int(user.id),
            UserRole.role_id == int(role.id),
            UserRole.tenant_id == int(tenant_id),
        )
    )
    if link.scalar_one_or_none() is None:
        db.add(
            UserRole(
                tenant_id=int(tenant_id),
                user_id=int(user.id),
                role_id=int(role.id),
            )
        )
        await db.flush()

    profile = await db.execute(
        select(RealphotosMerchantProfile).where(
            RealphotosMerchantProfile.tenant_id == int(tenant_id),
            RealphotosMerchantProfile.user_id == int(user.id),
            RealphotosMerchantProfile.deleted_at.is_(None),
        )
    )
    if profile.scalar_one_or_none() is None:
        db.add(
            RealphotosMerchantProfile(
                tenant_id=int(tenant_id),
                user_id=int(user.id),
                display_name=nickname,
            )
        )
        await db.flush()
    return user


async def bootstrap_s0_accounts(db: AsyncSession) -> dict[str, dict]:
    """幂等创建 S0 验收账号与角色；返回 username -> 摘要。"""
    tenants: dict[str, Tenant] = {}
    for account in S0_ACCOUNTS:
        if account.tenant_code not in tenants:
            tenants[account.tenant_code] = await _ensure_tenant(
                db, code=account.tenant_code, name=account.tenant_name
            )

    # 每个租户确保四类角色码存在（技术客服仅登记）
    roles_by_tenant: dict[int, dict[str, Role]] = {}
    for tenant in tenants.values():
        roles_by_tenant[int(tenant.id)] = {}
        for code, name, description in ROLE_DEFS:
            roles_by_tenant[int(tenant.id)][code] = await _ensure_role(
                db,
                tenant_id=int(tenant.id),
                code=code,
                name=name,
                description=description,
            )
        await RealphotosCreditService(db).get_or_create_account(tenant_id=int(tenant.id))

    summary: dict[str, dict] = {}
    for account in S0_ACCOUNTS:
        tenant = tenants[account.tenant_code]
        role = roles_by_tenant[int(tenant.id)][account.role_code]
        user = await _ensure_user(
            db,
            tenant_id=int(tenant.id),
            username=account.username,
            nickname=account.nickname,
            role=role,
        )
        summary[account.username] = {
            "userId": str(int(user.id)),
            "tenantId": str(int(tenant.id)),
            "tenantCode": account.tenant_code,
            "roleCode": account.role_code,
        }
    await db.commit()
    return summary
