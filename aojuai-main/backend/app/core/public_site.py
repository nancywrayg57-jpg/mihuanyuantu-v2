"""Deployment and tenant resolution for unauthenticated public-site traffic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.module_guards import is_module_enabled_for_tenant
from app.core.modules import is_module_enabled
from app.core.trusted_proxy import (
    is_forwarded_host_trusted,
    is_loopback_host,
    normalize_host,
)
from app.domain.auth.models import Tenant
from app.domain.auth.service import TenantService


@dataclass(frozen=True, slots=True)
class ResolvedPublicTenant:
    tenant: Tenant
    request_host: str
    canonical_host: str
    canonical_origin: str


def is_public_site_deployment_enabled() -> bool:
    """Return whether this process has the public CMS surface installed."""
    return (
        settings.PUBLIC_SITE_ROUTING_MODE != "off"
        and is_module_enabled("public_site")
    )


def require_public_site_deployment() -> None:
    if not is_public_site_deployment_enabled():
        raise NotFoundError("Site not found")


def _configured_domain(value: str | None) -> str:
    """Validate the hostname-only value stored in ``Tenant.domain``."""
    raw = str(value or "").strip().lower().rstrip(".")
    if not raw or any(token in raw for token in ("://", "/", "@", "?", "#", ",")):
        return ""
    return normalize_host(raw).rstrip(".")


def _direct_request_host(request: Request) -> str:
    return normalize_host(request.headers.get("host") or request.url.hostname).rstrip(".")


def resolve_public_request_host(request: Request) -> str:
    """Resolve Host while accepting forwarded authority only from a trusted proxy."""
    if is_forwarded_host_trusted(
        headers=request.headers,
        client_host=request.client.host if request.client else None,
        shared_secret=settings.AOJ_PROXY_SHARED_SECRET,
        is_pytest=settings.is_pytest_runtime,
    ):
        return normalize_host(request.headers.get("x-forwarded-host")).rstrip(".")
    return _direct_request_host(request)


def _canonical_origin(host: str) -> str:
    scheme = "http" if is_loopback_host(host) else "https"
    return f"{scheme}://{host}"


async def resolve_public_tenant(
    *,
    request: Request,
    db: Any,
    require_tenant_module: bool = True,
) -> ResolvedPublicTenant:
    """Resolve one active tenant without cross-tenant fallback.

    Production and staging accept only an exact configured public domain.
    Development may fall back by tenant code solely when the request itself is
    local and ``CMS_DEFAULT_TENANT_CODE`` was explicitly configured.
    """
    require_public_site_deployment()
    return await _resolve_tenant_by_public_host(
        request=request,
        db=db,
        module_code="public_site" if require_tenant_module else None,
    )


async def resolve_public_tenant_for_module(
    *,
    request: Request,
    db: Any,
    module_code: str,
) -> ResolvedPublicTenant:
    """Resolve an anonymous visitor's tenant for a module that owns its own public surface.

    与 :func:`resolve_public_tenant` **共用同一套主机解析**（可信代理、精确公开域、
    仅本机的开发回落），差别只有两处闸门：
    - 不要求公开站/CMS 已部署——那是 CMS 的部署形态，不该成为别的模块开放匿名入口的前提；
    - 校验的是**调用方模块**的租户开关，而不是 `public_site` 的。

    这不是绕过：解析不到主机、租户停用、或调用方模块在该租户下关着，一律 404（fail closed），
    与公开站的语义完全一致。新增匿名入口请走这里，不要各自另写一套主机→租户的解析。
    """
    normalized = str(module_code or "").strip()
    if not normalized:
        raise ValueError("module_code is required for a module-owned public surface")
    return await _resolve_tenant_by_public_host(request=request, db=db, module_code=normalized)


async def _resolve_tenant_by_public_host(
    *,
    request: Request,
    db: Any,
    module_code: str | None,
) -> ResolvedPublicTenant:
    host = resolve_public_request_host(request)
    service = TenantService(db)
    tenant: Tenant | None = None
    if host:
        tenant = await service.get_one(
            where=[Tenant.domain == host, Tenant.is_active.is_(True)],
        )
        if tenant is not None and _configured_domain(tenant.domain) != host:
            tenant = None

    fallback_code = str(settings.CMS_DEFAULT_TENANT_CODE or "").strip()
    if (
        tenant is None
        and settings.ENV == "development"
        and fallback_code
        and is_loopback_host(host)
    ):
        tenant = await service.get_one(
            where=[Tenant.code == fallback_code, Tenant.is_active.is_(True)],
        )

    if tenant is None:
        raise NotFoundError("Site not found")

    if module_code is not None and not await is_module_enabled_for_tenant(
        db=db,
        tenant_id=tenant.id,
        module_code=module_code,
    ):
        raise NotFoundError("Site not found")

    configured_host = _configured_domain(tenant.domain)
    canonical_host = configured_host or (host if is_loopback_host(host) else "")
    if not canonical_host:
        raise NotFoundError("Site not found")

    return ResolvedPublicTenant(
        tenant=tenant,
        request_host=host,
        canonical_host=canonical_host,
        canonical_origin=_canonical_origin(canonical_host),
    )
