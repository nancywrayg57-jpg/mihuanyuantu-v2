"""
AOJU Backend - CMS Service

Tenant-scoped CRUD for pages, posts, navigation, site settings and contact
submissions. All queries are filtered by tenant_id (never trust the UI alone).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.provider_secrets import decrypt_provider_secret_or_plain, encrypt_provider_secret
from app.domain.cms.models import (
    CmsContactSubmission,
    CmsLanguage,
    CmsNavigation,
    CmsPage,
    CmsPost,
    CmsSiteSettings,
    ContentStatus,
)
from app.infrastructure.repository import RepositoryBase


def _now() -> datetime:
    return datetime.now(UTC)


class CmsLanguageService(RepositoryBase[CmsLanguage]):
    """The language taxonomy: managed list of real languages, one default."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, CmsLanguage)

    async def list_languages(self, *, tenant_id: int, active_only: bool = False) -> list[CmsLanguage]:
        where = [CmsLanguage.tenant_id == tenant_id]
        if active_only:
            where.append(CmsLanguage.is_active.is_(True))
        return await self.get_list(page=1, page_size=100, where=where, order_by="sort_order")

    async def default_code(self, *, tenant_id: int) -> str:
        row = await self.get_one(
            where=[CmsLanguage.tenant_id == tenant_id, CmsLanguage.is_default.is_(True)]
        )
        if row:
            return row.code
        rows = await self.list_languages(tenant_id=tenant_id, active_only=True)
        return rows[0].code if rows else "zh-CN"

    async def get_by_code(self, code: str, *, tenant_id: int) -> CmsLanguage | None:
        return await self.get_one(
            where=[CmsLanguage.tenant_id == tenant_id, CmsLanguage.code == code]
        )

    async def create_language(self, data: dict[str, Any], *, tenant_id: int) -> CmsLanguage:
        if await self.get_by_code(data.get("code"), tenant_id=tenant_id):
            raise ConflictError(f"Language '{data.get('code')}' already exists")
        payload = dict(data)
        payload["tenant_id"] = tenant_id
        if payload.get("is_default"):
            await self._clear_defaults(tenant_id=tenant_id)
        return await self.create(payload)

    async def update_language(self, obj: CmsLanguage, data: dict[str, Any], *, tenant_id: int) -> CmsLanguage:
        if data.get("is_default"):
            await self._clear_defaults(tenant_id=tenant_id)
        return await self.update(obj, data)

    async def set_default(self, code: str, *, tenant_id: int) -> None:
        await self._clear_defaults(tenant_id=tenant_id)
        target = await self.get_by_code(code, tenant_id=tenant_id)
        if target:
            await self.update(target, {"is_default": True, "is_active": True})

    async def _clear_defaults(self, *, tenant_id: int) -> None:
        from sqlalchemy import update as sa_update

        await self.db.execute(
            sa_update(CmsLanguage)
            .where(CmsLanguage.tenant_id == tenant_id, CmsLanguage.is_default.is_(True))
            .values(is_default=False)
        )
        await self.db.flush()


class CmsPageService(RepositoryBase[CmsPage]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, CmsPage)

    async def list_pages(
        self,
        *,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        keyword: str | None = None,
    ) -> tuple[list[CmsPage], int]:
        where = [CmsPage.tenant_id == tenant_id]
        if status:
            where.append(CmsPage.status == status)
        if keyword:
            like = f"%{keyword.strip()}%"
            where.append(CmsPage.title.ilike(like))
        return await self.get_list(  # type: ignore[return-value]
            page=page,
            page_size=page_size,
            where=where,
            order_by="sort_order",
            return_total=True,
        )

    async def get_for_tenant(self, page_id: int, *, tenant_id: int) -> CmsPage | None:
        return await self.get_one(
            where=[CmsPage.id == page_id, CmsPage.tenant_id == tenant_id]
        )

    async def get_published_by_slug(
        self, slug: str, *, tenant_id: int, locale: str | None = None, default_locale: str | None = None
    ) -> CmsPage | None:
        """Resolve a published page by slug: requested language → default language → any."""
        order: list[str] = []
        for loc in (locale, default_locale):
            if loc and loc not in order:
                order.append(loc)
        for loc in order:
            page = await self.get_one(
                where=[
                    CmsPage.tenant_id == tenant_id,
                    CmsPage.slug == slug,
                    CmsPage.locale == loc,
                    CmsPage.status == ContentStatus.PUBLISHED.value,
                ]
            )
            if page:
                return page
        # Last resort: any published language for this slug.
        return await self.get_one(
            where=[
                CmsPage.tenant_id == tenant_id,
                CmsPage.slug == slug,
                CmsPage.status == ContentStatus.PUBLISHED.value,
            ],
            order_by="locale",
        )

    async def create_page(self, data: dict[str, Any], *, tenant_id: int, user_id: int) -> CmsPage:
        payload = dict(data)
        locale = payload.get("locale") or "default"
        if await self.get_one(
            where=[CmsPage.tenant_id == tenant_id, CmsPage.slug == payload.get("slug"), CmsPage.locale == locale]
        ):
            raise ConflictError(f"Slug '{payload.get('slug')}' ({locale}) already exists")
        payload["tenant_id"] = tenant_id
        payload["created_by"] = user_id
        payload["updated_by"] = user_id
        if payload.get("status") == ContentStatus.PUBLISHED.value:
            payload["published_at"] = _now()
        return await self.create(payload)

    async def update_page(self, obj: CmsPage, data: dict[str, Any], *, user_id: int) -> CmsPage:
        payload = dict(data)
        payload["updated_by"] = user_id
        if "status" in payload:
            if payload["status"] == ContentStatus.PUBLISHED.value and not obj.published_at:
                payload["published_at"] = _now()  # stamp on first publish
            elif payload["status"] == ContentStatus.DRAFT.value:
                payload["published_at"] = None  # clear when unpublished
        return await self.update(obj, payload)


class CmsPostService(RepositoryBase[CmsPost]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, CmsPost)

    async def list_posts(
        self,
        *,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        keyword: str | None = None,
        published_only: bool = False,
        locale: str | None = None,
    ) -> tuple[list[CmsPost], int]:
        where = [CmsPost.tenant_id == tenant_id]
        if published_only:
            where.append(CmsPost.status == ContentStatus.PUBLISHED.value)
            if locale:
                where.append(CmsPost.locale == locale)
        elif status:
            where.append(CmsPost.status == status)
        if keyword:
            like = f"%{keyword.strip()}%"
            where.append(CmsPost.title.ilike(like))
        return await self.get_list(  # type: ignore[return-value]
            page=page,
            page_size=page_size,
            where=where,
            order_by="published_at" if published_only else "updated_at",
            order_desc=True,
            return_total=True,
        )

    async def get_for_tenant(self, post_id: int, *, tenant_id: int) -> CmsPost | None:
        return await self.get_one(
            where=[CmsPost.id == post_id, CmsPost.tenant_id == tenant_id]
        )

    async def get_published_by_slug(
        self, slug: str, *, tenant_id: int, locale: str | None = None, default_locale: str | None = None
    ) -> CmsPost | None:
        order: list[str] = []
        for loc in (locale, default_locale):
            if loc and loc not in order:
                order.append(loc)
        for loc in order:
            post = await self.get_one(
                where=[
                    CmsPost.tenant_id == tenant_id,
                    CmsPost.slug == slug,
                    CmsPost.locale == loc,
                    CmsPost.status == ContentStatus.PUBLISHED.value,
                ]
            )
            if post:
                return post
        return await self.get_one(
            where=[
                CmsPost.tenant_id == tenant_id,
                CmsPost.slug == slug,
                CmsPost.status == ContentStatus.PUBLISHED.value,
            ],
            order_by="locale",
        )

    async def create_post(self, data: dict[str, Any], *, tenant_id: int, user_id: int) -> CmsPost:
        payload = dict(data)
        locale = payload.get("locale") or "default"
        if await self.get_one(
            where=[CmsPost.tenant_id == tenant_id, CmsPost.slug == payload.get("slug"), CmsPost.locale == locale]
        ):
            raise ConflictError(f"Slug '{payload.get('slug')}' ({locale}) already exists")
        payload["tenant_id"] = tenant_id
        payload["created_by"] = user_id
        payload["updated_by"] = user_id
        if payload.get("status") == ContentStatus.PUBLISHED.value:
            payload["published_at"] = _now()
        return await self.create(payload)

    async def update_post(self, obj: CmsPost, data: dict[str, Any], *, user_id: int) -> CmsPost:
        payload = dict(data)
        payload["updated_by"] = user_id
        if "status" in payload:
            if payload["status"] == ContentStatus.PUBLISHED.value and not obj.published_at:
                payload["published_at"] = _now()
            elif payload["status"] == ContentStatus.DRAFT.value:
                payload["published_at"] = None
        return await self.update(obj, payload)


class CmsNavigationService(RepositoryBase[CmsNavigation]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, CmsNavigation)

    async def get_by_location(self, location: str, *, tenant_id: int) -> CmsNavigation | None:
        return await self.get_one(
            where=[CmsNavigation.tenant_id == tenant_id, CmsNavigation.location == location]
        )

    async def upsert(self, location: str, items: list[dict[str, Any]], *, tenant_id: int) -> CmsNavigation:
        existing = await self.get_by_location(location, tenant_id=tenant_id)
        if existing:
            return await self.update(existing, {"items": items})
        return await self.create(
            {"tenant_id": tenant_id, "location": location, "items": items}
        )


class CmsSiteSettingsService(RepositoryBase[CmsSiteSettings]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, CmsSiteSettings)

    async def get_for_tenant(self, *, tenant_id: int) -> CmsSiteSettings | None:
        return await self.get_one(where=[CmsSiteSettings.tenant_id == tenant_id])

    async def upsert(self, settings: dict[str, Any], *, tenant_id: int) -> CmsSiteSettings:
        existing = await self.get_for_tenant(tenant_id=tenant_id)
        if existing:
            return await self.update(existing, {"settings": settings})
        return await self.create({"tenant_id": tenant_id, "settings": settings})

    # ---- CMS-scoped AI provider config (admin-only; never served publicly) ----
    async def get_ai_config(self, *, tenant_id: int) -> dict[str, Any]:
        row = await self.get_for_tenant(tenant_id=tenant_id)
        return dict(row.ai_config or {}) if row else {}

    @staticmethod
    def decrypt_ai_key(ai_config: dict[str, Any]) -> str | None:
        return decrypt_provider_secret_or_plain(ai_config.get("apiKey"))

    async def set_ai_config(self, data: dict[str, Any], *, tenant_id: int) -> dict[str, Any]:
        """Merge AI config; only (re)encrypt the api key when a new one is supplied."""
        row = await self.get_for_tenant(tenant_id=tenant_id)
        current = dict(row.ai_config) if (row and row.ai_config) else {}
        for key in ("mode", "baseUrl", "model", "temperature", "maxTokens"):
            if key in data and data[key] is not None:
                current[key] = data[key]
        new_key = (data.get("apiKey") or "").strip()
        if new_key:
            current["apiKey"] = encrypt_provider_secret(new_key)
        elif data.get("clearApiKey"):
            current.pop("apiKey", None)
        if row:
            await self.update(row, {"ai_config": current})
        else:
            await self.create({"tenant_id": tenant_id, "settings": {}, "ai_config": current})
        return current


class CmsContactService(RepositoryBase[CmsContactSubmission]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, CmsContactSubmission)

    async def list_submissions(
        self,
        *,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[CmsContactSubmission], int]:
        where = [CmsContactSubmission.tenant_id == tenant_id]
        if status:
            where.append(CmsContactSubmission.status == status)
        return await self.get_list(  # type: ignore[return-value]
            page=page,
            page_size=page_size,
            where=where,
            order_by="created_at",
            order_desc=True,
            return_total=True,
        )

    async def get_for_tenant(self, sub_id: int, *, tenant_id: int) -> CmsContactSubmission | None:
        return await self.get_one(
            where=[
                CmsContactSubmission.id == sub_id,
                CmsContactSubmission.tenant_id == tenant_id,
            ]
        )

    async def submit(self, data: dict[str, Any], *, tenant_id: int) -> CmsContactSubmission:
        payload = dict(data)
        payload["tenant_id"] = tenant_id
        return await self.create(payload)
