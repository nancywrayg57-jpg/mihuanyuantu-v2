from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.api.v1.endpoints import auth
from app.domain.users.models import UserStatus


def _build_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        tenant_id=7,
        username="admin",
        nickname="Admin",
        avatar="",
        password_hash="hashed-password",
        status=UserStatus.ENABLED,
        is_active=True,
        is_superuser=True,
        roles=[],
        failed_login_count=0,
    )


def _build_auth_app(
    *,
    current_user_factory: Callable[[], Any] | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")

    async def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[deps.get_db] = override_db

    if current_user_factory is not None:
        async def override_current_user():
            return current_user_factory()

        app.dependency_overrides[deps.get_current_user] = override_current_user

    return app


def _install_auth_service_mocks(monkeypatch: pytest.MonkeyPatch, *, user: SimpleNamespace) -> None:
    class _FakeUserService:
        def __init__(self, db: Any) -> None:
            self.db = db

        async def get_one(self, **kwargs: Any) -> SimpleNamespace | None:
            assert kwargs.get("username") == user.username
            return user

        async def record_login_success(self, current_user: SimpleNamespace) -> None:
            assert current_user is user

        async def get_user_by_id_any_tenant(self, user_id: int) -> SimpleNamespace | None:
            return user if int(user_id) == int(user.id) else None

        async def get_user_role_codes(self, user_id: int, tenant_id: int | None = None) -> list[str]:
            # 平台超管无 rp_* 岗位：允许底座登录；蜜獾业务角色由专项单测覆盖旁路关闭
            return []

    class _FakeInvitationService:
        def __init__(self, db: Any) -> None:
            self.db = db

        async def process_due_rewards(self, *, tenant_id: int, user_id: int) -> None:
            assert tenant_id == user.tenant_id
            assert user_id == user.id

    async def _fake_build_auth_session_payload(*, db: Any, user: Any, expires: datetime | None) -> dict[str, Any]:
        assert db is not None
        assert user is not None
        return {
            "avatar": user.avatar,
            "username": user.username,
            "nickname": user.nickname,
            "roles": ["superuser"],
            "permissions": ["system:manage"],
            "isSuperuser": True,
            "mustCompleteProfile": False,
            "expires": expires,
            "authMode": "cookie",
        }

    monkeypatch.setattr(auth, "UserService", _FakeUserService)
    monkeypatch.setattr(auth, "InvitationService", _FakeInvitationService)
    monkeypatch.setattr(auth, "_build_auth_session_payload", _fake_build_auth_session_payload)


@pytest.mark.asyncio
async def test_login_contract_matches_base_cookie_session(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _build_user()
    frozen_now = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)
    expires = datetime(2026, 4, 7, 13, 0, tzinfo=UTC)
    _install_auth_service_mocks(monkeypatch, user=user)
    monkeypatch.setattr(auth, "verify_password", lambda raw, hashed: raw == "admin123" and hashed == user.password_hash)
    monkeypatch.setattr(auth, "create_access_token", lambda **kwargs: "access-token")
    monkeypatch.setattr(auth, "create_refresh_token", lambda **kwargs: "refresh-token")
    monkeypatch.setattr(auth.settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    monkeypatch.setattr(auth.settings, "JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return frozen_now if tz is not None else frozen_now.replace(tzinfo=None)

    monkeypatch.setattr(auth, "datetime", _FrozenDateTime)

    app = _build_auth_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["authMode"] == "cookie"
    assert payload["accessToken"] == "access-token"
    assert payload["refreshToken"] == "refresh-token"
    assert payload["expires"] == expires.isoformat()
    assert payload["roles"] == ["superuser"]
    assert payload["permissions"] == ["system:manage"]

    set_cookies = response.headers.get_list("set-cookie")
    assert any("aoju_access_token=access-token" in value for value in set_cookies)
    assert any("aoju_refresh_token=refresh-token" in value for value in set_cookies)
    assert any("Path=/" in value and "HttpOnly" in value for value in set_cookies)
    assert any("Path=/api/v1/auth" in value and "HttpOnly" in value for value in set_cookies)


@pytest.mark.asyncio
async def test_refresh_token_contract_matches_base_cookie_session(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _build_user()
    frozen_now = datetime(2026, 4, 7, 13, 0, tzinfo=UTC)
    expires = datetime(2026, 4, 7, 14, 0, tzinfo=UTC)
    _install_auth_service_mocks(monkeypatch, user=user)
    monkeypatch.setattr(auth, "decode_token", lambda token: {"type": "refresh", "sub": str(user.id)})
    monkeypatch.setattr(auth, "create_access_token", lambda **kwargs: "next-access-token")
    monkeypatch.setattr(auth, "create_refresh_token", lambda **kwargs: "next-refresh-token")
    monkeypatch.setattr(auth.settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    monkeypatch.setattr(auth.settings, "JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return frozen_now if tz is not None else frozen_now.replace(tzinfo=None)

    monkeypatch.setattr(auth, "datetime", _FrozenDateTime)

    app = _build_auth_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refreshToken": "refresh-token"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload == {
        "avatar": "",
        "username": "admin",
        "nickname": "Admin",
        "roles": ["superuser"],
        "permissions": ["system:manage"],
        "isSuperuser": True,
        "mustCompleteProfile": False,
        "authMode": "cookie",
        "accessToken": "next-access-token",
        "refreshToken": "next-refresh-token",
        "expires": expires.isoformat(),
    }

    set_cookies = response.headers.get_list("set-cookie")
    assert any("aoju_access_token=next-access-token" in value for value in set_cookies)
    assert any("aoju_refresh_token=next-refresh-token" in value for value in set_cookies)


@pytest.mark.asyncio
async def test_session_contract_stays_cookie_backed(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _build_user()
    expires = datetime(2026, 4, 7, 14, 0, tzinfo=UTC)

    async def _fake_build_auth_session_payload(*, db: Any, user: Any, expires: datetime | None) -> dict[str, Any]:
        assert db is not None
        assert user is not None
        return {
            "avatar": user.avatar,
            "username": user.username,
            "nickname": user.nickname,
            "roles": ["superuser"],
            "permissions": ["system:manage"],
            "isSuperuser": True,
            "mustCompleteProfile": False,
            "expires": expires,
            "authMode": "cookie",
        }

    monkeypatch.setattr(auth, "_build_auth_session_payload", _fake_build_auth_session_payload)
    monkeypatch.setattr(auth, "get_token_expiry", lambda token: expires)

    app = _build_auth_app(current_user_factory=lambda: user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/session",
            headers={"cookie": "aoju_access_token=cookie-session-token"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload == {
        "avatar": "",
        "username": "admin",
        "nickname": "Admin",
        "roles": ["superuser"],
        "permissions": ["system:manage"],
        "isSuperuser": True,
        "mustCompleteProfile": False,
        "expires": expires.isoformat(),
        "authMode": "cookie",
    }
    assert "accessToken" not in payload
    assert "refreshToken" not in payload
