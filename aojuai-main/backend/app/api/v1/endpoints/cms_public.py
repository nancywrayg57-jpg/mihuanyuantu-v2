"""
AOJU Backend - CMS Public Endpoints (no auth)

These power the public marketing site. Tenant is resolved by request host
(same strategy as site.public-config). Only PUBLISHED content is returned.
Mounted at /api/v1/site/cms.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.deps import DBSession
from app.core.exceptions import NotFoundError
from app.core.public_site import (
    is_public_site_deployment_enabled,
    resolve_public_tenant,
)
from app.core.response import SuccessResponse
from app.domain.cms.models import NavLocation
from app.domain.cms.schemas import PublicPage, PublicPost
from app.domain.cms.service import (  # noqa: F401
    CmsLanguageService,
    CmsContactService,
    CmsNavigationService,
    CmsPageService,
    CmsPostService,
    CmsSiteSettingsService,
)

_public_routes = APIRouter()


@_public_routes.get("/settings")
async def public_settings(request: Request, db: DBSession) -> Any:
    resolved = await resolve_public_tenant(request=request, db=db)
    row = await CmsSiteSettingsService(db).get_for_tenant(tenant_id=resolved.tenant.id)
    site_settings = row.settings if row else {}
    return SuccessResponse(data={"settings": site_settings})


@_public_routes.get("/navigation")
async def public_navigation(request: Request, db: DBSession) -> Any:
    resolved = await resolve_public_tenant(request=request, db=db)
    result: dict[str, Any] = {NavLocation.HEADER.value: [], NavLocation.FOOTER.value: []}
    service = CmsNavigationService(db)
    for loc in (NavLocation.HEADER.value, NavLocation.FOOTER.value):
        nav = await service.get_by_location(loc, tenant_id=resolved.tenant.id)
        result[loc] = nav.items if nav else []
    return SuccessResponse(data=result)


async def _default_locale(db, tenant_id: int) -> str:
    return await CmsLanguageService(db).default_code(tenant_id=tenant_id)


@_public_routes.get("/languages")
async def public_languages(request: Request, db: DBSession) -> Any:
    """Active languages for the public site (taxonomy-driven switcher)."""
    resolved = await resolve_public_tenant(request=request, db=db)
    tenant_id = resolved.tenant.id
    langs = await CmsLanguageService(db).list_languages(tenant_id=tenant_id, active_only=True)
    return SuccessResponse(
        data={
            "list": [
                {"code": l.code, "name": l.name, "isDefault": l.is_default} for l in langs
            ],
            "defaultCode": await CmsLanguageService(db).default_code(tenant_id=tenant_id),
        }
    )


@_public_routes.get("/pages/{slug:path}")
async def public_page(slug: str, request: Request, db: DBSession, locale: str | None = None) -> Any:
    resolved = await resolve_public_tenant(request=request, db=db)
    tenant_id = resolved.tenant.id
    page = await CmsPageService(db).get_published_by_slug(
        slug.strip("/"), tenant_id=tenant_id, locale=locale, default_locale=await _default_locale(db, tenant_id)
    )
    if not page:
        raise NotFoundError("Page not found")
    return SuccessResponse(data=PublicPage.model_validate(page).model_dump(by_alias=True))


@_public_routes.get("/posts")
async def public_posts(
    request: Request,
    db: DBSession,
    current_page: int = Query(1, ge=1, alias="currentPage"),
    page_size: int = Query(12, ge=1, le=50, alias="pageSize"),
    locale: str | None = None,
) -> Any:
    resolved = await resolve_public_tenant(request=request, db=db)
    tenant_id = resolved.tenant.id
    svc = CmsPostService(db)
    items, total = await svc.list_posts(
        tenant_id=tenant_id, page=current_page, page_size=page_size, published_only=True, locale=locale
    )
    # Fallback: if no posts exist for the requested locale, show the default-locale list.
    if locale and total == 0:
        fallback = await _default_locale(db, tenant_id)
        if fallback != locale:
            items, total = await svc.list_posts(
                tenant_id=tenant_id, page=current_page, page_size=page_size, published_only=True, locale=fallback
            )
        if total == 0:
            items, total = await svc.list_posts(
                tenant_id=tenant_id, page=current_page, page_size=page_size, published_only=True
            )
    return SuccessResponse(
        data={
            "list": [PublicPost.model_validate(p).model_dump(by_alias=True) for p in items],
            "total": total,
            "pageSize": page_size,
            "currentPage": current_page,
        }
    )


@_public_routes.get("/posts/{slug}")
async def public_post(slug: str, request: Request, db: DBSession, locale: str | None = None) -> Any:
    resolved = await resolve_public_tenant(request=request, db=db)
    tenant_id = resolved.tenant.id
    post = await CmsPostService(db).get_published_by_slug(
        slug.strip(), tenant_id=tenant_id, locale=locale, default_locale=await _default_locale(db, tenant_id)
    )
    if not post:
        raise NotFoundError("Post not found")
    return SuccessResponse(data=PublicPost.model_validate(post).model_dump(by_alias=True))


def _client_ip(request: Request) -> str:
    fwd = (request.headers.get("x-forwarded-for", "") or "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "unknown")


@_public_routes.get("/sitemap")
async def public_sitemap(request: Request, db: DBSession) -> Any:
    """Data for the frontend sitemap.xml: enabled locales + published slugs."""
    resolved = await resolve_public_tenant(request=request, db=db)
    tenant_id = resolved.tenant.id
    langs = await CmsLanguageService(db).list_languages(tenant_id=tenant_id, active_only=True)
    pages, _ = await CmsPageService(db).list_pages(
        tenant_id=tenant_id, page=1, page_size=500, status="published"
    )
    posts, _ = await CmsPostService(db).list_posts(
        tenant_id=tenant_id, page=1, page_size=500, published_only=True
    )

    def _dedupe(rows: list, getslug, getupd) -> list[dict[str, Any]]:
        seen: dict[str, str] = {}
        for r in rows:
            slug = getslug(r)
            upd = getupd(r)
            iso = upd.isoformat() if upd else None
            if slug not in seen or (iso and (seen[slug] is None or iso > seen[slug])):
                seen[slug] = iso
        return [{"slug": s, "updatedAt": u} for s, u in seen.items()]

    default_code = next((l.code for l in langs if l.is_default), (langs[0].code if langs else "zh-CN"))
    return SuccessResponse(
        data={
            "canonicalOrigin": resolved.canonical_origin,
            "defaultLocale": default_code,
            "locales": [l.code for l in langs],
            "pages": _dedupe(pages, lambda p: p.slug, lambda p: p.updated_at or p.published_at),
            "posts": _dedupe(posts, lambda p: p.slug, lambda p: p.published_at or p.updated_at),
        }
    )


@_public_routes.post("/contact")
async def public_contact(payload: dict, request: Request, db: DBSession) -> Any:
    # Validate via schema (kept loose at signature to attach honeypot handling).
    from app.core.exceptions import BusinessError
    from app.domain.cms.schemas import ContactCreate
    from app.infrastructure.cache.runtime_cache import get_json, set_json

    resolved = await resolve_public_tenant(request=request, db=db)
    data = ContactCreate.model_validate(payload)
    # Honeypot: if the hidden 'website' field is filled, silently accept (drop).
    if (data.website or "").strip():
        return SuccessResponse(message="ok")

    # Lightweight per-IP throttle: max 5 submissions / 10 min (best-effort; cache
    # degrades to local memory when Redis is unavailable).
    ip = _client_ip(request)
    rl_key = f"cms_contact_rl:{ip}"
    count = int(await get_json(rl_key) or 0)
    if count >= 5:
        raise BusinessError("提交过于频繁，请稍后再试")
    await set_json(rl_key, count + 1, ttl_seconds=600)

    record = {
        "name": data.name,
        "email": data.email,
        "company": data.company,
        "message": data.message,
        "source_page": data.source_page,
        "meta": {"ip": request.headers.get("x-forwarded-for", "")},
    }
    submission = await CmsContactService(db).submit(record, tenant_id=resolved.tenant.id)
    ticket = await _bridge_contact_to_support(
        db,
        tenant_id=resolved.tenant.id,
        data=data,
        submission_id=int(submission.id),
    )
    return SuccessResponse(
        data={
            "submissionId": int(submission.id),
            "ticketId": int(ticket.id) if ticket is not None else None,
            "ticketNo": ticket.ticket_no if ticket is not None else None,
        },
        message="Submitted",
    )


async def _bridge_contact_to_support(
    db: Any,
    *,
    tenant_id: int,
    data: Any,
    submission_id: int,
) -> Any | None:
    """Optionally open a support ticket for one contact submission.

    CMS **拥有**这条留言，工单只是可选的下游流程。所以三件事按顺序守住：

    1. `is_module_installed("support")`——工单包没装（甚至代码不在磁盘上）时
       连 import 都不做。`import` 一个不存在的可选包会让整个公开留言接口 500。
    2. `is_module_enabled_for_tenant`——装了但该租户关了，留言照样落库，
       只是不开单。这里**不能**用 `ensure_module_enabled_for_tenant`：
       那会把"别人的模块关着"变成本接口的 403。
    3. 延迟 import：CMS 的模块级 import 里不允许出现工单包，否则可选联动
       就变成了硬依赖，两个模块以后拆不开。
    """
    from app.core.feature_switches import is_module_installed
    from app.core.module_guards import is_module_enabled_for_tenant

    if not is_module_installed("support"):
        return None
    if not await is_module_enabled_for_tenant(db=db, tenant_id=tenant_id, module_code="support"):
        return None

    from app.capabilities.support.bridge import create_ticket_from_public_contact

    return await create_ticket_from_public_contact(
        db,
        tenant_id=tenant_id,
        name=data.name,
        email=data.email,
        message=data.message,
        company=data.company,
        source_page=data.source_page,
        submission_id=submission_id,
    )


def build_public_cms_router() -> APIRouter:
    """Build an empty router when the public CMS is not deployed."""
    result = APIRouter()
    if is_public_site_deployment_enabled():
        result.include_router(_public_routes)
    return result


router = build_public_cms_router()
