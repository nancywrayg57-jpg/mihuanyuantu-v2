"""FR-001 / architecture §9.2: realphotos merchant self-registration."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import deps
from app.capabilities.realphotos.api import auth as rp_auth
from app.capabilities.realphotos.constants import allow_dev_captcha
from app.capabilities.realphotos.models import RealphotosMerchantProfile
from app.capabilities.realphotos.permissions import ROLE_MERCHANT
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.core.exceptions import AOJUException
from app.core.response import AppORJSONResponse
from app.domain.auth.models import Tenant
from app.domain.users.models import User, UserRole


def _app_with_auth(db) -> FastAPI:
    app = FastAPI()
    app.include_router(rp_auth.router, prefix="/api/v1/realphotos")

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
    return app


@pytest.mark.asyncio
async def test_register_creates_tenant_merchant_and_allows_login(db) -> None:
    assert allow_dev_captcha(), "unit tests expect plaintext captcha under allow_dev_captcha"
    await bootstrap_s0_accounts(db)
    app = _app_with_auth(db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        challenge = await client.post("/api/v1/realphotos/auth/challenges", json={"clientKey": "ut-reg"})
        assert challenge.status_code == 200, challenge.text
        body = challenge.json()["data"]
        challenge_id = body["challengeId"]
        code = body["devCode"]
        assert code

        username = "new_merchant_ut1"
        password = "RegTest@123456"
        registered = await client.post(
            "/api/v1/realphotos/auth/register",
            json={
                "username": username,
                "password": password,
                "nickname": "新商家",
                "challengeId": challenge_id,
                "challengeCode": code,
            },
        )
        assert registered.status_code == 200, registered.text
        payload = registered.json()["data"]
        assert payload["username"] == username
        assert payload["tenantCode"] == f"m-{username}"
        assert payload["roleCode"] == ROLE_MERCHANT
        assert payload["requireAudit"] is False

        tenant = (
            await db.execute(select(Tenant).where(Tenant.code == payload["tenantCode"]))
        ).scalar_one()
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()
        assert int(user.tenant_id) == int(tenant.id)
        assert int(user.status) == 1
        role_link = (
            await db.execute(
                select(UserRole).where(
                    UserRole.user_id == int(user.id),
                    UserRole.tenant_id == int(tenant.id),
                )
            )
        ).scalar_one()
        assert role_link is not None
        profile = (
            await db.execute(
                select(RealphotosMerchantProfile).where(
                    RealphotosMerchantProfile.user_id == int(user.id),
                    RealphotosMerchantProfile.tenant_id == int(tenant.id),
                )
            )
        ).scalar_one()
        assert profile.display_name == "新商家"

        challenge2 = await client.post("/api/v1/realphotos/auth/challenges", json={"clientKey": "ut-login"})
        login_body = challenge2.json()["data"]
        logged_in = await client.post(
            "/api/v1/realphotos/auth/login",
            json={
                "username": username,
                "password": password,
                "challengeId": login_body["challengeId"],
                "challengeCode": login_body["devCode"],
            },
        )
        assert logged_in.status_code == 200, logged_in.text
        assert logged_in.json()["data"]["username"] == username
        assert ROLE_MERCHANT in (logged_in.json()["data"].get("roles") or [])


@pytest.mark.asyncio
async def test_register_rejects_duplicate_username(db) -> None:
    assert allow_dev_captcha()
    await bootstrap_s0_accounts(db)
    app = _app_with_auth(db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        challenge = await client.post("/api/v1/realphotos/auth/challenges", json={})
        body = challenge.json()["data"]
        response = await client.post(
            "/api/v1/realphotos/auth/register",
            json={
                "username": "rp_merchant_a1",
                "password": "RegTest@123456",
                "challengeId": body["challengeId"],
                "challengeCode": body["devCode"],
            },
        )
    assert response.status_code >= 400
    assert "已存在" in (response.json().get("message") or "")


@pytest.mark.asyncio
async def test_register_requires_captcha(db) -> None:
    await bootstrap_s0_accounts(db)
    app = _app_with_auth(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/realphotos/auth/register",
            json={
                "username": "need_captcha_user",
                "password": "RegTest@123456",
                "challengeId": "missing",
                "challengeCode": "000000",
            },
        )
    assert response.status_code >= 400
    assert "验证码" in (response.json().get("message") or "")
