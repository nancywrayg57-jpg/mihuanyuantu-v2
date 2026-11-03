"""
AOJU Backend - Tenant Management Endpoints

Note: These endpoints are for system-level admin only (superuser).
"""
from typing import Any

from fastapi import APIRouter
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.api.deps import CurrentSuperuser, DBSession
from app.core.response import ErrorResponse, SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.auth.schemas import (
    RegistrationConfigUpdate,
    TenantCreateWithAdmin,
    TenantListItem,
    TenantResponse,
    TenantSimpleItem,
    TenantUpdate,
    TenantUserItem,
)
from app.domain.auth.service import TenantService
from app.infrastructure.cache import (
    bump_site_public_config_cache_version,
    bump_tenant_ui_config_cache_version,
)
from app.infrastructure.cache.base_runtime_keys import (
    invalidate_site_public_config_cache,
    invalidate_tenant_runtime_cache,
)

router = APIRouter()


# ============== Schemas ==============


class TenantListQuery(BaseModel):
    """Tenant list query parameters"""

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    name: str | None = None
    is_active: bool | None = Field(None, alias="isActive")
    # 排序参数
    sort_by: str | None = Field(
        None,
        alias="sortBy",
        description="排序字段: id, name, code, created_at",
    )
    sort_order: str | None = Field(
        None,
        alias="sortOrder",
        description="排序方向: asc, desc",
    )

    model_config = ConfigDict(populate_by_name=True)


# ============== Endpoints ==============


@router.get("/all", response_model=ResponseBase[list[TenantSimpleItem]])
async def get_all_tenants(
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get all tenants for dropdown select (superuser only).
    """
    service = TenantService(db)
    tenants = await service.get_all_tenants(is_active=True)

    return SuccessResponse(
        data=[{"id": t.id, "name": t.name, "code": t.code} for t in tenants]
    )


@router.post("", response_model=ResponseBase[PageResponse[TenantListItem]])
async def get_tenant_list(
    query: TenantListQuery,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get tenant list with pagination (superuser only).
    """
    service = TenantService(db)
    tenants, total = await service.list_tenants(
        page=query.page,
        page_size=query.page_size,
        name=query.name,
        is_active=query.is_active,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    return SuccessResponse(
        data={
            "list": [TenantService.to_list_item(t) for t in tenants],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/current", response_model=ResponseBase[TenantResponse])
async def get_current_tenant(
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get current user's tenant info.
    """
    service = TenantService(db)
    tenant = await service.get_by_id(current_user.tenant_id)

    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    return SuccessResponse(data=TenantService.to_response(tenant))


@router.get("/{tenant_id}", response_model=ResponseBase[TenantResponse])
async def get_tenant(
    tenant_id: int,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get tenant by ID (superuser only).
    """
    service = TenantService(db)
    tenant = await service.get_by_id(tenant_id)

    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    return SuccessResponse(data=TenantService.to_response(tenant))


@router.post("/create", response_model=ResponseBase[TenantResponse])
async def create_tenant(
    data: TenantCreateWithAdmin,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Create new tenant with optional initial admin (superuser only).

    If initialAdmin is provided, will create:
    - Default roles (admin, user) for the tenant
    - Initial admin user with admin role
    """
    service = TenantService(db)
    tenant, admin_user = await service.create_tenant_with_admin(data)
    await bump_site_public_config_cache_version()
    await invalidate_site_public_config_cache()

    result = TenantService.to_response(tenant)
    if admin_user:
        result["initialAdmin"] = {
            "id": admin_user.id,
            "username": admin_user.username,
        }

    return SuccessResponse(data=result)


@router.put("/{tenant_id}", response_model=ResponseBase[TenantResponse])
async def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Update tenant (superuser only).
    """
    service = TenantService(db)
    tenant = await service.update_tenant(tenant_id, data)
    await bump_site_public_config_cache_version()
    await bump_tenant_ui_config_cache_version(tenant_id)
    await invalidate_tenant_runtime_cache(tenant.id)

    return SuccessResponse(data=TenantService.to_response(tenant))


@router.put("/{tenant_id}/registration", response_model=ResponseBase[TenantResponse])
async def update_tenant_registration(
    tenant_id: int,
    data: RegistrationConfigUpdate,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Update tenant registration configuration (superuser only).

    This allows tenant admin to configure:
    - enabled: Whether self-registration is allowed
    - requireAudit: Whether new registrations need approval
    - defaultRole: Default role for approved users
    """
    service = TenantService(db)
    tenant = await service.update_registration_config(tenant_id, data)
    await bump_site_public_config_cache_version()
    await bump_tenant_ui_config_cache_version(tenant_id)
    await invalidate_tenant_runtime_cache(tenant.id)

    return SuccessResponse(data=TenantService.to_response(tenant))


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Delete tenant (superuser only, soft delete).
    """
    service = TenantService(db)
    await service.delete_tenant(tenant_id)
    await bump_site_public_config_cache_version()
    await bump_tenant_ui_config_cache_version(tenant_id)
    await invalidate_tenant_runtime_cache(tenant_id)

    return SuccessResponse(message="Tenant deleted")


# ============== Tenant User Management ==============


class TenantUserQuery(BaseModel):
    """Tenant user list query"""
    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    username: str | None = None
    is_admin: bool | None = Field(None, alias="isAdmin")

    model_config = ConfigDict(populate_by_name=True)


class SetAdminRequest(BaseModel):
    """Set user admin status request"""
    is_admin: bool = Field(..., alias="isAdmin")

    model_config = ConfigDict(populate_by_name=True)


@router.post("/{tenant_id}/users", response_model=ResponseBase[PageResponse[TenantUserItem]])
async def get_tenant_users(
    tenant_id: int,
    query: TenantUserQuery,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get users belonging to a tenant (superuser only).
    """
    service = TenantService(db)

    # Verify tenant exists
    tenant = await service.get_by_id(tenant_id)
    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    users, total = await service.get_tenant_users(
        tenant_id=tenant_id,
        page=query.page,
        page_size=query.page_size,
        username=query.username,
        is_admin=query.is_admin,
    )

    return SuccessResponse(
        data={
            "list": users,
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.put("/{tenant_id}/users/{user_id}/admin")
async def set_user_admin(
    tenant_id: int,
    user_id: int,
    data: SetAdminRequest,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Set or remove admin role for a user in tenant (superuser only).
    """
    service = TenantService(db)

    # Verify tenant exists
    tenant = await service.get_by_id(tenant_id)
    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    result = await service.set_user_admin(
        tenant_id=tenant_id,
        user_id=user_id,
        is_admin=data.is_admin,
    )

    return SuccessResponse(data=result)
