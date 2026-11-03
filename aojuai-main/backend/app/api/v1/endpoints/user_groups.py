"""
AOJU Backend - User Group Endpoints
"""
from typing import Any

from fastapi import APIRouter
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.api.deps import CurrentUser, CurrentSuperuser, DBSession
from app.core.response import ErrorResponse, SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.user_groups.schemas import (
    AddGroupMembers,
    RemoveGroupMembers,
    UserGroupCreate,
    UserGroupListItem,
    UserGroupResponse,
    UserGroupUpdate,
)
from app.domain.user_groups.service import UserGroupService

router = APIRouter()


# ============== Schemas ==============


class GroupListQuery(BaseModel):
    """Group list query parameters"""

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

    model_config = ConfigDict(populate_by_name=True)


# ============== Endpoints ==============


@router.post("", response_model=ResponseBase[PageResponse[UserGroupListItem]])
async def get_group_list(
    query: GroupListQuery,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get user group list with pagination.
    """
    service = UserGroupService(db)
    groups, total = await service.list_groups(
        tenant_id=current_user.tenant_id,
        page=query.page,
        page_size=query.page_size,
        name=query.name,
        is_active=query.is_active,
    )

    return SuccessResponse(
        data={
            "list": [UserGroupService.to_list_item(g) for g in groups],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/all")
async def get_all_groups(
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get all user groups (for dropdown).
    """
    service = UserGroupService(db)
    groups = await service.list_all_groups(current_user.tenant_id)

    return SuccessResponse(
        data=[
            {"id": g.id, "name": g.name, "code": g.code}
            for g in groups
        ]
    )


@router.get("/tree")
async def get_group_tree(
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get user groups as tree structure.
    """
    service = UserGroupService(db)
    groups = await service.get_tree(current_user.tenant_id)

    return SuccessResponse(
        data=[UserGroupService.to_response(g) for g in groups]
    )


@router.get("/{group_id}", response_model=ResponseBase[UserGroupResponse])
async def get_group(
    group_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get user group by ID.
    """
    service = UserGroupService(db)
    group = await service.get_by_id(group_id, current_user.tenant_id)

    if not group:
        return ErrorResponse(message="Group not found", code="NOT_FOUND")

    return SuccessResponse(data=UserGroupService.to_response(group))


@router.post("/create", response_model=ResponseBase[UserGroupResponse])
async def create_group(
    data: UserGroupCreate,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Create user group (admin only).
    """
    service = UserGroupService(db)
    group = await service.create_group(
        data=data,
        tenant_id=current_user.tenant_id,
    )

    return SuccessResponse(data=UserGroupService.to_response(group))


@router.put("/{group_id}", response_model=ResponseBase[UserGroupResponse])
async def update_group(
    group_id: int,
    data: UserGroupUpdate,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Update user group (admin only).
    """
    service = UserGroupService(db)
    group = await service.update_group(
        group_id=group_id,
        data=data,
        tenant_id=current_user.tenant_id,
    )

    return SuccessResponse(data=UserGroupService.to_response(group))


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Delete user group (admin only).
    """
    service = UserGroupService(db)
    await service.delete_group(group_id, current_user.tenant_id)

    return SuccessResponse(message="Group deleted")


@router.get("/{group_id}/members")
async def get_group_members(
    group_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get group members.
    """
    service = UserGroupService(db)
    members = await service.get_group_members(group_id, current_user.tenant_id)

    return SuccessResponse(
        data=[
            {
                "userId": m.user_id,
                "username": m.user.username if m.user else None,
                "nickname": m.user.nickname if m.user else None,
                "isLeader": m.is_leader,
            }
            for m in members
        ]
    )


@router.post("/{group_id}/members")
async def add_group_members(
    group_id: int,
    data: AddGroupMembers,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Add members to group (admin only).
    """
    service = UserGroupService(db)
    await service.add_members(
        group_id=group_id,
        user_ids=data.user_ids,
        tenant_id=current_user.tenant_id,
    )

    return SuccessResponse(message="Members added")


@router.delete("/{group_id}/members")
async def remove_group_members(
    group_id: int,
    data: RemoveGroupMembers,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Remove members from group (admin only).
    """
    service = UserGroupService(db)
    await service.remove_members(
        group_id=group_id,
        user_ids=data.user_ids,
        tenant_id=current_user.tenant_id,
    )

    return SuccessResponse(message="Members removed")
