from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.api.v1.endpoints import auth


class _Tenant:
    def __init__(self, *, invitation_enabled: bool, registration_enabled: bool = False) -> None:
        self.code = "demo"
        self.name = "Demo Tenant"
        self.is_active = True
        self.config = {
            "registration": {
                "enabled": registration_enabled,
                "requireAudit": True,
                "invitation": {
                    "enabled": invitation_enabled,
                },
            }
        }

    @property
    def registration_enabled(self) -> bool:
        reg = self.config.get("registration", {})
        return bool(reg.get("enabled", True))

    @property
    def registration_require_audit(self) -> bool:
        reg = self.config.get("registration", {})
        return bool(reg.get("requireAudit", True))

    @property
    def registration_default_role(self) -> str:
        reg = self.config.get("registration", {})
        return str(reg.get("defaultRole", "user"))


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")

    async def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[deps.get_db] = override_db
    return app


@pytest.mark.asyncio
async def test_parse_invite_allows_invite_only_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _Tenant(invitation_enabled=True, registration_enabled=False)

    async def fake_resolve_code_context(self, code: str, for_update: bool = False):  # noqa: ANN001, ARG001
        return None

    async def fake_get_one(self, **kwargs):  # noqa: ANN001
        if kwargs.get("code") == "demo":
            return tenant
        return None

    monkeypatch.setattr(auth, "decode_invite_code", lambda code: "demo")
    monkeypatch.setattr(auth.InvitationService, "resolve_code_context", fake_resolve_code_context)
    monkeypatch.setattr(auth.TenantService, "get_one", fake_get_one)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/parse-invite?code=invite-only-demo")

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["tenantCode"] == "demo"
    assert payload["tenantSource"] == "invite"
    assert payload["invitation"]["enabled"] is True


@pytest.mark.asyncio
async def test_parse_invite_rejects_when_invitation_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _Tenant(invitation_enabled=False, registration_enabled=False)

    async def fake_resolve_code_context(self, code: str, for_update: bool = False):  # noqa: ANN001, ARG001
        return None

    async def fake_get_one(self, **kwargs):  # noqa: ANN001
        if kwargs.get("code") == "demo":
            return tenant
        return None

    monkeypatch.setattr(auth, "decode_invite_code", lambda code: "demo")
    monkeypatch.setattr(auth.InvitationService, "resolve_code_context", fake_resolve_code_context)
    monkeypatch.setattr(auth.TenantService, "get_one", fake_get_one)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/parse-invite?code=invite-disabled-demo")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is False
    assert payload["code"] == "INVITATION_DISABLED"
