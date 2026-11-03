from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.api.v1.endpoints import tenant_profile
from app.core.provider_secrets import decrypt_provider_secret, encrypt_provider_secret
from app.infrastructure.cache.runtime_cache import delete_prefix


@pytest.fixture(autouse=True)
async def clear_tenant_email_runtime_cache() -> None:
    await delete_prefix("tenant_settings:")
    await delete_prefix("tenant_profile:")
    yield
    await delete_prefix("tenant_settings:")
    await delete_prefix("tenant_profile:")


def _build_tenant(config: object = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="Demo Tenant",
        code="demo",
        domain=None,
        description=None,
        is_active=True,
        expires_at=None,
        config=config,
        quota={},
        contact_name=None,
        contact_phone=None,
        contact_email=None,
        created_at=None,
    )


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(tenant_profile.router, prefix="/api/v1/tenant/profile")

    async def override_current_user():
        return SimpleNamespace(id=1, tenant_id=1, is_superuser=True)

    async def override_tenant_admin():
        return SimpleNamespace(id=1, tenant_id=1, is_superuser=True)

    async def override_db():
        yield SimpleNamespace()

    async def override_tenant_ctx():
        return SimpleNamespace(tenant_id=1, is_superuser=True, user_tenant_id=1)

    app.dependency_overrides[deps.get_current_user] = override_current_user
    app.dependency_overrides[deps.get_current_tenant_admin] = override_tenant_admin
    app.dependency_overrides[deps.get_db] = override_db
    app.dependency_overrides[deps.get_tenant_context] = override_tenant_ctx
    return app


def _install_tenant_service(
    monkeypatch: pytest.MonkeyPatch,
    tenant: SimpleNamespace,
) -> list[dict[str, object]]:
    updates: list[dict[str, object]] = []

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001, ARG001
        return tenant

    async def fake_update(self, obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        updates.append(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(tenant_profile.TenantService, "update", fake_update)
    return updates


@pytest.mark.asyncio
async def test_patch_encrypts_password_and_stores_only_canonical_smtp_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(config={})
    updates = _install_tenant_service(monkeypatch, tenant)
    plaintext = "new-smtp-password"

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/tenant/profile/email-config",
            json={
                "mode": "override",
                "smtp": {
                    "host": "smtp.tenant.example",
                    "port": 465,
                    "username": "tenant-user",
                    "password": plaintext,
                    "sender_email": "sender@example.com",
                    "senderName": "Tenant Mail",
                    "useSsl": True,
                    "timeout_seconds": 18,
                },
            },
        )

    assert response.status_code == 200, response.text
    assert len(updates) == 1
    saved = updates[0]["config"]
    assert isinstance(saved, dict)
    email = saved["messaging"]["email"]
    smtp = email["smtp"]
    assert email["mode"] == "override"
    assert set(smtp) == {
        "host",
        "port",
        "username",
        "passwordEncrypted",
        "senderEmail",
        "senderName",
        "security",
        "timeoutSeconds",
    }
    assert smtp["security"] == "ssl"
    assert smtp["senderEmail"] == "sender@example.com"
    assert smtp["passwordEncrypted"] != plaintext
    assert decrypt_provider_secret(smtp["passwordEncrypted"]) == plaintext
    assert plaintext not in response.text
    assert smtp["passwordEncrypted"] not in response.text


@pytest.mark.asyncio
async def test_smtp_get_views_return_only_password_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encrypted = encrypt_provider_secret("stored-secret")
    tenant = _build_tenant(
        config={
            "messaging": {
                "email": {
                    "mode": "override",
                    "smtp": {
                        "host": "smtp.tenant.example",
                        "senderEmail": "sender@example.com",
                        "passwordEncrypted": encrypted,
                    },
                }
            },
            "verification": {
                "email": {
                    "smtp": {
                        "host": "legacy.example",
                        "from": "legacy@example.com",
                        "password": "legacy-plaintext",
                    }
                }
            },
        }
    )
    _install_tenant_service(monkeypatch, tenant)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        dedicated = await client.get("/api/v1/tenant/profile/email-config")
        generic = await client.get("/api/v1/tenant/profile/settings")

    assert dedicated.status_code == 200, dedicated.text
    assert generic.status_code == 200, generic.text
    dedicated_smtp = dedicated.json()["data"]["smtp"]
    generic_config = generic.json()["data"]["config"]
    assert dedicated_smtp["passwordSet"] is True
    assert "password" not in dedicated_smtp
    assert "passwordEncrypted" not in dedicated_smtp
    assert generic_config["messaging"]["email"]["smtp"]["passwordSet"] is True
    assert generic_config["verification"]["email"]["smtp"]["passwordSet"] is True
    for response_text in (dedicated.text, generic.text):
        assert encrypted not in response_text
        assert "stored-secret" not in response_text
        assert "legacy-plaintext" not in response_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"verification": {"email": {"smtp": {"password": "bypass-plaintext"}}}},
        {"messaging": {"email": {"smtp": {"passwordEncrypted": "bypass-ciphertext"}}}},
    ],
)
async def test_generic_settings_patch_cannot_bypass_smtp_encryption(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    tenant = _build_tenant(config={})
    updates = _install_tenant_service(monkeypatch, tenant)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch("/api/v1/tenant/profile/settings", json=payload)

    assert response.status_code == 422, response.text
    assert updates == []
    assert tenant.config == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("clear_value", [None, ""])
async def test_password_patch_preserves_replaces_and_clears(
    monkeypatch: pytest.MonkeyPatch,
    clear_value: str | None,
) -> None:
    original_encrypted = encrypt_provider_secret("original-password")
    tenant = _build_tenant(
        config={
            "messaging": {
                "email": {
                    "mode": "override",
                    "smtp": {
                        "host": "smtp.tenant.example",
                        "username": "tenant-user",
                        "senderEmail": "sender@example.com",
                        "security": "starttls",
                        "passwordEncrypted": original_encrypted,
                    },
                }
            }
        }
    )
    _install_tenant_service(monkeypatch, tenant)
    app = _build_test_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        preserved = await client.patch(
            "/api/v1/tenant/profile/email-config",
            json={"smtp": {"host": "smtp.changed.example"}},
        )
        assert preserved.status_code == 200, preserved.text
        smtp = tenant.config["messaging"]["email"]["smtp"]
        assert smtp["passwordEncrypted"] == original_encrypted

        replaced = await client.patch(
            "/api/v1/tenant/profile/email-config",
            json={"smtp": {"password": "replacement-password"}},
        )
        assert replaced.status_code == 200, replaced.text
        smtp = tenant.config["messaging"]["email"]["smtp"]
        assert smtp["passwordEncrypted"] != original_encrypted
        assert decrypt_provider_secret(smtp["passwordEncrypted"]) == "replacement-password"

        cleared = await client.patch(
            "/api/v1/tenant/profile/email-config",
            json={"smtp": {"password": clear_value}},
        )

    assert cleared.status_code == 200, cleared.text
    smtp = tenant.config["messaging"]["email"]["smtp"]
    assert "passwordEncrypted" not in smtp
    assert cleared.json()["data"]["smtp"]["passwordSet"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["inherit", "override", "disabled"])
async def test_email_config_patch_supports_each_mode(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    tenant = _build_tenant(config={})
    _install_tenant_service(monkeypatch, tenant)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/tenant/profile/email-config",
            json={"mode": mode},
        )

    assert response.status_code == 200, response.text
    assert tenant.config["messaging"]["email"]["mode"] == mode
    assert response.json()["data"]["mode"] == mode
