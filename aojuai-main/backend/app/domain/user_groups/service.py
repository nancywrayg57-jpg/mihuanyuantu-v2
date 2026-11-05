"""
AOJU Backend - User Group Service

Supports unlimited hierarchy using materialized path pattern.
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.domain.user_groups.models import UserGroup, UserGroupMember
from app.domain.user_groups.schemas import UserGroupCreate, UserGroupUpdate
from app.infrastructure.repository.base import RepositoryBase


class UserGroupService(RepositoryBase[UserGroup]):
    """User group business logic"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, UserGroup)
        self._default_options = [selectinload(UserGroup.members)]

    async def get_by_id(self, group_id: int, tenant_id: int) -> UserGroup | None:
        """Get group by ID"""
        return await self.get_one(
            where=[UserGroup.id == group_id, UserGroup.tenant_id == tenant_id],
            options=self._default_options,
        )

    async def get_by_code(self, code: str, tenant_id: int) -> UserGroup | None:
        """Get group by code"""
        return await self.get_one(
            where=[UserGroup.code == code, UserGroup.tenant_id == tenant_id],
        )

    async def list_groups(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 10,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[UserGroup], int]:
        """List groups with pagination"""
        where = [UserGroup.tenant_id == tenant_id]

        if name:
            where.append(UserGroup.name.ilike(f"%{name}%"))
        if is_active is not None:
            where.append(UserGroup.is_active == is_active)

        return await self.get_list(
            page=page,
            page_size=page_size,
            where=where,
            options=self._default_options,
            order_by="sort_order",
            return_total=True,
        )

    async def list_all_groups(self, tenant_id: int) -> list[UserGroup]:
        """List all groups (for dropdown)"""
        return await self.get_list(
            page_size=0,  # No pagination
            where=[UserGroup.tenant_id == tenant_id, UserGroup.is_active],
            order_by="sort_order",
        )

    async def get_tree(self, tenant_id: int) -> list[UserGroup]:
        """Get groups as tree structure (root level only, children loaded via relationship)"""
        return await self.get_list(
            page_size=0,
            where=[
                UserGroup.tenant_id == tenant_id,
                UserGroup.parent_id.is_(None),
            ],
            options=[selectinload(UserGroup.children).selectinload(UserGroup.children)],
            order_by="sort_order",
        )

    async def get_descendants(self, group_id: int, tenant_id: int) -> list[UserGroup]:
        """Get all descendant groups using path prefix matching"""
        group = await self.get_by_id(group_id, tenant_id)
        if not group:
            return []

        # Find all groups whose path starts with this group's path + id
        prefix = f"{group.path}{group.id}/"
        return await self.get_list(
            page_size=0,
            where=[
                UserGroup.tenant_id == tenant_id,
                UserGroup.path.startswith(prefix),
            ],
            order_by="sort_order",
        )

    async def create_group(
        self,
        data: UserGroupCreate,
        tenant_id: int,
    ) -> UserGroup:
        """Create group with proper path calculation"""
        # Check code exists
        existing = await self.get_by_code(data.code, tenant_id)
        if existing:
            raise ConflictError(message=f"Group code '{data.code}' already exists")

        # Get parent if specified
        parent = None
        if data.parent_id:
            parent = await self.get_by_id(data.parent_id, tenant_id)
            if not parent:
                raise NotFoundError(message="Parent group not found")

        group_data = {
            "tenant_id": tenant_id,
            "name": data.name,
            "code": data.code,
            "description": data.description,
            "parent_id": data.parent_id,
            "sort_order": data.sort_order,
            "is_active": data.is_active,
        }
        group = await self.create(group_data)

        # Calculate path and level (needs ID)
        group.update_path(parent)
        await self.db.flush()
        await self.db.refresh(group)
        return group

    async def update_group(
        self,
        group_id: int,
        data: UserGroupUpdate,
        tenant_id: int,
    ) -> UserGroup:
        """Update group"""
        group = await self.get_by_id(group_id, tenant_id)
        if not group:
            raise NotFoundError(message="Group not found")

        # Check if parent is changing
        old_parent_id = group.parent_id

        update_data = data.model_dump(exclude_unset=True, exclude={"parent_id"})

        # If parent changed, update path for this group and all descendants
        if data.parent_id is not None and data.parent_id != old_parent_id:
            # Prevent circular reference
            if data.parent_id == group_id:
                raise BusinessError(message="Cannot set group as its own parent")

            # Get new parent
            new_parent = None
            if data.parent_id:
                new_parent = await self.get_by_id(data.parent_id, tenant_id)
                if not new_parent:
                    raise NotFoundError(message="Parent group not found")

                # Check if new parent is a descendant of this group
                if new_parent.path.startswith(f"{group.path}{group.id}/"):
                    raise BusinessError(message="Cannot set descendant as parent")

            # Update this group's path
            old_path = group.path
            old_full_path = f"{old_path}{group.id}/"
            update_data["parent_id"] = data.parent_id

            # Apply update first
            group = await self.update(group, update_data, exclude_unset=False)
            group.update_path(new_parent)
            new_full_path = f"{group.path}{group.id}/"

            # Update all descendants' paths
            descendants = await self.get_descendants(group_id, tenant_id)
            level_diff = group.level - (new_parent.level + 1 if new_parent else 1)
            for desc in descendants:
                desc.path = desc.path.replace(old_full_path, new_full_path, 1)
                desc.level = desc.level - level_diff

            await self.db.flush()
            await self.db.refresh(group)
            return group
        else:
            return await self.update(group, update_data, exclude_unset=False)

    async def delete_group(self, group_id: int, tenant_id: int) -> None:
        """Soft delete group and optionally its descendants"""
        group = await self.get_by_id(group_id, tenant_id)
        if not group:
            raise NotFoundError(message="Group not found")

        # Check if has members
        if group.members:
            raise BusinessError(message="Cannot delete group with members")

        # Check if has children
        if group.children:
            raise BusinessError(message="Cannot delete group with children. Delete children first or move them.")

        await self.delete(group)

    async def add_members(
        self,
        group_id: int,
        user_ids: list[int],
        tenant_id: int,
    ) -> None:
        """Add members to group"""
        group = await self.get_by_id(group_id, tenant_id)
        if not group:
            raise NotFoundError(message="Group not found")

        existing_user_ids = {m.user_id for m in group.members}
        for user_id in user_ids:
            if user_id not in existing_user_ids:
                member = UserGroupMember(
                    user_id=user_id,
                    group_id=group_id,
                    tenant_id=tenant_id,
                )
                self.db.add(member)

        await self.db.flush()

    async def remove_members(
        self,
        group_id: int,
        user_ids: list[int],
        tenant_id: int,
    ) -> None:
        """Remove members from group"""
        stmt = select(UserGroupMember).where(
            UserGroupMember.group_id == group_id,
            UserGroupMember.user_id.in_(user_ids),
            UserGroupMember.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        for member in result.scalars():
            await self.db.delete(member)
        await self.db.flush()

    async def get_group_members(
        self,
        group_id: int,
        tenant_id: int,
    ) -> list[UserGroupMember]:
        """Get all members of a group"""
        stmt = (
            select(UserGroupMember)
            .options(selectinload(UserGroupMember.user))
            .where(
                UserGroupMember.group_id == group_id,
                UserGroupMember.tenant_id == tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def to_response(group: UserGroup) -> dict[str, Any]:
        """Convert group to response dict"""
        return {
            "id": group.id,
            "name": group.name,
            "code": group.code,
            "description": group.description,
            "parentId": group.parent_id,
            "path": group.path,
            "level": group.level,
            "sortOrder": group.sort_order,
            "isActive": group.is_active,
            "memberCount": len(group.members) if group.members else 0,
            "createdAt": group.created_at.isoformat() if group.created_at else None,
            "children": [
                UserGroupService.to_response(child)
                for child in group.children
            ] if group.children else [],
        }

    @staticmethod
    def to_list_item(group: UserGroup) -> dict[str, Any]:
        """Convert group to list item dict"""
        return {
            "id": group.id,
            "name": group.name,
            "code": group.code,
            "description": group.description,
            "parentId": group.parent_id,
            "path": group.path,
            "level": group.level,
            "sortOrder": group.sort_order,
            "isActive": group.is_active,
            "memberCount": len(group.members) if group.members else 0,
            "createdAt": group.created_at.isoformat() if group.created_at else None,
        }
