"""
AOJU Backend - Team Management Endpoints

权限设计:
- 系统管理员 (is_superuser=True): 可以通过 X-Tenant-Id 或 tenant_id 参数管理任意租户的团队
- 租户管理员 (roles 包含 admin): 只能管理本租户的团队
- 细粒度权限控制: 基于权限码（如 team:create, team:update）
- 数据权限控制: 直接检查团队ID本身是否在有权限的团队列表中（与用户管理的数据权限逻辑不同）

数据权限说明:
- 团队管理的数据权限与用户管理不同
- 用户管理：检查用户所属团队是否在有权限的团队列表中
- 团队管理：直接检查团队ID本身是否在有权限的团队列表中
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import (
    CurrentUser,
    DataScopeCtx,
    DBSession,
    PermissionChecker,
    TenantCtx,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logger import get_logger
from app.core.response import SuccessResponse
from app.core.schemas import ResponseBase
from app.domain.teams.schemas import (
    TeamCreate,
    TeamResponse,
    TeamTreeNode,
    TeamUpdate,
)
from app.domain.teams.service import TeamService

logger = get_logger(__name__)

router = APIRouter()


# ============== Schemas ==============

class TeamIdList(BaseModel):
    """Team ID list for batch operations"""
    ids: list[int] = Field(..., min_length=1, description="团队ID列表")


# ============== Endpoints ==============

@router.get("/tree", response_model=ResponseBase[list[TeamTreeNode]])
async def get_team_tree(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    status: int | None = None,
    _: None = Depends(PermissionChecker(["team:read"])),
) -> dict[str, Any]:
    """
    获取团队树形列表

    需要权限：team:read
    数据权限：直接过滤团队ID本身，只返回有读取权限的团队
    
    超级管理员可以通过以下方式指定目标租户:
    - 请求头: X-Tenant-Id: {tenant_id}
    - 查询参数: ?tenant_id={tenant_id}
    """
    service = TeamService(db)

    # 根据数据权限过滤团队
    read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids

    tree = await service.get_tree_list(
        tenant_id=tenant_ctx.tenant_id,
        status=status,
        team_ids=read_team_ids,
    )

    logger.info(
        "team_tree_retrieved",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(tree)
    )

    return SuccessResponse(data=tree)


@router.get("/options", response_model=ResponseBase[list[dict]])
async def get_team_options(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    include_disabled: bool = False,
    _: None = Depends(PermissionChecker(["team:read"])),
) -> dict[str, Any]:
    """
    获取团队树形选项（用于下拉选择）

    需要权限：team:read
    数据权限：直接过滤团队ID本身，只返回有读取权限的团队
    
    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = TeamService(db)

    # 根据数据权限过滤团队（直接过滤团队ID本身）
    read_team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids

    options = await service.get_tree_options(
        tenant_id=tenant_ctx.tenant_id,
        include_disabled=include_disabled,
        team_ids=read_team_ids,
    )

    return SuccessResponse(data=options)


@router.get("/{team_id}", response_model=ResponseBase[TeamResponse])
async def get_team(
    team_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["team:read"])),
) -> dict[str, Any]:
    """
    获取团队详情

    需要权限：team:read
    数据权限：直接检查团队ID本身是否在有读取权限的团队列表中
    
    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = TeamService(db)

    team = await service.get_team_by_id(
        team_id,
        tenant_ctx.tenant_id
    )

    if not team:
        raise NotFoundError(message="团队不存在")

    # 检查数据权限：直接检查团队ID本身
    if not data_scope.has_all_read_access and not data_scope.can_read(team_id):
        raise ForbiddenError(message="无权查看该团队")

    logger.info(
        "team_retrieved",
        user_id=current_user.id,
        team_id=team_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(data=TeamService.to_response(team))


@router.post("", response_model=ResponseBase[TeamResponse])
async def create_team(
    data: TeamCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["team:create"])),
) -> dict[str, Any]:
    """
    创建团队

    需要权限：team:create
    数据权限：如果指定了父团队，需要对父团队拥有"本团队及以下"权限才能在其下创建子团队
    
    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = TeamService(db)

    # 如果指定了父团队，检查是否可以在该父团队下创建子团队
    # 只有拥有"本团队及以下"权限的团队才能创建子团队
    if data.parent_id and not data_scope.has_all_edit_access:
        if not data_scope.can_create_child_team(data.parent_id):
            raise ForbiddenError(
                message="无权在该父团队下创建子团队，需要对父团队拥有'本团队及以下'权限"
            )

    team = await service.create_team(
        data=data,
        tenant_id=tenant_ctx.tenant_id,
        created_by=current_user.id,
    )

    logger.info(
        "team_created",
        user_id=current_user.id,
        team_id=team.id,
        team_name=team.name,
        team_code=team.code,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(
        data=TeamService.to_response(team),
        message="团队创建成功"
    )


@router.put("/{team_id}", response_model=ResponseBase[TeamResponse])
async def update_team(
    team_id: int,
    data: TeamUpdate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["team:update"])),
) -> dict[str, Any]:
    """
    更新团队信息

    需要权限：team:update
    数据权限：
    - 直接检查团队ID本身是否在有编辑权限的团队列表中
    - 如果要移动团队到新的父团队，需要对新父团队拥有"本团队及以下"权限
    
    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = TeamService(db)

    # 先获取团队，检查数据权限
    team = await service.get_team_by_id(team_id, tenant_ctx.tenant_id)
    if not team:
        raise NotFoundError(message="团队不存在")

    # 检查数据权限：直接检查团队ID本身
    if not data_scope.has_all_edit_access and not data_scope.can_edit(team_id):
        raise ForbiddenError(message="无权编辑该团队")

    # 如果用户明确传了 parent_id 参数，检查权限
    # 只有拥有"本团队及以下"权限的团队才能移动到其下
    if "parent_id" in data.model_fields_set:
        new_parent_id = data.parent_id if data.parent_id != 0 else None
        # 只有当新的父团队与原来不同时才需要检查权限
        if new_parent_id != team.parent_id:
            # 如果目标是顶级团队（设为顶级团队），只有管理员可以
            if new_parent_id is None and not data_scope.has_all_edit_access:
                raise ForbiddenError(
                    message="只有管理员才能将团队设为顶级团队"
                )
            # 如果目标是非顶级团队（移动到某个团队下），检查对目标父团队的权限
            elif new_parent_id and not data_scope.has_all_edit_access:
                if not data_scope.can_create_child_team(new_parent_id):
                    raise ForbiddenError(
                        message="无权将团队移动到该父团队下，需要对目标父团队拥有'本团队及以下'权限"
                    )

    team = await service.update_team(
        team_id=team_id,
        data=data,
        tenant_id=tenant_ctx.tenant_id
    )

    logger.info(
        "team_updated",
        user_id=current_user.id,
        team_id=team_id,
        team_name=team.name,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(
        data=TeamService.to_response(team),
        message="团队更新成功"
    )


@router.delete("/{team_id}")
async def delete_team(
    team_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["team:delete"])),
) -> dict[str, Any]:
    """
    删除团队（软删除）

    需要权限：team:delete
    数据权限：直接检查团队ID本身是否在有删除权限的团队列表中
    
    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = TeamService(db)

    # 先获取团队，检查数据权限
    team = await service.get_team_by_id(team_id, tenant_ctx.tenant_id)
    if not team:
        raise NotFoundError(message="团队不存在")

    # 检查数据权限：直接检查团队ID本身
    if not data_scope.has_all_delete_access and not data_scope.can_delete(team_id):
        raise ForbiddenError(message="无权删除该团队")

    await service.delete_team(
        team_id=team_id,
        tenant_id=tenant_ctx.tenant_id
    )

    logger.info(
        "team_deleted",
        user_id=current_user.id,
        team_id=team_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(message="团队删除成功")


@router.delete("")
async def delete_teams_batch(
    ids: TeamIdList,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["team:delete"])),
) -> dict[str, Any]:
    """
    批量删除团队

    需要权限：team:delete
    数据权限：直接检查团队ID本身是否在有删除权限的团队列表中
    
    超级管理员可以通过 X-Tenant-Id 或 tenant_id 参数指定目标租户
    """
    service = TeamService(db)

    # 检查每个团队的数据权限（直接检查团队ID本身）
    if not data_scope.has_all_delete_access:
        for team_id in ids.ids:
            if not data_scope.can_delete(team_id):
                raise ForbiddenError(message=f"无权删除团队 {team_id}")

    await service.delete_teams_batch(
        team_ids=ids.ids,
        tenant_id=tenant_ctx.tenant_id
    )

    logger.info(
        "teams_batch_deleted",
        user_id=current_user.id,
        team_ids=ids.ids,
        count=len(ids.ids),
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant
    )

    return SuccessResponse(message=f"成功删除 {len(ids.ids)} 个团队")
