from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.api.v1.endpoints import tenant_profile
from app.core import feature_switches
from app.core.config import settings
from app.infrastructure.cache import runtime_cache


@pytest.fixture(autouse=True)
def reset_feature_switch_state(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.AOJ_ENABLED_MODULES = ""
    feature_switches._installed_module_codes.cache_clear()
    feature_switches._available_module_defaults.cache_clear()
    runtime_cache._local_cache.clear()
    runtime_cache._remember_locks.clear()
    monkeypatch.setattr(runtime_cache, "_redis_client", None)
    monkeypatch.setattr(runtime_cache, "_redis_initialized", True)
    yield
    settings.AOJ_ENABLED_MODULES = ""
    feature_switches._installed_module_codes.cache_clear()
    feature_switches._available_module_defaults.cache_clear()
    runtime_cache._local_cache.clear()
    runtime_cache._remember_locks.clear()


def _build_test_app(*, target_tenant_id: int) -> FastAPI:
    app = FastAPI()
    app.include_router(tenant_profile.router, prefix="/api/v1/tenant/profile")

    async def override_current_user():
        return SimpleNamespace(id=1, tenant_id=1, is_superuser=True)

    async def override_tenant_admin():
        return SimpleNamespace(id=1, tenant_id=1, is_superuser=True)

    async def override_db():
        yield SimpleNamespace()

    async def override_tenant_ctx():
        return SimpleNamespace(tenant_id=target_tenant_id, is_superuser=True, user_tenant_id=1)

    app.dependency_overrides[deps.get_current_user] = override_current_user
    app.dependency_overrides[deps.get_current_tenant_admin] = override_tenant_admin
    app.dependency_overrides[deps.get_db] = override_db
    app.dependency_overrides[deps.get_tenant_context] = override_tenant_ctx
    return app


@pytest.mark.asyncio
async def test_feature_catalog_endpoint_uses_target_tenant_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_tenant_ids: list[int] = []

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        requested_tenant_ids.append(tenant_id)
        return SimpleNamespace(
            id=tenant_id,
            config={
                "feature_switches": {
                    "modules": {
                        "assistant": False,
                        "speech": True,
                    }
                }
            },
        )

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)

    app = _build_test_app(target_tenant_id=84)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tenant/profile/settings/feature-catalog")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["featureSwitches"]["modules"]["assistant"] is False
    assert payload["data"]["featureSwitches"]["modules"]["speech"] is True
    assert len(payload["data"]["catalogDigest"]) == 64
    # 内置项都是 capability 层；能力包会带 pack/sample 层进来，所以只校验内置项。
    builtin_layers = {
        item["code"]: item["layer"]
        for item in payload["data"]["modules"]
        if item["code"] in {"assistant", "speech", "public_site"}
    }
    assert set(builtin_layers.values()) == {"capability"}
    assert requested_tenant_ids == [84]


@pytest.mark.asyncio
async def test_feature_catalog_endpoint_recovers_from_non_object_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        return SimpleNamespace(id=tenant_id, config=[])

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)

    app = _build_test_app(target_tenant_id=21)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tenant/profile/settings/feature-catalog")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["featureSwitches"] == feature_switches.normalize_feature_switches({})


@pytest.mark.asyncio
async def test_runtime_feature_switches_endpoint_uses_target_tenant_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_tenant_ids: list[int] = []

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        requested_tenant_ids.append(tenant_id)
        return SimpleNamespace(
            id=tenant_id,
            config={
                "feature_switches": {
                    "modules": {
                        "assistant": False,
                        "speech": True,
                    },
                    "capabilities": {
                        "verification_sms": False,
                    },
                }
            },
        )

    monkeypatch.setattr(tenant_profile.TenantService, "get_by_id", fake_get_by_id)

    app = _build_test_app(target_tenant_id=84)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tenant/profile/feature-switches")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["tenantId"] == 84
    assert payload["data"]["featureSwitches"]["modules"]["assistant"] is False
    assert payload["data"]["featureSwitches"]["modules"]["speech"] is True
    assert payload["data"]["featureSwitches"]["capabilities"]["verification_sms"] is False
    assert requested_tenant_ids == [84]
