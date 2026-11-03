"""权限守卫真的会拒绝——静态"每条路由都挂了 checker"不等于"checker 会拦人"。

两层闸门各测一次：
1. 租户模块开关：包装着但该租户没开 support => 403（模块已关闭）
2. 角色权限：租户开着但用户没有该权限码 => 403
"""

from __future__ import annotations

import pytest

from app.api.deps import PermissionChecker
from app.capabilities.support.permissions import MANAGE, READ
from app.core import feature_switches
from app.core.exceptions import ForbiddenError

TENANT = 4201


def _install(codes: str) -> None:
    feature_switches.settings.AOJ_ENABLED_MODULES = codes
    feature_switches.clear_module_install_caches()


async def _seed(db, *, support_enabled: bool, superuser: bool = False):
    from app.domain.auth.models import Tenant
    from app.domain.users.models import User

    db.add(
        Tenant(
            id=TENANT,
            name="perm-tenant",
            code=f"perm{TENANT}",
            is_active=True,
            config={"feature_switches": {"modules": {"support": support_enabled}}},
        )
    )
    user = User(
        id=771,
        tenant_id=TENANT,
        username="agent",
        password_hash="x",
        is_superuser=superuser,
        status=1,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_tenant_switch_off_blocks_even_a_granted_permission(db) -> None:
    _install("support")
    user = await _seed(db, support_enabled=False)

    with pytest.raises(ForbiddenError, match="模块已关闭"):
        await PermissionChecker([READ])(current_user=user, db=db)


@pytest.mark.asyncio
async def test_user_without_the_permission_is_rejected(db) -> None:
    _install("support")
    user = await _seed(db, support_enabled=True)

    with pytest.raises(ForbiddenError):
        await PermissionChecker([MANAGE])(current_user=user, db=db)


@pytest.mark.asyncio
async def test_superuser_passes_every_checker(db) -> None:
    _install("support")
    user = await _seed(db, support_enabled=True, superuser=True)

    assert await PermissionChecker([MANAGE])(current_user=user, db=db) is None


def test_permission_prefix_resolves_back_to_this_module() -> None:
    """权限前缀映射是模块开关的依据：解析不到模块，PermissionChecker 就不会查开关。"""
    _install("support")
    assert feature_switches.resolve_module_from_permission(MANAGE) == "support"
    assert feature_switches.resolve_module_from_permission(READ) == "support"
