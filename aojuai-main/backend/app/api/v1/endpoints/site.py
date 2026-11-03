"""
AOJU Backend - Site Public Config Endpoints

These endpoints provide public (no-auth) site-level config such as SEO settings.
In multi-tenant mode, config is resolved by request host/domain when possible.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import DBSession
from app.core.public_site import resolve_public_tenant
from app.core.response import SuccessResponse
from app.core.schemas import ResponseBase
from app.infrastructure.cache.base_runtime_keys import (
    SITE_PUBLIC_CONFIG_TTL_SECONDS,
    build_site_public_config_cache_key,
)
from app.infrastructure.cache.runtime_cache import remember_json

router = APIRouter()


class SiteSeoConfig(BaseModel):
    title: str = ""
    keywords: str = ""
    description: str = ""


class SiteAppearanceConfig(BaseModel):
    primary_color: str | None = Field(None, alias="primaryColor")
    default_locale: str | None = Field(None, alias="defaultLocale")

    model_config = ConfigDict(populate_by_name=True)


class SitePublicConfig(BaseModel):
    tenant_id: int | None = Field(None, alias="tenantId")
    tenant_code: str | None = Field(None, alias="tenantCode")
    tenant_name: str | None = Field(None, alias="tenantName")
    canonical_origin: str | None = Field(None, alias="canonicalOrigin")
    seo: SiteSeoConfig = Field(default_factory=SiteSeoConfig)
    appearance: SiteAppearanceConfig = Field(default_factory=SiteAppearanceConfig)

    model_config = ConfigDict(populate_by_name=True)


@router.get("/public-config", response_model=ResponseBase[SitePublicConfig])
async def get_site_public_config(
    request: Request,
    db: DBSession,
) -> dict[str, Any]:
    """
    Public site config (no auth).

    Production resolves only an exact configured tenant domain.  A local
    development fallback is available only through CMS_DEFAULT_TENANT_CODE.
    """
    resolved = await resolve_public_tenant(request=request, db=db)
    tenant = resolved.tenant
    cache_key = build_site_public_config_cache_key(resolved.canonical_host)

    async def _load_public_config() -> dict[str, Any]:
        cfg = dict(getattr(tenant, "config", {}) or {})
        seo = dict(cfg.get("seo", {}) or {})
        appearance = dict(cfg.get("appearance", {}) or {})

        title = (seo.get("title") or tenant.name or "").strip()
        keywords = (seo.get("keywords") or "").strip()
        description = (seo.get("description") or "").strip()

        return {
            "tenantId": tenant.id,
            "tenantCode": tenant.code,
            "tenantName": tenant.name,
            "canonicalOrigin": resolved.canonical_origin,
            "seo": {
                "title": title,
                "keywords": keywords,
                "description": description,
            },
            "appearance": {
                "primaryColor": (appearance.get("primaryColor") or "").strip() or None,
                "defaultLocale": (appearance.get("defaultLocale") or "").strip() or None,
            },
        }

    payload = await remember_json(
        cache_key,
        ttl_seconds=SITE_PUBLIC_CONFIG_TTL_SECONDS,
        loader=_load_public_config,
    )
    return SuccessResponse(data=payload)
