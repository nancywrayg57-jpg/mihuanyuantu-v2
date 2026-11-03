"""
AOJU Backend - CMS Admin Endpoints

All endpoints require auth + a `cms:*` permission. Everything is scoped to the
caller's tenant_id (PermissionChecker enforces RBAC; tenant_id enforces isolation).
Mounted at /api/v1/cms.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DBSession, PermissionChecker
from app.core.exceptions import NotFoundError
from app.core.response import SuccessResponse
from app.domain.cms.models import ContentStatus, NavLocation
from app.domain.cms.schemas import (
    CmsAiConfigUpdate,
    LanguageCreate,
    LanguageItem,
    LanguageUpdate,
    NavigationDetail,
    NavigationUpdate,
    PageCreate,
    PageDetail,
    PageListItem,
    PageUpdate,
    PostCreate,
    PostDetail,
    PostListItem,
    PostUpdate,
    SiteSettingsDetail,
    SiteSettingsUpdate,
    SubmissionItem,
    SubmissionUpdate,
)
from app.domain.cms.service import (
    CmsContactService,
    CmsLanguageService,
    CmsNavigationService,
    CmsPageService,
    CmsPostService,
    CmsSiteSettingsService,
)

router = APIRouter()


def _page_list_item(p) -> dict[str, Any]:
    return PageListItem.model_validate(p).model_dump(by_alias=True)


def _page_detail(p) -> dict[str, Any]:
    return PageDetail.model_validate(p).model_dump(by_alias=True)


def _post_list_item(p) -> dict[str, Any]:
    return PostListItem.model_validate(p).model_dump(by_alias=True)


def _post_detail(p) -> dict[str, Any]:
    return PostDetail.model_validate(p).model_dump(by_alias=True)


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@router.get("/pages")
async def list_pages(
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:page:read"])),
    current_page: int = Query(1, ge=1, alias="currentPage"),
    page_size: int = Query(20, ge=1, le=200, alias="pageSize"),
    status: str | None = None,
    keyword: str | None = None,
) -> Any:
    service = CmsPageService(db)
    items, total = await service.list_pages(
        tenant_id=current_user.tenant_id,
        page=current_page,
        page_size=page_size,
        status=status,
        keyword=keyword,
    )
    return SuccessResponse(
        data={
            "list": [_page_list_item(p) for p in items],
            "total": total,
            "pageSize": page_size,
            "currentPage": current_page,
        }
    )


@router.get("/pages/{page_id}")
async def get_page(
    page_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:page:read"])),
) -> Any:
    service = CmsPageService(db)
    page = await service.get_for_tenant(page_id, tenant_id=current_user.tenant_id)
    if not page:
        raise NotFoundError("Page not found")
    return SuccessResponse(data=_page_detail(page))


@router.post("/pages")
async def create_page(
    payload: PageCreate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:page:create"])),
) -> Any:
    service = CmsPageService(db)
    data = payload.model_dump(by_alias=False)
    data["status"] = data["status"].value if hasattr(data["status"], "value") else data["status"]
    if not data.get("locale") or data["locale"] == "default":
        data["locale"] = await CmsLanguageService(db).default_code(tenant_id=current_user.tenant_id)
    page = await service.create_page(
        data, tenant_id=current_user.tenant_id, user_id=current_user.id
    )
    return SuccessResponse(data=_page_detail(page), message="Created", code="CREATED")


@router.put("/pages/{page_id}")
async def update_page(
    page_id: int,
    payload: PageUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:page:update"])),
) -> Any:
    service = CmsPageService(db)
    page = await service.get_for_tenant(page_id, tenant_id=current_user.tenant_id)
    if not page:
        raise NotFoundError("Page not found")
    data = payload.model_dump(by_alias=False, exclude_unset=True)
    if "status" in data and hasattr(data["status"], "value"):
        data["status"] = data["status"].value
    page = await service.update_page(page, data, user_id=current_user.id)
    return SuccessResponse(data=_page_detail(page), message="Updated")


@router.post("/pages/{page_id}/publish")
async def publish_page(
    page_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:page:publish"])),
    publish: bool = Query(True),
) -> Any:
    service = CmsPageService(db)
    page = await service.get_for_tenant(page_id, tenant_id=current_user.tenant_id)
    if not page:
        raise NotFoundError("Page not found")
    status = ContentStatus.PUBLISHED.value if publish else ContentStatus.DRAFT.value
    page = await service.update_page(page, {"status": status}, user_id=current_user.id)
    return SuccessResponse(data=_page_detail(page), message="Updated")


@router.delete("/pages/{page_id}")
async def delete_page(
    page_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:page:delete"])),
) -> Any:
    service = CmsPageService(db)
    page = await service.get_for_tenant(page_id, tenant_id=current_user.tenant_id)
    if not page:
        raise NotFoundError("Page not found")
    if page.is_system:
        from app.core.exceptions import BusinessError

        raise BusinessError("System pages cannot be deleted")
    await service.delete(page)
    return SuccessResponse(message="Deleted")


# --------------------------------------------------------------------------- #
# Posts
# --------------------------------------------------------------------------- #
@router.get("/posts")
async def list_posts(
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:post:read"])),
    current_page: int = Query(1, ge=1, alias="currentPage"),
    page_size: int = Query(20, ge=1, le=200, alias="pageSize"),
    status: str | None = None,
    keyword: str | None = None,
) -> Any:
    service = CmsPostService(db)
    items, total = await service.list_posts(
        tenant_id=current_user.tenant_id,
        page=current_page,
        page_size=page_size,
        status=status,
        keyword=keyword,
    )
    return SuccessResponse(
        data={
            "list": [_post_list_item(p) for p in items],
            "total": total,
            "pageSize": page_size,
            "currentPage": current_page,
        }
    )


@router.get("/posts/{post_id}")
async def get_post(
    post_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:post:read"])),
) -> Any:
    service = CmsPostService(db)
    post = await service.get_for_tenant(post_id, tenant_id=current_user.tenant_id)
    if not post:
        raise NotFoundError("Post not found")
    return SuccessResponse(data=_post_detail(post))


@router.post("/posts")
async def create_post(
    payload: PostCreate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:post:create"])),
) -> Any:
    service = CmsPostService(db)
    data = payload.model_dump(by_alias=False)
    data["status"] = data["status"].value if hasattr(data["status"], "value") else data["status"]
    if not data.get("locale") or data["locale"] == "default":
        data["locale"] = await CmsLanguageService(db).default_code(tenant_id=current_user.tenant_id)
    post = await service.create_post(
        data, tenant_id=current_user.tenant_id, user_id=current_user.id
    )
    return SuccessResponse(data=_post_detail(post), message="Created", code="CREATED")


@router.put("/posts/{post_id}")
async def update_post(
    post_id: int,
    payload: PostUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:post:update"])),
) -> Any:
    service = CmsPostService(db)
    post = await service.get_for_tenant(post_id, tenant_id=current_user.tenant_id)
    if not post:
        raise NotFoundError("Post not found")
    data = payload.model_dump(by_alias=False, exclude_unset=True)
    if "status" in data and hasattr(data["status"], "value"):
        data["status"] = data["status"].value
    post = await service.update_post(post, data, user_id=current_user.id)
    return SuccessResponse(data=_post_detail(post), message="Updated")


@router.post("/posts/{post_id}/publish")
async def publish_post(
    post_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:post:publish"])),
    publish: bool = Query(True),
) -> Any:
    service = CmsPostService(db)
    post = await service.get_for_tenant(post_id, tenant_id=current_user.tenant_id)
    if not post:
        raise NotFoundError("Post not found")
    status = ContentStatus.PUBLISHED.value if publish else ContentStatus.DRAFT.value
    post = await service.update_post(post, {"status": status}, user_id=current_user.id)
    return SuccessResponse(data=_post_detail(post), message="Updated")


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:post:delete"])),
) -> Any:
    service = CmsPostService(db)
    post = await service.get_for_tenant(post_id, tenant_id=current_user.tenant_id)
    if not post:
        raise NotFoundError("Post not found")
    await service.delete(post)
    return SuccessResponse(message="Deleted")


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #
@router.get("/navigation")
async def get_navigation(
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:nav:read"])),
) -> Any:
    service = CmsNavigationService(db)
    out: list[dict[str, Any]] = []
    for loc in (NavLocation.HEADER.value, NavLocation.FOOTER.value):
        nav = await service.get_by_location(loc, tenant_id=current_user.tenant_id)
        out.append(
            NavigationDetail(location=loc, items=nav.items if nav else []).model_dump(by_alias=True)
        )
    return SuccessResponse(data={"list": out})


@router.put("/navigation/{location}")
async def update_navigation(
    location: str,
    payload: NavigationUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:nav:update"])),
) -> Any:
    if location not in (NavLocation.HEADER.value, NavLocation.FOOTER.value):
        from app.core.exceptions import ValidationError

        raise ValidationError("Invalid navigation location")
    service = CmsNavigationService(db)
    nav = await service.upsert(location, payload.items, tenant_id=current_user.tenant_id)
    return SuccessResponse(
        data=NavigationDetail(location=nav.location, items=nav.items).model_dump(by_alias=True),
        message="Updated",
    )


# --------------------------------------------------------------------------- #
# Site settings
# --------------------------------------------------------------------------- #
@router.get("/settings")
async def get_settings(
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:settings:read"])),
) -> Any:
    service = CmsSiteSettingsService(db)
    row = await service.get_for_tenant(tenant_id=current_user.tenant_id)
    return SuccessResponse(
        data=SiteSettingsDetail(settings=row.settings if row else {}).model_dump(by_alias=True)
    )


@router.put("/settings")
async def update_settings(
    payload: SiteSettingsUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:settings:update"])),
) -> Any:
    service = CmsSiteSettingsService(db)
    row = await service.upsert(payload.settings, tenant_id=current_user.tenant_id)
    return SuccessResponse(
        data=SiteSettingsDetail(settings=row.settings).model_dump(by_alias=True),
        message="Updated",
    )


# --------------------------------------------------------------------------- #
# CMS AI config (defaults to inheriting the system/assistant AI config)
# --------------------------------------------------------------------------- #
@router.get("/ai-config")
async def get_ai_config(
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:settings:read"])),
) -> Any:
    from app.domain.assistant.config_service import AssistantConfigService

    service = CmsSiteSettingsService(db)
    ai = await service.get_ai_config(tenant_id=current_user.tenant_id)
    system = await AssistantConfigService(db).get_provider_settings(current_user.tenant_id)
    data = {
        "mode": ai.get("mode") or "inherit",
        "baseUrl": ai.get("baseUrl"),
        "model": ai.get("model"),
        "temperature": ai.get("temperature"),
        "maxTokens": ai.get("maxTokens"),
        "hasApiKey": bool(ai.get("apiKey")),
        "systemConfigured": bool(system and system.get("api_key") and system.get("base_url")),
    }
    return SuccessResponse(data=data)


@router.put("/ai-config")
async def update_ai_config(
    payload: CmsAiConfigUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:settings:update"])),
) -> Any:
    service = CmsSiteSettingsService(db)
    await service.set_ai_config(
        payload.model_dump(by_alias=True, exclude_unset=True), tenant_id=current_user.tenant_id
    )
    ai = await service.get_ai_config(tenant_id=current_user.tenant_id)
    return SuccessResponse(
        data={
            "mode": ai.get("mode") or "inherit",
            "baseUrl": ai.get("baseUrl"),
            "model": ai.get("model"),
            "temperature": ai.get("temperature"),
            "maxTokens": ai.get("maxTokens"),
            "hasApiKey": bool(ai.get("apiKey")),
        },
        message="Updated",
    )


# --------------------------------------------------------------------------- #
# Languages (taxonomy)
# --------------------------------------------------------------------------- #
@router.get("/languages")
async def list_languages(
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:settings:read"])),
) -> Any:
    rows = await CmsLanguageService(db).list_languages(tenant_id=current_user.tenant_id)
    return SuccessResponse(
        data={"list": [LanguageItem.model_validate(r).model_dump(by_alias=True) for r in rows]}
    )


@router.post("/languages")
async def create_language(
    payload: LanguageCreate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:settings:update"])),
) -> Any:
    row = await CmsLanguageService(db).create_language(
        payload.model_dump(by_alias=False), tenant_id=current_user.tenant_id
    )
    return SuccessResponse(data=LanguageItem.model_validate(row).model_dump(by_alias=True), code="CREATED")


@router.put("/languages/{lang_id}")
async def update_language(
    lang_id: int,
    payload: LanguageUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:settings:update"])),
) -> Any:
    service = CmsLanguageService(db)
    row = await service.get_for_tenant(lang_id, tenant_id=current_user.tenant_id) if hasattr(service, "get_for_tenant") else None
    if not row:
        from app.domain.cms.models import CmsLanguage

        row = await service.get_one(
            where=[CmsLanguage.id == lang_id, CmsLanguage.tenant_id == current_user.tenant_id]
        )
    if not row:
        raise NotFoundError("Language not found")
    row = await service.update_language(
        row, payload.model_dump(by_alias=False, exclude_unset=True), tenant_id=current_user.tenant_id
    )
    return SuccessResponse(data=LanguageItem.model_validate(row).model_dump(by_alias=True))


@router.delete("/languages/{lang_id}")
async def delete_language(
    lang_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:settings:update"])),
) -> Any:
    from app.core.exceptions import BusinessError
    from app.domain.cms.models import CmsLanguage

    service = CmsLanguageService(db)
    row = await service.get_one(
        where=[CmsLanguage.id == lang_id, CmsLanguage.tenant_id == current_user.tenant_id]
    )
    if not row:
        raise NotFoundError("Language not found")
    if row.is_default:
        raise BusinessError("默认语言不能删除")
    await service.delete(row)
    return SuccessResponse(message="Deleted")


# --------------------------------------------------------------------------- #
# Contact submissions (leads)
# --------------------------------------------------------------------------- #
@router.get("/submissions")
async def list_submissions(
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:contact:read"])),
    current_page: int = Query(1, ge=1, alias="currentPage"),
    page_size: int = Query(20, ge=1, le=200, alias="pageSize"),
    status: str | None = None,
) -> Any:
    service = CmsContactService(db)
    items, total = await service.list_submissions(
        tenant_id=current_user.tenant_id,
        page=current_page,
        page_size=page_size,
        status=status,
    )
    return SuccessResponse(
        data={
            "list": [SubmissionItem.model_validate(s).model_dump(by_alias=True) for s in items],
            "total": total,
            "pageSize": page_size,
            "currentPage": current_page,
        }
    )


@router.put("/submissions/{sub_id}")
async def update_submission(
    sub_id: int,
    payload: SubmissionUpdate,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:contact:update"])),
) -> Any:
    service = CmsContactService(db)
    sub = await service.get_for_tenant(sub_id, tenant_id=current_user.tenant_id)
    if not sub:
        raise NotFoundError("Submission not found")
    sub = await service.update(
        sub, {"status": payload.status.value, "handled_by": current_user.id}
    )
    return SuccessResponse(
        data=SubmissionItem.model_validate(sub).model_dump(by_alias=True), message="Updated"
    )
