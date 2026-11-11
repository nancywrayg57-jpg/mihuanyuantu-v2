"""REMAIN-GAP W1: base login bypass closed + asset server pagination."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.capabilities.realphotos.constants import ASSET_PAGE_SIZE_DEFAULT, ASSET_PAGE_SIZE_MAX
from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
from app.core.exceptions import AOJUException


def _jpeg(color: tuple[int, int, int] = (40, 80, 120)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1280, 960), color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_r1_base_login_blocked_for_merchant(db) -> None:
    from fastapi import FastAPI, Request
    from httpx import ASGITransport, AsyncClient

    from app.api import deps
    from app.api.v1.endpoints import auth as auth_ep
    from app.core.response import AppORJSONResponse

    await bootstrap_s0_accounts(db)

    app = FastAPI()
    app.include_router(auth_ep.router, prefix="/api/v1/auth")

    @app.exception_handler(AOJUException)
    async def _aoju_handler(_request: Request, exc: AOJUException):
        return AppORJSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    async def override_db():
        yield db

    app.dependency_overrides[deps.get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "rp_merchant_a1", "password": DEFAULT_PASSWORD},
        )
    assert response.status_code == 403, response.text
    body = response.json()
    assert body.get("code") == "AUTH_CAPTCHA_REQUIRED"
    assert "/api/v1/realphotos/auth/login" in str(body.get("details") or {})


@pytest.mark.asyncio
async def test_r1_helper_raises_for_rp_roles(db) -> None:
    from sqlalchemy import select

    from app.api.v1.endpoints.auth import _reject_realphotos_roles_on_base_login
    from app.domain.users.models import User

    summary = await bootstrap_s0_accounts(db)
    user_id = int(summary["rp_merchant_a1"]["userId"])
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one()
    with pytest.raises(AOJUException) as blocked:
        await _reject_realphotos_roles_on_base_login(db=db, user=user, client_ip="test")
    assert blocked.value.code == "AUTH_CAPTCHA_REQUIRED"
    assert blocked.value.status_code == 403


@pytest.mark.asyncio
async def test_r2_asset_server_pagination(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant_id = int(summary["rp_merchant_a1"]["tenantId"])
    owner_id = int(summary["rp_merchant_a1"]["userId"])
    service = RealphotosS1Service(db)
    for i in range(25):
        await service.upload(
            tenant_id=tenant_id,
            owner_account_id=owner_id,
            data=_jpeg((i % 180, 40, 80)),
        )
    await db.flush()
    growth = RealphotosGrowthService(db)
    page1, total, page_n, size = await growth.list_assets_page(
        tenant_id=tenant_id,
        owner_account_id=owner_id,
        page=1,
        page_size=ASSET_PAGE_SIZE_DEFAULT,
    )
    assert total >= 25
    assert page_n == 1
    assert size == ASSET_PAGE_SIZE_DEFAULT
    assert len(page1) == ASSET_PAGE_SIZE_DEFAULT
    page2, total2, page_n2, _ = await growth.list_assets_page(
        tenant_id=tenant_id,
        owner_account_id=owner_id,
        page=2,
        page_size=ASSET_PAGE_SIZE_DEFAULT,
    )
    assert total2 == total
    assert page_n2 == 2
    assert len(page2) >= 5
    assert {int(a.id) for a in page1}.isdisjoint({int(a.id) for a in page2})
    _, _, _, clamped = await growth.list_assets_page(
        tenant_id=tenant_id,
        owner_account_id=owner_id,
        page=1,
        page_size=10_000,
    )
    assert clamped == ASSET_PAGE_SIZE_MAX
