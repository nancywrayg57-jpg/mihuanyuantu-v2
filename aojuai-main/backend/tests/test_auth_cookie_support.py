from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from starlette.responses import Response

from app.api import deps
from app.api.v1.endpoints import auth
from app.core.auth_cookies import clear_auth_cookies, get_access_cookie, get_refresh_cookie, set_auth_cookies


def test_set_auth_cookies_sets_dual_paths() -> None:
    response = Response()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"host", b"example.com")],
            "scheme": "https",
        }
    )

    set_auth_cookies(
        response,
        request=request,
        access_token="access-token",
        refresh_token="refresh-token",
    )

    raw_headers = [value.decode("latin-1") for name, value in response.raw_headers if name == b"set-cookie"]
    assert any("aoju_access_token=access-token" in header and "Path=/" in header for header in raw_headers)
    assert any("aoju_refresh_token=refresh-token" in header and "Path=/api/v1/auth" in header for header in raw_headers)


def test_cookie_helpers_read_expected_cookie_names() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/session",
            "headers": [(b"cookie", b"aoju_access_token=access-demo; aoju_refresh_token=refresh-demo")],
        }
    )

    assert get_access_cookie(request) == "access-demo"
    assert get_refresh_cookie(request) == "refresh-demo"


def test_clear_auth_cookies_preserves_paths() -> None:
    response = Response()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/logout",
            "headers": [(b"host", b"example.com")],
            "scheme": "https",
        }
    )

    clear_auth_cookies(response, request=request)

    raw_headers = [value.decode("latin-1") for name, value in response.raw_headers if name == b"set-cookie"]
    assert any(
        "aoju_access_token=" in header and "Max-Age=0" in header and "Path=/" in header
        for header in raw_headers
    )
    assert any(
        "aoju_refresh_token=" in header and "Max-Age=0" in header and "Path=/api/v1/auth" in header
        for header in raw_headers
    )


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")

    async def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[deps.get_db] = override_db
    return app


@pytest.mark.asyncio
async def test_refresh_token_allows_cookie_only_request_without_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=7, tenant_id=3, is_active=True)

    async def fake_get_user_by_id_any_tenant(self, user_id: int):  # noqa: ANN001
        assert user_id == 7
        return user

    async def fake_build_auth_session_payload(*, db, user, expires):  # noqa: ANN001
        _ = db, expires
        return {
            "avatar": "",
            "username": "member",
            "nickname": "",
            "roles": ["user"],
            "permissions": ["agents:myapp:read"],
            "isSuperuser": False,
            "mustCompleteProfile": False,
        }

    monkeypatch.setattr(auth, "decode_token", lambda token: {"type": "refresh", "sub": "7"} if token == "refresh-demo" else {})
    monkeypatch.setattr(auth.UserService, "get_user_by_id_any_tenant", fake_get_user_by_id_any_tenant)
    monkeypatch.setattr(auth, "_build_auth_session_payload", fake_build_auth_session_payload)
    monkeypatch.setattr(auth, "create_access_token", lambda subject, extra_data: f"access-{subject}-{extra_data['tenant_id']}")
    monkeypatch.setattr(auth, "create_refresh_token", lambda subject: f"refresh-{subject}")

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/refresh-token",
            headers={"Cookie": "aoju_refresh_token=refresh-demo"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["accessToken"] == "access-7-3"
    assert payload["data"]["refreshToken"] == "refresh-7"
    assert payload["data"]["mustCompleteProfile"] is False

    set_cookies = response.headers.get_list("set-cookie")
    assert any("aoju_access_token=access-7-3" in value for value in set_cookies)
    assert any("aoju_refresh_token=refresh-7" in value for value in set_cookies)
