"""公开留言 → 工单：装了 CMS 与没装 CMS 两种情形都要成立。

这条联动的方向是 `cms_public ──▶ support.bridge`，且必须是**可选**的：
- 工单包没装：留言照样落库，只是不开单；support 一行代码都不被 import。
- 工单包装了但该租户关了：同上（不能变成留言接口的 403）。
- 两边都开：留言与工单**都保留**，靠 related_id 互相定位。

反过来，support 在没有 CMS 的部署里必须完整可用——它自己就有匿名入口。
"""

from __future__ import annotations

import sys

import pytest

from app.api.v1.endpoints import cms_public
from app.capabilities.support.constants import PUBLIC_CONTACT_RELATED_TYPE
from app.capabilities.support.service import SupportService
from app.core import feature_switches

TENANT = 4001
SUPPORT_MODULE_PREFIX = "app.capabilities.support"


class _Contact:
    name = "Dana"
    email = "dana@example.com"
    message = "please call me back"
    company = "Acme"
    source_page = "/pricing"


def _install(codes: str) -> None:
    feature_switches.settings.AOJ_ENABLED_MODULES = codes
    feature_switches.clear_module_install_caches()


async def _seed_tenant(db, *, modules: dict[str, bool]) -> None:
    from app.domain.auth.models import Tenant

    db.add(
        Tenant(
            id=TENANT,
            name="bridge-tenant",
            code=f"bridge{TENANT}",
            is_active=True,
            config={"feature_switches": {"modules": modules}},
        )
    )
    await db.flush()


@pytest.mark.asyncio
async def test_bridge_opens_a_ticket_when_support_is_installed_and_enabled(db) -> None:
    _install("support,public_site")
    await _seed_tenant(db, modules={"support": True, "public_site": True})

    ticket = await cms_public._bridge_contact_to_support(
        db, tenant_id=TENANT, data=_Contact(), submission_id=77
    )

    assert ticket is not None
    assert ticket.related_type == PUBLIC_CONTACT_RELATED_TYPE
    assert ticket.related_id == "77", "留言与工单要能互相定位"
    assert ticket.extra["submissionId"] == 77
    assert "dana@example.com" in ticket.description
    assert ticket.extra["contact"]["company"] == "Acme"


@pytest.mark.asyncio
async def test_bridge_is_a_no_op_when_the_tenant_disabled_support(db) -> None:
    _install("support,public_site")
    await _seed_tenant(db, modules={"support": False, "public_site": True})

    ticket = await cms_public._bridge_contact_to_support(
        db, tenant_id=TENANT, data=_Contact(), submission_id=78
    )

    assert ticket is None, "别人的模块关着不该让留言接口报错，只是不开单"


@pytest.mark.asyncio
async def test_bridge_never_imports_support_when_it_is_not_installed(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install("public_site")
    await _seed_tenant(db, modules={"public_site": True})
    for name in [name for name in sys.modules if name.startswith(SUPPORT_MODULE_PREFIX)]:
        monkeypatch.delitem(sys.modules, name, raising=False)

    ticket = await cms_public._bridge_contact_to_support(
        db, tenant_id=TENANT, data=_Contact(), submission_id=79
    )

    assert ticket is None
    assert not [name for name in sys.modules if name.startswith(SUPPORT_MODULE_PREFIX)], (
        "工单包没装时连 import 都不该发生——import 一个不在磁盘上的可选包会让公开留言接口 500"
    )


@pytest.mark.asyncio
async def test_support_works_without_the_cms_module_installed(db) -> None:
    """没有公开站/CMS 的部署里，工单包必须整包可用（它自己就有匿名入口）。"""
    _install("support")
    assert feature_switches.is_module_installed("public_site") is False

    service = SupportService(db)
    ticket = await service.create_anonymous_ticket(
        tenant_id=TENANT, subject="no cms here", description="still works"
    )

    assert ticket.id is not None
    _, total = await service.list_tickets(tenant_id=TENANT, page=1, page_size=20)
    assert total == 1


@pytest.mark.asyncio
async def test_support_declares_no_dependency_on_the_cms_module() -> None:
    from app.capabilities.support import CAPABILITY

    assert "public_site" not in CAPABILITY.dependencies
    assert "cms" not in CAPABILITY.dependencies
    assert CAPABILITY.dependencies == ("core",)
