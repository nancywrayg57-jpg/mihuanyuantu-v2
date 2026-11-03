from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.api.v1.endpoints import cms_public
from app.core import modules, public_site
from app.core.config import settings
from app.core.exceptions import NotFoundError


def _request(
    host: str,
    *,
    forwarded_host: str | None = None,
    proxy_key: str | None = None,
    client_host: str = "203.0.113.20",
) -> Request:
    raw_headers = [(b"host", host.encode())]
    if forwarded_host:
        raw_headers.append((b"x-forwarded-host", forwarded_host.encode()))
    if proxy_key:
        raw_headers.append((b"x-aoju-proxy-key", proxy_key.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/api/v1/site/public-config",
            "raw_path": b"/api/v1/site/public-config",
            "query_string": b"",
            "headers": raw_headers,
            "client": (client_host, 43210),
            "server": (host.split(":", 1)[0], 443),
        }
    )


def _tenant(*, domain: str | None = "www.example.com", code: str = "public") -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        code=code,
        name="Public tenant",
        domain=domain,
        config={},
        is_active=True,
    )


@pytest.fixture(autouse=True)
def public_site_settings() -> None:
    previous = (
        settings.PUBLIC_SITE_ROUTING_MODE,
        settings.ENV,
        settings.CMS_DEFAULT_TENANT_CODE,
        settings.AOJ_PROXY_SHARED_SECRET,
        settings.AOJ_ENABLED_MODULES,
    )
    settings.PUBLIC_SITE_ROUTING_MODE = "domain"
    settings.ENV = "production"
    settings.CMS_DEFAULT_TENANT_CODE = None
    settings.AOJ_PROXY_SHARED_SECRET = "trusted-secret"
    settings.AOJ_ENABLED_MODULES = ""
    modules.clear_module_install_caches()
    yield
    (
        settings.PUBLIC_SITE_ROUTING_MODE,
        settings.ENV,
        settings.CMS_DEFAULT_TENANT_CODE,
        settings.AOJ_PROXY_SHARED_SECRET,
        settings.AOJ_ENABLED_MODULES,
    ) = previous
    modules.clear_module_install_caches()


@pytest.mark.asyncio
async def test_unknown_production_host_is_not_fallen_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queried: list[list[object]] = []

    async def fake_get_one(self, where=None, **kwargs):  # noqa: ANN001, ARG001
        queried.append([getattr(getattr(item, "right", None), "value", None) for item in where or []])
        return None

    monkeypatch.setattr(public_site.TenantService, "get_one", fake_get_one)
    settings.CMS_DEFAULT_TENANT_CODE = "should-not-be-used"

    with pytest.raises(NotFoundError, match="Site not found"):
        await public_site.resolve_public_tenant(
            request=_request("unknown.example"),
            db=SimpleNamespace(),
        )

    assert queried == [["unknown.example", None]]


@pytest.mark.asyncio
async def test_untrusted_forwarded_host_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queried_hosts: list[object] = []

    async def fake_get_one(self, where=None, **kwargs):  # noqa: ANN001, ARG001
        values = [getattr(getattr(item, "right", None), "value", None) for item in where or []]
        queried_hosts.extend(values)
        return _tenant() if "www.example.com" in values else None

    monkeypatch.setattr(public_site.TenantService, "get_one", fake_get_one)

    with pytest.raises(NotFoundError):
        await public_site.resolve_public_tenant(
            request=_request("unknown.example", forwarded_host="www.example.com"),
            db=SimpleNamespace(),
        )

    assert "unknown.example" in queried_hosts
    assert "www.example.com" not in queried_hosts


@pytest.mark.asyncio
async def test_development_fallback_requires_explicit_code_and_local_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_tenant = _tenant(domain=None, code="local-site")
    queried: list[list[object]] = []

    async def fake_get_one(self, where=None, **kwargs):  # noqa: ANN001, ARG001
        values = [getattr(getattr(item, "right", None), "value", None) for item in where or []]
        queried.append(values)
        return fallback_tenant if "local-site" in values else None

    async def fake_module_enabled(**kwargs):  # noqa: ANN003
        return True

    monkeypatch.setattr(public_site.TenantService, "get_one", fake_get_one)
    monkeypatch.setattr(public_site, "is_module_enabled_for_tenant", fake_module_enabled)
    settings.ENV = "development"

    with pytest.raises(NotFoundError):
        await public_site.resolve_public_tenant(
            request=_request("localhost:3000", client_host="127.0.0.1"),
            db=SimpleNamespace(),
        )
    assert len(queried) == 1

    settings.CMS_DEFAULT_TENANT_CODE = "local-site"
    resolved = await public_site.resolve_public_tenant(
        request=_request("localhost:3000", client_host="127.0.0.1"),
        db=SimpleNamespace(),
    )
    assert resolved.tenant.code == "local-site"
    assert resolved.canonical_origin == "http://localhost"


@pytest.mark.asyncio
async def test_tenant_module_is_rejected_before_cms_service_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_one(self, where=None, **kwargs):  # noqa: ANN001, ARG001
        values = [getattr(getattr(item, "right", None), "value", None) for item in where or []]
        return _tenant() if "www.example.com" in values else None

    async def fake_module_disabled(**kwargs):  # noqa: ANN003
        return False

    class CmsTableMustNotBeTouched:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("CMS table service was touched")

    monkeypatch.setattr(public_site.TenantService, "get_one", fake_get_one)
    monkeypatch.setattr(public_site, "is_module_enabled_for_tenant", fake_module_disabled)
    monkeypatch.setattr(cms_public, "CmsPageService", CmsTableMustNotBeTouched)

    with pytest.raises(NotFoundError, match="Site not found"):
        await cms_public.public_page(
            "pricing",
            _request("www.example.com"),
            SimpleNamespace(),
        )


@pytest.mark.asyncio
async def test_module_owned_public_surface_shares_the_host_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """能力包自带的匿名入口走同一套主机解析，只是闸门换成它自己的模块开关。

    这条是为了防止"每个模块各写一套 host → tenant"：那才是真正的旁路，
    可信代理判定、精确公开域、开发回落三处只要有一处写漏就是跨租户读。
    """
    checked: list[str] = []

    async def fake_get_one(self, where=None, **kwargs):  # noqa: ANN001, ARG001
        values = [getattr(getattr(item, "right", None), "value", None) for item in where or []]
        return _tenant() if "www.example.com" in values else None

    async def fake_module_enabled(*, db, tenant_id, module_code):  # noqa: ANN001, ARG001
        checked.append(module_code)
        return module_code == "support"

    monkeypatch.setattr(public_site.TenantService, "get_one", fake_get_one)
    monkeypatch.setattr(public_site, "is_module_enabled_for_tenant", fake_module_enabled)

    resolved = await public_site.resolve_public_tenant_for_module(
        request=_request("www.example.com"),
        db=SimpleNamespace(),
        module_code="support",
    )
    assert resolved.canonical_origin == "https://www.example.com"
    assert checked == ["support"], "校验的必须是调用方模块，不是 public_site"

    # 调用方模块在该租户下关着 => 404（不泄漏"这里有功能但关了"）
    with pytest.raises(NotFoundError, match="Site not found"):
        await public_site.resolve_public_tenant_for_module(
            request=_request("www.example.com"),
            db=SimpleNamespace(),
            module_code="not_installed_module",
        )


@pytest.mark.asyncio
async def test_module_owned_public_surface_does_not_need_the_cms_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """公开站没部署时，别的模块的匿名入口仍然可用——CMS 的部署形态不该绑住它。"""

    async def fake_get_one(self, where=None, **kwargs):  # noqa: ANN001, ARG001
        values = [getattr(getattr(item, "right", None), "value", None) for item in where or []]
        return _tenant() if "www.example.com" in values else None

    async def fake_module_enabled(**kwargs):  # noqa: ANN003
        return True

    monkeypatch.setattr(public_site.TenantService, "get_one", fake_get_one)
    monkeypatch.setattr(public_site, "is_module_enabled_for_tenant", fake_module_enabled)
    settings.PUBLIC_SITE_ROUTING_MODE = "off"

    assert public_site.is_public_site_deployment_enabled() is False
    with pytest.raises(NotFoundError):
        await public_site.resolve_public_tenant(
            request=_request("www.example.com"), db=SimpleNamespace()
        )

    resolved = await public_site.resolve_public_tenant_for_module(
        request=_request("www.example.com"),
        db=SimpleNamespace(),
        module_code="support",
    )
    assert resolved.tenant.code == "public"


@pytest.mark.asyncio
async def test_module_owned_public_surface_requires_a_module_code() -> None:
    with pytest.raises(ValueError, match="module_code is required"):
        await public_site.resolve_public_tenant_for_module(
            request=_request("www.example.com"),
            db=SimpleNamespace(),
            module_code="  ",
        )
