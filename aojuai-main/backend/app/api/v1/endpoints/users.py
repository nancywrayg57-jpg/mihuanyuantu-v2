"""
AOJU Backend - User Management Endpoints

权限设计:
- 系统管理员 (is_superuser=True): 可以通过 X-Tenant-Id 或 tenant_id 参数管理任意租户的用户
- 租户管理员 (roles 包含 admin): 只能管理本租户的用户
- 细粒度权限控制: 基于权限码（如 user:create, user:update）
- 数据权限控制: 基于团队的数据隔离（只能查看/编辑/删除有权限团队下的用户）
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.api.deps import (
    CurrentUser,
    DataScopeCtx,
    DBSession,
    PermissionChecker,
    TenantCtx,
)
from app.core.exceptions import ForbiddenError
from app.core.logger import get_logger
from app.core.response import ErrorResponse, SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.users.schemas import (
    PasswordChange,
    PasswordReset,
    UserAudit,
    UserCreate,
    UserListItem,
    UserResponse,
    UserUpdate,
)
from app.domain.users.service import UserService

logger = get_logger(__name__)

router = APIRouter()


# ============== Schemas ==============


class UserListQuery(BaseModel):
    """User list query parameters"""

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    username: str | None = None
    nickname: str | None = None
    phone: str | None = None
    status: int | None = None
    organization_id: int | None = Field(None, alias="organizationId")
    profile_filters: dict[str, Any] | None = Field(None, alias="profileFilters")
    # 排序参数
    sort_by: str | None = Field(
        None,
        alias="sortBy",
        description="排序字段: id, username, nickname, created_at, status",
    )
    sort_order: str | None = Field(
        None,
        alias="sortOrder",
        description="排序方向: asc, desc",
    )

    model_config = ConfigDict(populate_by_name=True)


# ============== Endpoints ==============


@router.post("", response_model=ResponseBase[PageResponse[UserListItem]])
async def get_user_list(
    query: UserListQuery,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:read", "user:list"])),
) -> dict[str, Any]:
    """
    Get user list with pagination.

    需要权限: user:read 或 user:list
    数据权限: 只能查看有读取权限团队下的用户

    超级管理员可以通过以下方式指定目标租户:
    - 请求头: X-Tenant-Id: {tenant_id}
    - 查询参数: ?tenant_id={tenant_id}
    """
    service = UserService(db)
    profile_config = await service.get_tenant_profile_config(tenant_ctx.tenant_id)

    # 根据数据权限过滤团队
    read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids

    users, total = await service.list_users(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        username=query.username,
        nickname=query.nickname,
        phone=query.phone,
        status=query.status,
        organization_id=query.organization_id,
        profile_filters=query.profile_filters,
        team_ids=read_team_ids,  # 数据权限过滤
        include_tenant_info=tenant_ctx.is_superuser,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )
    invitation_context_map = await service.get_invitation_context_map(
        tenant_id=tenant_ctx.tenant_id,
        user_ids=[int(user.id) for user in users],
    )

    logger.info(
        "user_list_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(users),
        total=total
    )

    return SuccessResponse(
        data={
            "list": [
                UserService.to_list_item(
                    u,
                    include_tenant=tenant_ctx.is_superuser,
                    profile_config=profile_config,
                    invitation_context=invitation_context_map.get(int(u.id)),
                )
                for u in users
            ],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.post("/pending", response_model=ResponseBase[PageResponse[UserListItem]])
async def get_pending_users(
    query: UserListQuery,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:audit", "user:read"])),
) -> dict[str, Any]:
    """
    Get pending registration users.

    需要权限: user:audit 或 user:read
    数据权限: 只能查看有读取权限团队下的待审核用户

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = UserService(db)
    profile_config = await service.get_tenant_profile_config(tenant_ctx.tenant_id)

    # 根据数据权限过滤团队
    read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids

    users, total = await service.list_pending_users(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        team_ids=read_team_ids,  # 数据权限过滤
    )
    invitation_context_map = await service.get_invitation_context_map(
        tenant_id=tenant_ctx.tenant_id,
        user_ids=[int(user.id) for user in users],
    )

    logger.info(
        "pending_users_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(users)
    )

    return SuccessResponse(
        data={
            "list": [
                UserService.to_list_item(
                    u,
                    include_tenant=tenant_ctx.is_superuser,
                    profile_config=profile_config,
                    invitation_context=invitation_context_map.get(int(u.id)),
                )
                for u in users
            ],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/{user_id}", response_model=ResponseBase[UserResponse])
async def get_user(
    user_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:read"])),
) -> dict[str, Any]:
    """
    Get user by ID.

    需要权限: user:read
    数据权限: 只能查看有读取权限团队下的用户

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = UserService(db)
    profile_config = await service.get_tenant_profile_config(tenant_ctx.tenant_id)

    user = await service.get_user_by_id(user_id, tenant_ctx.tenant_id)

    if not user:
        return ErrorResponse(message="User not found", code="NOT_FOUND")

    # 检查数据权限：用户是否属于有读取权限的团队
    await data_scope.check_read_permission(user_id, db)

    logger.info(
        "user_retrieved",
        user_id=current_user.id,
        target_user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    invitation_context = await service.get_invitation_context(tenant_id=tenant_ctx.tenant_id, user_id=user.id)
    return SuccessResponse(
        data=UserService.to_response(
            user,
            profile_config=profile_config,
            invitation_context=invitation_context,
        )
    )


class UserImportRequest(BaseModel):
    """CSV 内容直接放在请求体里。

    不用 multipart 上传：导入的是文本，前端读完文件再发 JSON 更简单，
    也省掉一套文件大小/类型的校验分支。行数上限在解析层管（MAX_ROWS）。
    """

    model_config = ConfigDict(populate_by_name=True)

    content: str = Field(..., max_length=2_000_000)
    #: 默认预演。导入很难撤销，必须先让人看过逐行结论再执行。
    dry_run: bool = Field(True, alias="dryRun")


@router.get("/import/template")
async def get_import_template(
    _: None = Depends(PermissionChecker(["user:create"])),
) -> dict[str, Any]:
    """CSV 模板。

    返回 JSON 而不是直接下发文件：前端要带 Bearer token，普通的 `<a href>` 下载
    链接带不上；而且模板只应有一个真源——前端自己再抄一份 CSV 字面量，
    改表头时必然漏掉一边。前端拿到文本自己组装 Blob 下载即可。
    """
    from app.domain.users.import_service import template_csv

    return SuccessResponse(data={"filename": "user-import-template.csv", "content": template_csv()})


@router.post("/import")
async def import_users(
    data: UserImportRequest,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:create"])),
) -> dict[str, Any]:
    """从 CSV 批量导入用户。默认预演，`dryRun=false` 才真的写库。

    数据权限与单个创建保持一致：**只能把人导入到自己有编辑权限的团队**。
    不做这个检查，导入就成了绕过数据权限的提权路径——组长可以把人塞进别的组。
    """
    from app.domain.users.import_service import UserImportService

    service = UserImportService(db, tenant_id=tenant_ctx.tenant_id, actor_id=current_user.id)
    outcome = await service.run(data.content, dry_run=data.dry_run)

    if not data_scope.has_all_edit_access:
        allowed = await service._team_index()
        for row in outcome.rows:
            if row.status != "created" or not row.resolved_team:
                continue
            team_id = allowed.get(row.resolved_team.lower())
            if team_id is None or not data_scope.can_edit(team_id):
                raise ForbiddenError(message=f"无权将用户分配到团队「{row.resolved_team}」")

    logger.info(
        "users_imported",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        dry_run=data.dry_run,
        total=outcome.total,
        created=outcome.created,
        skipped=outcome.skipped,
        failed=outcome.failed,
    )

    return SuccessResponse(
        data={
            **outcome.summary(),
            "headerErrors": outcome.header_errors,
            "rows": [
                {
                    "line": row.line,
                    "username": row.username,
                    "status": row.status,
                    "message": row.message,
                    # 初始密码只在这一次返回，之后无处可查——由管理员线下转交
                    "initialPassword": row.initial_password,
                    "team": row.resolved_team,
                    "role": row.resolved_role,
                }
                for row in outcome.rows
            ],
        }
    )


@router.post("/create", response_model=ResponseBase[UserResponse])
async def create_user(
    data: UserCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:create"])),
) -> dict[str, Any]:
    """
    Create new user.

    需要权限: user:create
    数据权限: 只能将用户分配到有编辑权限的团队

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    # 验证所选团队是否有编辑权限
    if data.team_ids and not data_scope.has_all_edit_access:
        for team_id in data.team_ids:
            if not data_scope.can_edit(team_id):
                raise ForbiddenError(message=f"无权将用户分配到团队 {team_id}")

    service = UserService(db)
    profile_config = await service.get_tenant_profile_config(tenant_ctx.tenant_id)

    user = await service.create_user(
        data=data,
        tenant_id=tenant_ctx.tenant_id,
        created_by=current_user.id,
    )

    logger.info(
        "user_created",
        user_id=current_user.id,
        new_user_id=user.id,
        new_username=user.username,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(data=UserService.to_response(user, profile_config=profile_config))


@router.put("/{user_id}", response_model=ResponseBase[UserResponse])
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:update"])),
) -> dict[str, Any]:
    """
    Update user.

    需要权限: user:update
    数据权限: 只能编辑有编辑权限团队下的用户，且只能将用户分配到有编辑权限的团队

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    # 检查数据权限：用户是否属于有编辑权限的团队
    await data_scope.check_edit_permission(user_id, db)

    # 验证新团队是否有编辑权限
    if data.team_ids is not None and not data_scope.has_all_edit_access:
        for team_id in data.team_ids:
            if not data_scope.can_edit(team_id):
                raise ForbiddenError(message=f"无权将用户分配到团队 {team_id}")

    service = UserService(db)
    profile_config = await service.get_tenant_profile_config(tenant_ctx.tenant_id)

    user = await service.update_user(
        user_id=user_id,
        data=data,
        tenant_id=tenant_ctx.tenant_id,
    )

    if not user:
        return ErrorResponse(message="User not found", code="NOT_FOUND")

    logger.info(
        "user_updated",
        user_id=current_user.id,
        target_user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(data=UserService.to_response(user, profile_config=profile_config))


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:delete"])),
) -> dict[str, Any]:
    """
    Delete user (soft delete).

    需要权限: user:delete
    数据权限: 只能删除有删除权限团队下的用户

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = UserService(db)

    # 检查数据权限：用户是否属于有删除权限的团队
    await data_scope.check_delete_permission(user_id, db)

    await service.delete_user(user_id, tenant_ctx.tenant_id)

    logger.info(
        "user_deleted",
        user_id=current_user.id,
        target_user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(message="User deleted")


@router.post("/{user_id}/audit", response_model=ResponseBase[UserResponse])
async def audit_user(
    user_id: int,
    data: UserAudit,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:audit"])),
) -> dict[str, Any]:
    """
    Audit user registration (approve/reject).

    需要权限: user:audit
    数据权限: 只能审核有编辑权限团队下的用户

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    # 检查数据权限：用户是否属于有编辑权限的团队
    await data_scope.check_edit_permission(user_id, db)

    service = UserService(db)
    profile_config = await service.get_tenant_profile_config(tenant_ctx.tenant_id)

    user = await service.audit_user(
        user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        audit_data=data,
        auditor_id=current_user.id,
    )

    logger.info(
        "user_audited",
        user_id=current_user.id,
        target_user_id=user_id,
        approved=data.approved,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(data=UserService.to_response(user, profile_config=profile_config))


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    data: PasswordReset,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["user:reset-password", "user:manage"])),
) -> dict[str, Any]:
    """
    Reset user password.

    需要权限: user:reset-password 或 user:manage
    数据权限: 只能重置有编辑权限团队下的用户密码

    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    # 检查数据权限：用户是否属于有编辑权限的团队
    await data_scope.check_edit_permission(user_id, db)

    service = UserService(db)

    await service.reset_password(
        user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        data=data,
    )

    logger.info(
        "user_password_reset",
        user_id=current_user.id,
        target_user_id=user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(message="Password reset successfully")


@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Change current user's password.

    用户只能修改自己的密码，不需要租户上下文。
    """
    service = UserService(db)
    await service.change_password(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        data=data,
    )

    logger.info(
        "user_password_changed",
        user_id=current_user.id
    )

    return SuccessResponse(message="Password changed successfully")
