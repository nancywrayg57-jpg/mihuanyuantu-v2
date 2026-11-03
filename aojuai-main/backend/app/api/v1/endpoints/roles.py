"""
AOJU Backend - Role Management Endpoints

权限设计:
- 系统管理员 (is_superuser=True): 可以通过 X-Tenant-Id 或 tenant_id 参数管理任意租户的角色
- 租户管理员 (roles 包含 admin): 只能管理本租户的角色
- 数据权限控制: 只能配置有权限的团队
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.api.deps import CurrentUser, DataScopeCtx, DBSession, PermissionChecker, TenantCtx
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logger import get_logger
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.roles.service import RoleService

logger = get_logger(__name__)

router = APIRouter()


# ============== Schemas ==============


class RoleListQuery(BaseModel):
    """Role list query parameters"""

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    name: str | None = None
    code: str | None = None
    is_active: bool | None = Field(None, alias="isActive")
    status: int | None = None  # legacy (0/1)
    # 排序参数
    sort_by: str | None = Field(
        None,
        alias="sortBy",
        description="排序字段: id, name, code, sort_order, created_at",
    )
    sort_order: str | None = Field(
        None,
        alias="sortOrder",
        description="排序方向: asc, desc",
    )

    model_config = ConfigDict(populate_by_name=True)


class RoleItem(BaseModel):
    """Role list item"""

    id: int
    name: str
    code: str
    description: str | None = None
    is_system: bool = Field(False, alias="isSystem")
    is_active: bool = Field(True, alias="isActive")
    sort_order: int = Field(0, alias="sortOrder")
    menu_ids: list[int] = Field(default_factory=list, alias="menuIds")
    data_range: int = Field(4, alias="dataRange")
    data_permissions: int = Field(0, alias="dataPermissions")
    team_permissions: list[dict[str, Any]] = Field(default_factory=list, alias="teamPermissions")
    created_at: str | None = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class RoleListResponse(ResponseBase[PageResponse[RoleItem]]):
    """Role list response"""

    pass


class AllRoleItem(BaseModel):
    """Simple role item for dropdowns"""

    id: int
    name: str
    code: str


class AllRoleListResponse(ResponseBase[list[AllRoleItem]]):
    """All roles response"""

    pass


class TeamPermission(BaseModel):
    """Team permission item"""
    id: int
    permissions: int = 0


class RoleCreate(BaseModel):
    """Role creation schema"""

    name: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=200)
    sort_order: int = Field(0, alias="sortOrder")
    is_active: bool = Field(True, alias="isActive")
    menu_ids: list[int] | None = Field(None, alias="menuIds")
    data_range: int = Field(4, alias="dataRange")
    data_permissions: int = Field(0, alias="dataPermissions")
    team_permissions: list[TeamPermission] | None = Field(None, alias="teamPermissions")

    model_config = ConfigDict(populate_by_name=True)


class RoleUpdate(BaseModel):
    """Role update schema"""

    name: str | None = None
    code: str | None = None
    description: str | None = Field(None, max_length=200)
    sort_order: int | None = Field(None, alias="sortOrder")
    is_active: bool | None = Field(None, alias="isActive")
    menu_ids: list[int] | None = Field(None, alias="menuIds")
    data_range: int | None = Field(None, alias="dataRange")
    data_permissions: int | None = Field(None, alias="dataPermissions")
    team_permissions: list[TeamPermission] | None = Field(None, alias="teamPermissions")

    model_config = ConfigDict(populate_by_name=True)


class MenuAssign(BaseModel):
    """Menu assignment schema"""

    menu_ids: list[int] = Field(default_factory=list, alias="menuIds")

    model_config = ConfigDict(populate_by_name=True)


class RoleResponse(BaseModel):
    """Role detail response"""

    id: int
    name: str
    code: str
    description: str | None = None
    is_active: bool = Field(True, alias="isActive")
    is_system: bool = Field(False, alias="isSystem")
    sort_order: int = Field(0, alias="sortOrder")
    data_range: int = Field(4, alias="dataRange")
    data_permissions: int = Field(0, alias="dataPermissions")
    team_permissions: list[dict[str, Any]] = Field(default_factory=list, alias="teamPermissions")
    created_at: str | None = Field(None, alias="createdAt")
    menus: list[dict[str, Any]] | None = None

    model_config = ConfigDict(populate_by_name=True)


class RoleDetailResponse(ResponseBase[RoleResponse]):
    """Role detail response wrapper"""

    pass


class RoleMenuTreeResponse(ResponseBase[dict[str, Any]]):
    """Role menu tree response"""

    pass


# ============== Endpoints ==============


@router.post("", response_model=RoleListResponse)
async def get_role_list(
    query: RoleListQuery,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:read", "role:list"])),
) -> dict[str, Any]:
    """
    Get role list with pagination.

    需要权限: role:read 或 role:list
    数据权限: 只能查看有读取权限团队下创建的角色

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = RoleService(db)

    status: int | None
    if query.is_active is not None:
        status = 1 if query.is_active else 0
    else:
        status = query.status

    # 根据数据权限过滤团队
    read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids
    roles, total = await service.list_roles(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        name=query.name,
        code=query.code,
        status=status,
        team_ids=read_team_ids,  # 数据权限过滤
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    # Convert roles to list items with team permissions
    role_items = [await service.to_list_item(role) for role in roles]

    logger.info(
        "role_list_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(roles),
        total=total
    )

    return SuccessResponse(
        data={
            "list": role_items,
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/all", response_model=AllRoleListResponse)
async def get_all_roles(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:read", "role:list"])),
) -> dict[str, Any]:
    """
    Get all roles for dropdown.

    需要权限: role:read 或 role:list

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = RoleService(db)
    roles = await service.get_all_roles(tenant_id=tenant_ctx.tenant_id)

    logger.info(
        "all_roles_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(roles)
    )

    return SuccessResponse(data=[RoleService.to_simple_item(role) for role in roles])


@router.get("/{role_id}", response_model=RoleDetailResponse)
async def get_role(
    role_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:read"])),
) -> dict[str, Any]:
    """
    Get role by ID.

    需要权限: role:read
    数据权限: 只能查看有读取权限团队下创建的角色

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = RoleService(db)
    role = await service.get_by_id(role_id, tenant_ctx.tenant_id)
    if not role:
        raise NotFoundError(message="Role not found")

    # 检查数据权限：角色创建人是否属于有读取权限的团队
    if role.created_by:
        await data_scope.check_read_permission(role.created_by, db)

    logger.info(
        "role_retrieved",
        user_id=current_user.id,
        role_id=role_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(data=await service.to_response(role))


@router.get("/{role_id}/menus", response_model=ResponseBase[list[int]])
async def get_role_menus(
    role_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:read"])),
) -> dict[str, Any]:
    """
    Get role menu IDs (for permission assignment dialog).
    Returns list of menu IDs assigned to this role.

    需要权限: role:read
    数据权限: 只能查看有读取权限团队下创建的角色

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = RoleService(db)
    role = await service.get_by_id(role_id, tenant_ctx.tenant_id)
    if not role:
        raise NotFoundError(message="Role not found")

    # 检查数据权限：角色创建人是否属于有读取权限的团队
    if role.created_by:
        await data_scope.check_read_permission(role.created_by, db)

    menu_ids: list[int] = []
    if hasattr(role, "menus") and role.menus:
        menu_ids = [menu.id for menu in role.menus if menu.deleted_at is None]

    logger.info(
        "role_menus_retrieved",
        user_id=current_user.id,
        role_id=role_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        menu_count=len(menu_ids)
    )

    return SuccessResponse(data=menu_ids)


@router.post("/create", response_model=RoleDetailResponse)
async def create_role(
    data: RoleCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:create"])),
) -> dict[str, Any]:
    """
    Create new role.

    需要权限: role:create
    数据权限: 只能配置有编辑权限的团队

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    # 验证团队权限配置是否有权限
    if data.team_permissions and not data_scope.has_all_edit_access:
        for tp in data.team_permissions:
            if not data_scope.can_edit(tp.id):
                raise ForbiddenError(message=f"无权配置团队 {tp.id} 的权限")

    service = RoleService(db)
    # Convert team_permissions to list of dicts
    team_perms = None
    if data.team_permissions:
        team_perms = [{"id": tp.id, "permissions": tp.permissions} for tp in data.team_permissions]

    role = await service.create_role(
        tenant_id=tenant_ctx.tenant_id,
        name=data.name,
        code=data.code,
        description=data.description,
        sort_order=data.sort_order,
        is_active=data.is_active,
        menu_ids=data.menu_ids,
        data_range=data.data_range,
        data_permissions=data.data_permissions,
        team_permissions=team_perms,
        created_by=current_user.id,  # 设置创建人
    )

    logger.info(
        "role_created",
        user_id=current_user.id,
        role_id=role.id,
        role_name=role.name,
        role_code=role.code,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(data=await service.to_response(role))


@router.put("/{role_id}", response_model=RoleDetailResponse)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:update"])),
) -> dict[str, Any]:
    """
    Update role.

    需要权限: role:update
    数据权限: 只能编辑有编辑权限团队下创建的角色，且只能配置有编辑权限的团队

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = RoleService(db)

    # 先获取角色，检查数据权限
    role = await service.get_by_id(role_id, tenant_ctx.tenant_id)
    if not role:
        raise NotFoundError(message="Role not found")

    # 检查数据权限：角色创建人是否属于有编辑权限的团队
    if role.created_by:
        await data_scope.check_edit_permission(role.created_by, db)

    # 验证团队权限配置是否有权限
    if data.team_permissions is not None and not data_scope.has_all_edit_access:
        for tp in data.team_permissions:
            if not data_scope.can_edit(tp.id):
                raise ForbiddenError(message=f"无权配置团队 {tp.id} 的权限")

    role = await service.update_role(
        role_id=role_id,
        tenant_id=tenant_ctx.tenant_id,
        name=data.name,
        code=data.code,
        description=data.description,
        sort_order=data.sort_order,
        is_active=data.is_active,
        data_range=data.data_range,
        data_permissions=data.data_permissions,
    )

    if data.menu_ids is not None:
        role = await service.update_menus(
            role_id=role_id,
            tenant_id=tenant_ctx.tenant_id,
            menu_ids=data.menu_ids,
        )

    if data.team_permissions is not None:
        team_perms = [{"id": tp.id, "permissions": tp.permissions} for tp in data.team_permissions]
        role = await service.update_team_permissions(
            role_id=role_id,
            tenant_id=tenant_ctx.tenant_id,
            team_permissions=team_perms,
        )

    logger.info(
        "role_updated",
        user_id=current_user.id,
        role_id=role_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(data=await service.to_response(role))


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:delete"])),
) -> dict[str, Any]:
    """
    Delete role (soft delete).

    需要权限: role:delete
    数据权限: 只能删除有删除权限团队下创建的角色

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = RoleService(db)

    # 先获取角色，检查数据权限
    role = await service.get_by_id(role_id, tenant_ctx.tenant_id)
    if not role:
        raise NotFoundError(message="Role not found")

    # 检查数据权限：角色创建人是否属于有删除权限的团队
    if role.created_by:
        await data_scope.check_delete_permission(role.created_by, db)

    await service.delete_role(role_id, tenant_ctx.tenant_id)

    logger.info(
        "role_deleted",
        user_id=current_user.id,
        role_id=role_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(message="Role deleted")


@router.post("/{role_id}/menus", response_model=RoleDetailResponse)
async def update_role_menus(
    role_id: int,
    data: MenuAssign,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:update"])),
) -> dict[str, Any]:
    """
    Update role menus (permission assignment).

    需要权限: role:update
    数据权限: 只能编辑有编辑权限团队下创建的角色

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = RoleService(db)

    # 先获取角色，检查数据权限
    role = await service.get_by_id(role_id, tenant_ctx.tenant_id)
    if not role:
        raise NotFoundError(message="Role not found")

    # 检查数据权限：角色创建人是否属于有编辑权限的团队
    if role.created_by:
        await data_scope.check_edit_permission(role.created_by, db)

    role = await service.update_menus(
        role_id=role_id,
        tenant_id=tenant_ctx.tenant_id,
        menu_ids=data.menu_ids,
    )

    logger.info(
        "role_menus_updated",
        user_id=current_user.id,
        role_id=role_id,
        menu_count=len(data.menu_ids),
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(data=await service.to_response(role))


@router.get("/{role_id}/team-permissions", response_model=ResponseBase[list[dict[str, Any]]])
async def get_role_team_permissions(
    role_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["role:read"])),
) -> dict[str, Any]:
    """
    Get role team permissions (for permission assignment dialog).
    Returns list of {id, permissions} for each team assigned to this role.

    需要权限: role:read
    数据权限: 只能查看有读取权限团队下创建的角色

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = RoleService(db)
    role = await service.get_by_id(role_id, tenant_ctx.tenant_id)
    if not role:
        raise NotFoundError(message="Role not found")

    # 检查数据权限：角色创建人是否属于有读取权限的团队
    if role.created_by:
        await data_scope.check_read_permission(role.created_by, db)

    team_permissions = await service.get_role_team_permissions(role_id, tenant_ctx.tenant_id)

    logger.info(
        "role_team_permissions_retrieved",
        user_id=current_user.id,
        role_id=role_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        team_count=len(team_permissions)
    )

    return SuccessResponse(data=team_permissions)
