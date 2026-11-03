from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.api.v1.endpoints import tenant_profile
from app.infrastructure.cache.runtime_cache import delete_prefix


@pytest.fixture(autouse=True)
async def clear_tenant_profile_runtime_cache() -> None:
    await delete_prefix("tenant_settings:")
    await delete_prefix("tenant_profile:")
    await delete_prefix("tenant_feature_catalog:")
    await delete_prefix("tenant_feature_switches:")
    yield
    await delete_prefix("tenant_settings:")
    await delete_prefix("tenant_profile:")
    await delete_prefix("tenant_feature_catalog:")
    await delete_prefix("tenant_feature_switches:")


def _build_tenant(*, tenant_id: int = 1, config: object = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=tenant_id,
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


@pytest.mark.asyncio
async def test_update_tenant_settings_recovers_from_non_object_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(config=[])
    captured_update: dict[str, object] = {}

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        return tenant

    async def fake_update(self, obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured_update.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(tenant_profile.TenantService, "update", fake_update)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/api/v1/tenant/profile/settings",
            json={
                "timezone": "Asia/Shanghai",
                "registration": {
                    "enabled": False,
                    "requireAudit": False,
                    "defaultRole": "user",
                    "basicFields": {
                        "nickname": {"enabled": True, "required": True},
                        "email": {"enabled": True, "required": False},
                        "phone": {"enabled": False, "required": False},
                    },
                }
            },
        )

    assert response.status_code == 200, response.text
    saved_config = captured_update["config"]
    assert isinstance(saved_config, dict)
    assert saved_config["timezone"] == "Asia/Shanghai"
    assert saved_config["registration"] == {
        "enabled": False,
        "requireAudit": False,
        "defaultRole": "user",
        "basicFields": {
            "nickname": {"enabled": True, "required": True},
            "email": {"enabled": True, "required": False},
            "phone": {"enabled": False, "required": False},
        },
    }
    assert isinstance(saved_config["verification"], dict)
    assert saved_config["feature_switches"] == saved_config["featureSwitches"]
    assert response.json()["data"]["config"]["timezone"] == "Asia/Shanghai"


@pytest.mark.asyncio
async def test_get_tenant_settings_normalizes_registration_basic_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(
        config={
            "registration": {
                "basicFields": {
                    "nickname": {"enabled": False, "required": True},
                    "email": {"enabled": True, "required": True},
                }
            }
        }
    )

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        return tenant

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tenant/profile/settings")

    assert response.status_code == 200, response.text
    payload = response.json()["data"]["config"]["registration"]["basicFields"]
    assert payload == {
        "nickname": {"enabled": True, "required": True},
        "email": {"enabled": True, "required": True},
        "phone": {"enabled": True, "required": False},
    }


@pytest.mark.asyncio
async def test_get_tenant_settings_hides_removed_knowledge_base_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(
        config={
            "knowledge_base": {
                "provider": "legacy_vendor",
                "providerSettings": {
                    "apiUrl": "https://legacy.example.com/v1",
                    "apiKey": "secret-token",
                },
            },
            "knowledgeBase": {"provider": "legacy_remote"},
            "ai": {
                "provider": "legacy_vendor",
                "providerSettings": {
                    "apiUrl": "https://legacy.example.com/v1",
                    "apiKey": "legacy-secret",
                },
            },
        }
    )

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        return tenant

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tenant/profile/settings")

    assert response.status_code == 200, response.text
    payload = response.json()["data"]["config"]
    assert "knowledge_base" not in payload
    assert "knowledgeBase" not in payload
    assert "ai" not in payload
    assert "secret-token" not in response.text
    assert "legacy-secret" not in response.text


@pytest.mark.asyncio
async def test_update_tenant_settings_ignores_removed_knowledge_base_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(config={})
    captured_update: dict[str, object] = {}

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        return tenant

    async def fake_update(self, obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured_update.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(tenant_profile.TenantService, "update", fake_update)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/api/v1/tenant/profile/settings",
            json={
                "timezone": "Asia/Shanghai",
                "knowledgeBase": {
                    "provider": "legacy_vendor",
                    "providerSettings": {
                        "apiUrl": "https://new.example.com",
                        "apiKey": "secret-new",
                    },
                },
            },
        )

    assert response.status_code == 200, response.text
    saved_config = captured_update["config"]
    assert isinstance(saved_config, dict)
    assert saved_config["timezone"] == "Asia/Shanghai"
    assert "knowledge_base" not in saved_config
    assert "knowledgeBase" not in saved_config
    assert "secret-new" not in response.text


@pytest.mark.asyncio
async def test_update_tenant_settings_accepts_valid_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(config={})
    captured_update: dict[str, object] = {}

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        return tenant

    async def fake_update(self, obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured_update.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(tenant_profile.TenantService, "update", fake_update)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/api/v1/tenant/profile/settings",
            json={"timezone": "Asia/Shanghai"},
        )

    assert response.status_code == 200, response.text
    saved_config = captured_update["config"]
    assert isinstance(saved_config, dict)
    assert saved_config["timezone"] == "Asia/Shanghai"
    assert response.json()["data"]["config"]["timezone"] == "Asia/Shanghai"


@pytest.mark.asyncio
async def test_update_tenant_settings_rejects_invalid_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(config={})

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        return tenant

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/api/v1/tenant/profile/settings",
            json={"timezone": "Mars/Base"},
        )

    assert response.status_code == 422, response.text
    assert "invalid timezone" in response.text
