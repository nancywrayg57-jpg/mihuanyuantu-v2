"""S4 security regressions: tech readonly, role ceiling, owner delete."""

from __future__ import annotations

import pytest

from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT, ROLE_TECH_SUPPORT
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
from app.core.exceptions import ForbiddenError, NotFoundError
from PIL import Image
import io


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1200, 900), (40, 80, 120)).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_tech_cannot_create_user_or_set_admin_role(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    ops = RealphotosOpsService(db)
    tech = int(summary["rp_tech_support"]["userId"])
    admin = int(summary["rp_admin"]["userId"])
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    with pytest.raises(ForbiddenError):
        await ops.create_user(
            actor_role_codes={ROLE_TECH_SUPPORT},
            operator_user_id=tech,
            tenant_id=tenant,
            username="sec_tech_create",
            password="SecUser@123456",
            role_code=ROLE_MERCHANT,
        )
    created = await ops.create_user(
        actor_role_codes={ROLE_ADMIN},
        operator_user_id=admin,
        tenant_id=tenant,
        username="sec_admin_create",
        password="SecUser@123456",
        role_code=ROLE_MERCHANT,
    )
    with pytest.raises(ForbiddenError):
        await ops.set_roles(
            actor_role_codes={ROLE_TECH_SUPPORT},
            operator_user_id=tech,
            tenant_id=tenant,
            user_id=int(created["id"]),
            role_codes=[ROLE_ADMIN],
        )


@pytest.mark.asyncio
async def test_asset_delete_requires_owner(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    owner = int(summary["rp_merchant_a1"]["userId"])
    other = int(summary["rp_merchant_a2"]["userId"])
    # a2 may be another tenant — use same tenant second user if present
    svc = RealphotosS1Service(db)
    asset = await svc.upload(tenant_id=tenant, owner_account_id=owner, data=_jpeg())
    with pytest.raises(NotFoundError):
        await svc.soft_delete_asset(
            tenant_id=tenant,
            asset_id=int(asset.id),
            owner_account_id=other if other != owner else owner + 999999,
        )
    await svc.soft_delete_asset(
        tenant_id=tenant,
        asset_id=int(asset.id),
        owner_account_id=owner,
    )


@pytest.mark.asyncio
async def test_adjust_credits_requires_tenant_user_bind(db) -> None:
    """SEC-C06：tenantId 与 userId 必须同属一租户。"""
    summary = await bootstrap_s0_accounts(db)
    ops = RealphotosOpsService(db)
    admin = int(summary["rp_admin"]["userId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    wrong_tenant = int(summary["rp_admin"]["tenantId"])
    if wrong_tenant == int(summary["rp_merchant_a1"]["tenantId"]):
        wrong_tenant = wrong_tenant + 999001
    with pytest.raises(ForbiddenError):
        await ops.adjust_credits(
            actor_role_codes={ROLE_ADMIN},
            operator_user_id=admin,
            tenant_id=wrong_tenant,
            user_id=user,
            delta=1,
            reason="sec-c06",
            event_key="sec-c06-mismatch",
        )
