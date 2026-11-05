"""
AOJU Backend - User Group Schemas
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserGroupBase(BaseModel):
    """Base user group schema"""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    parent_id: int | None = Field(None, alias="parentId")
    sort_order: int = Field(0, alias="sortOrder")
    is_active: bool = Field(True, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class UserGroupCreate(UserGroupBase):
    """Create user group schema"""
    pass


class UserGroupUpdate(BaseModel):
    """Update user group schema"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    parent_id: int | None = Field(None, alias="parentId")
    sort_order: int | None = Field(None, alias="sortOrder")
    is_active: bool | None = Field(None, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class UserGroupResponse(BaseModel):
    """User group response schema"""
    id: int
    name: str
    code: str
    description: str | None = None
    parent_id: int | None = Field(None, alias="parentId")
    path: str = "/"
    level: int = 1
    sort_order: int = Field(0, alias="sortOrder")
    is_active: bool = Field(True, alias="isActive")
    created_at: datetime | None = Field(None, alias="createdAt")
    children: list["UserGroupResponse"] = []
    member_count: int = Field(0, alias="memberCount")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class UserGroupListItem(BaseModel):
    """User group list item"""
    id: int
    name: str
    code: str
    description: str | None = None
    parent_id: int | None = Field(None, alias="parentId")
    path: str = "/"
    level: int = 1
    sort_order: int = Field(0, alias="sortOrder")
    is_active: bool = Field(True, alias="isActive")
    member_count: int = Field(0, alias="memberCount")
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class AddGroupMembers(BaseModel):
    """Add members to group"""
    user_ids: list[int] = Field(..., alias="userIds")

    model_config = ConfigDict(populate_by_name=True)


class RemoveGroupMembers(BaseModel):
    """Remove members from group"""
    user_ids: list[int] = Field(..., alias="userIds")

    model_config = ConfigDict(populate_by_name=True)
