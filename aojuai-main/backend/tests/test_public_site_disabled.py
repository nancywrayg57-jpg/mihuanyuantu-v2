from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse

from app.api import deps
from app.api.v1.endpoints import cms_public, site
from app.core import modules
from app.core.config import Settings, settings
from app.core.exceptions import AOJUException


@pytest.fixture(autouse=True)
def restore_deployment_settings() -> None:
    previous = (settings.PUBLIC_SITE_ROUTING_MODE, settings.AOJ_ENABLED_MODULES)
    yield
    settings.PUBLIC_SITE_ROUTING_MODE, settings.AOJ_ENABLED_MODULES = previous
    modules.clear_module_install_caches()


def test_public_site_routing_mode_defaults_off() -> None:
    defaults = Settings(_env_file=None)
    assert defaults.PUBLIC_SITE_ROUTING_MODE == "off"
    assert defaults.CMS_DEFAULT_TENANT_CODE is None


def test_cms_public_router_is_not_registered_when_deployment_is_off() -> None:
    settings.PUBLIC_SITE_ROUTING_MODE = "off"
    settings.AOJ_ENABLED_MODULES = ""
    modules.clear_module_install_caches()
    assert cms_public.build_public_cms_router().routes == []

    settings.PUBLIC_SITE_ROUTING_MODE = "domain"
    assert cms_public.build_public_cms_router().routes

    settings.AOJ_ENABLED_MODULES = "none"
    modules.clear_module_install_caches()
    assert cms_public.build_public_cms_router().routes == []


def _site_test_app() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AOJUException)
    async def handle_aoju_exception(request: Request, exc: AOJUException):  # noqa: ARG001
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code})

    app.include_router(site.router, prefix="/api/v1/site")
    app.include_router(cms_public.build_public_cms_router(), prefix="/api/v1/site/cms")

    async def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[deps.get_db] = override_db
    return app


@pytest.mark.asyncio
async def test_disabled_public_interfaces_return_404() -> None:
    settings.PUBLIC_SITE_ROUTING_MODE = "off"
    settings.AOJ_ENABLED_MODULES = ""
    modules.clear_module_install_caches()
    app = _site_test_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        cms_response = await client.get("/api/v1/site/cms/settings")
        config_response = await client.get("/api/v1/site/public-config")

    assert cms_response.status_code == 404
    assert config_response.status_code == 404
