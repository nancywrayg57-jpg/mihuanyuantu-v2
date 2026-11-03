from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.api.v1.endpoints import site
from app.core import modules, public_site
from app.core.config import settings
from app.infrastructure.cache.runtime_cache import delete_prefix


@pytest.fixture(autouse=True)
async def clear_site_public_config_runtime_cache() -> None:
    previous = (
        settings.PUBLIC_SITE_ROUTING_MODE,
        settings.AOJ_PROXY_SHARED_SECRET,
        settings.CMS_DEFAULT_TENANT_CODE,
        settings.AOJ_ENABLED_MODULES,
    )
    settings.PUBLIC_SITE_ROUTING_MODE = "domain"
    settings.AOJ_PROXY_SHARED_SECRET = "site-test-secret"
    settings.CMS_DEFAULT_TENANT_CODE = None
    settings.AOJ_ENABLED_MODULES = ""
    modules.clear_module_install_caches()
    await delete_prefix("site_public_config:")
    yield
    await delete_prefix("site_public_config:")
    (
        settings.PUBLIC_SITE_ROUTING_MODE,
        settings.AOJ_PROXY_SHARED_SECRET,
        settings.CMS_DEFAULT_TENANT_CODE,
        settings.AOJ_ENABLED_MODULES,
    ) = previous
    modules.clear_module_install_caches()


def _build_tenant(
    *,
    tenant_id: int,
    name: str,
    code: str,
    domain: str | None,
    seo: dict[str, str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=tenant_id,
        name=name,
        code=code,
        domain=domain,
        config={"seo": dict(seo or {})},
        is_active=True,
    )


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(site.router, prefix="/api/v1/site")

    async def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[deps.get_db] = override_db
    return app


@pytest.mark.asyncio
async def test_site_public_config_prefers_forwarded_host_for_tenant_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matched_tenant = _build_tenant(
        tenant_id=2,
        name="AOJUAI",
        code="aojuai",
        domain="share.example.test",
        seo={
            "title": "AOJUAI Share",
            "keywords": "ai,share",
            "description": "AOJUAI public share site",
        },
    )
    captured_values: list[list[object]] = []

    async def fake_get_one(self, where=None, **kwargs):  # noqa: ANN001, ARG001
        values = [getattr(getattr(clause, "right", None), "value", None) for clause in (where or [])]
        captured_values.append(values)
        if "share.example.test" in values:
            return matched_tenant
        return None

    async def fake_module_enabled(**kwargs):  # noqa: ANN003
        return True

    async def fake_remember_json(  # noqa: ANN001
        cache_key: str,
        *,
        ttl_seconds: int,
        loader,
    ) -> dict[str, object]:
        assert cache_key == site.build_site_public_config_cache_key("share.example.test")
        assert ttl_seconds >= 0
        return await loader()

    monkeypatch.setattr(public_site.TenantService, "get_one", fake_get_one)
    monkeypatch.setattr(public_site, "is_module_enabled_for_tenant", fake_module_enabled)
    monkeypatch.setattr(site, "remember_json", fake_remember_json)

    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/site/public-config",
            headers={
                "host": "127.0.0.1:3000",
                "x-forwarded-host": "share.example.test, proxy.internal",
                "x-aoju-proxy-key": "site-test-secret",
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["tenantId"] == 2
    assert payload["tenantCode"] == "aojuai"
    assert payload["tenantName"] == "AOJUAI"
    assert payload["canonicalOrigin"] == "https://share.example.test"
    assert payload["seo"]["title"] == "AOJUAI Share"
    assert payload["seo"]["keywords"] == "ai,share"
    assert payload["seo"]["description"] == "AOJUAI public share site"
    assert captured_values
    assert "share.example.test" in captured_values[0]
