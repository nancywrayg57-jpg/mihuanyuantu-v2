"""S3 security regressions: challenge consume, lock persistence, weak password."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import deps
from app.capabilities.realphotos.api import auth as rp_auth
from app.capabilities.realphotos.constants import LOCKOUT_MINUTES, MAX_FAILED_LOGINS, allow_dev_captcha
from app.capabilities.realphotos.models import RealphotosAuthChallenge, RealphotosAuthGuard
from app.capabilities.realphotos.services.auth_service import RealphotosAuthService
from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
from app.core.exceptions import AOJUException, BusinessError, TooManyRequestsError
from app.core.response import AppORJSONResponse
from app.domain.users.schemas import _validate_password_strength


@pytest.mark.asyncio
async def test_wrong_captcha_consumes_challenge(db) -> None:
    await bootstrap_s0_accounts(db)
    auth = RealphotosAuthService(db)
    challenge = await auth.create_challenge(client_key="sec-a01")
    cid = challenge["challengeId"]
    with pytest.raises(BusinessError):
        await auth.login(
            username="rp_merchant_a1",
            password=DEFAULT_PASSWORD,
            challenge_id=cid,
            challenge_code="000000",
        )
    row = (
        await db.execute(
            select(RealphotosAuthChallenge).where(
                RealphotosAuthChallenge.challenge_public_id == cid
            )
        )
    ).scalar_one()
    assert row.consumed_at is not None
    with pytest.raises(BusinessError) as reused:
        await auth.login(
            username="rp_merchant_a1",
            password=DEFAULT_PASSWORD,
            challenge_id=cid,
            challenge_code=str(challenge.get("devCode") or "111111"),
        )
    assert "已使用" in reused.value.message or reused.value.code == "INPUT_INVALID"


@pytest.mark.asyncio
async def test_wrong_password_commit_survives_rollback_semantics(db) -> None:
    """SEC-A00：模拟 get_db——失败后先 commit 再抛错，回滚不得抹掉副作用。"""
    from app.core.exceptions import UnauthorizedError

    assert allow_dev_captcha()
    await bootstrap_s0_accounts(db)
    auth = RealphotosAuthService(db)
    challenge = await auth.create_challenge(client_key="sec-a00")
    try:
        await auth.login(
            username="rp_merchant_a1",
            password="WrongPass@999",
            challenge_id=challenge["challengeId"],
            challenge_code=challenge["devCode"],
        )
        raise AssertionError("expected UnauthorizedError")
    except UnauthorizedError:
        await db.commit()

    # 新查询：验证码已消费、失败计数已落库
    row = (
        await db.execute(
            select(RealphotosAuthChallenge).where(
                RealphotosAuthChallenge.challenge_public_id == challenge["challengeId"]
            )
        )
    ).scalar_one()
    assert row.consumed_at is not None
    guard = (
        await db.execute(
            select(RealphotosAuthGuard).where(
                RealphotosAuthGuard.username_normalized == "rp_merchant_a1"
            )
        )
    ).scalar_one()
    assert int(guard.failed_count or 0) >= 1


@pytest.mark.asyncio
async def test_login_http_body_omits_tokens(db) -> None:
    """SEC-A05：成功登录 JSON 不含 access/refresh，仅 Cookie。"""
    assert allow_dev_captcha()
    await bootstrap_s0_accounts(db)

    async def override_db():
        yield db

    app = FastAPI()
    app.include_router(rp_auth.router, prefix="/api/v1/realphotos")

    @app.exception_handler(AOJUException)
    async def _aoju_handler(_request: Request, exc: AOJUException):
        return AppORJSONResponse(
            status_code=exc.status_code,
            content={"success": False, "code": exc.code, "message": exc.message, "details": exc.details},
        )

    app.dependency_overrides[deps.get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ch = await client.post("/api/v1/realphotos/auth/challenges", json={"clientKey": "sec-a05"})
        data = ch.json()["data"]
        ok = await client.post(
            "/api/v1/realphotos/auth/login",
            json={
                "username": "rp_merchant_a1",
                "password": DEFAULT_PASSWORD,
                "challengeId": data["challengeId"],
                "challengeCode": data["devCode"],
            },
        )
        assert ok.status_code == 200, ok.text
        payload = ok.json()["data"]
        assert "accessToken" not in payload
        assert "refreshToken" not in payload
        assert payload.get("authMode") == "cookie"
        assert "set-cookie" in {k.lower() for k in ok.headers}


@pytest.mark.asyncio
async def test_lockout_raises_429(db) -> None:
    from app.core.exceptions import UnauthorizedError

    await bootstrap_s0_accounts(db)
    auth = RealphotosAuthService(db)
    for i in range(MAX_FAILED_LOGINS - 1):
        ch = await auth.create_challenge(client_key=f"lock-{i}")
        with pytest.raises(UnauthorizedError):
            await auth.login(
                username="rp_merchant_a1",
                password="WrongPass@999",
                challenge_id=ch["challengeId"],
                challenge_code=ch["devCode"],
            )
    ch = await auth.create_challenge(client_key="lock-trip")
    with pytest.raises(TooManyRequestsError) as locked:
        await auth.login(
            username="rp_merchant_a1",
            password="WrongPass@999",
            challenge_id=ch["challengeId"],
            challenge_code=ch["devCode"],
        )
    assert locked.value.status_code == 429
    assert int(locked.value.details.get("retryAfterSeconds") or 0) >= 1
    assert LOCKOUT_MINUTES == 15
    ch2 = await auth.create_challenge(client_key="lock-final")
    with pytest.raises(TooManyRequestsError):
        await auth.login(
            username="rp_merchant_a1",
            password=DEFAULT_PASSWORD,
            challenge_id=ch2["challengeId"],
            challenge_code=ch2["devCode"],
        )


def test_password_requires_three_classes() -> None:
    with pytest.raises(ValueError):
        _validate_password_strength("Abcdefgh")  # letters only
    with pytest.raises(ValueError):
        _validate_password_strength("abcdefg1")  # no symbol
    with pytest.raises(ValueError):
        _validate_password_strength("abcdefg!", username="abcdefg")  # contains username
    assert _validate_password_strength("GoodPass@1") == "GoodPass@1"

@pytest.mark.asyncio
async def test_logout_revokes_access_token() -> None:
    """SEC-A03：吊销后同 jti 的 access 不可再用。"""
    from app.core.security import create_access_token, decode_token
    from app.core.token_revocation import is_token_revoked, revoke_token

    token = create_access_token(subject=42, extra_data={"tenant_id": 1})
    assert await is_token_revoked(token) is False
    await revoke_token(token)
    assert await is_token_revoked(token) is True
    payload = decode_token(token)
    assert payload.get("jti")


def test_rp_abs_exp_enforced() -> None:
    """SEC-A07：越过绝对会话边界拒绝。"""
    from datetime import UTC, datetime, timedelta

    from app.core.exceptions import UnauthorizedError
    from app.core.security import assert_absolute_session_valid

    assert_absolute_session_valid({})
    assert_absolute_session_valid({"rp_abs_exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp())})
    with pytest.raises(UnauthorizedError):
        assert_absolute_session_valid({"rp_abs_exp": int((datetime.now(UTC) - timedelta(seconds=5)).timestamp())})


def test_jwt_secret_gate_production(monkeypatch) -> None:
    """SEC-A08：生产默认占位密钥拒绝启动。"""
    from app.core import security as sec
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", sec.DEFAULT_JWT_SECRET_PLACEHOLDER)
    with pytest.raises(RuntimeError):
        sec.assert_jwt_secret_safe_for_env()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "prod-not-default-secret-value-32b")
    sec.assert_jwt_secret_safe_for_env()
