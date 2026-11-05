"""
AOJU Backend - Role Service

Role management service with multi-tenant support.
Follows itrainer design for data permissions.
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.domain.menus.models import Menu
from app.domain.menus.service import expand_menu_ids_with_ancestors
from app.domain.roles.models import Role, RoleMenu, RoleTeam
from app.domain.teams.models import Team
from app.infrastructure.cache import bump_tenant_permissions_cache_version
from app.infrastructure.repository.base import RepositoryBase


class RoleService(RepositoryBase[Role]):
    """Role business logic"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Role)
        self._default_options = [selectinload(Role.menus), selectinload(Role.teams)]

    async def get_by_id(self, role_id: int, tenant_id: int) -> Role | None:
        """Get role by ID (tenant-scoped)"""
        return await self.get_one(
            where=[Role.id == role_id, Role.tenant_id == tenant_id],
            options=self._default_options,
        )

    async def get_by_code(self, code: str, tenant_id: int) -> Role | None:
        """Get role by code (tenant-scoped)"""
        return await self.get_one(
            where=[Role.code == code, Role.tenant_id == tenant_id],
        )

    async def list_roles(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 10,
        name: str | None = None,
        code: str | None = None,
        status: int | None = None,
        team_ids: list[int] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[Role], int]:
        """
        List roles with pagination

        Args:
            tenant_id: 租户ID
            page: 页码
            page_size: 每页数量
            name: 角色名称（模糊搜索）
            code: 角色编码（模糊搜索）
            status: 状态
            team_ids: 团队ID列表（数据权限过滤，角色创建人需属于这些团队之一）
            sort_by: 排序字段 (id, name, code, sort_order, created_at)
            sort_order: 排序方向 (asc, desc)
        """
        from app.domain.users.models import UserTeam

        where = [Role.tenant_id == tenant_id]

        if name:
            where.append(Role.name.ilike(f"%{name}%"))
        if code:
            where.append(Role.code.ilike(f"%{code}%"))
        if status is not None:
            where.append(Role.is_active == (status == 1))

        # 数据权限过滤：角色创建人需属于指定团队之一
        if team_ids is not None and len(team_ids) > 0:
            # 子查询：获取属于指定团队的用户ID
            subquery = (
                select(UserTeam.user_id)
                .where(UserTeam.team_id.in_(team_ids))
                .distinct()
            )
            # 角色创建人在子查询结果中，或者创建人为空（系统角色）
            where.append(
                (Role.created_by.in_(subquery)) | (Role.created_by.is_(None))
            )

        # 排序处理
        allowed_sort_fields = {"id", "name", "code", "sort_order", "created_at"}
        order_field = sort_by if sort_by in allowed_sort_fields else "id"
        order_desc = sort_order and sort_order.lower() == "desc"

        return await self.get_list(
            page=page,
            page_size=page_size,
            where=where,
            options=self._default_options,
            order_by=order_field,
            order_desc=order_desc,
            return_total=True,
        )

    async def get_all_roles(self, tenant_id: int) -> list[Role]:
        """Get all active roles for dropdown"""
        return await self.get_list(
            page_size=0,  # No pagination
            where=[Role.tenant_id == tenant_id, Role.is_active.is_(True)],
            order_by="sort_order",
        )

    async def create_role(
        self,
        tenant_id: int,
        name: str,
        code: str,
        description: str | None = None,
        sort_order: int = 0,
        is_active: bool = True,
        menu_ids: list[int] | None = None,
        data_range: int = 4,
        data_permissions: int = 0,
        team_permissions: list[dict[str, Any]] | None = None,
        created_by: int | None = None,
    ) -> Role:
        """Create a new role"""
        existing = await self.get_by_code(code, tenant_id)
        if existing:
            raise ConflictError(message=f"Role code '{code}' already exists")

        role_data = {
            "tenant_id": tenant_id,
            "name": name,
            "code": code,
            "description": description,
            "sort_order": sort_order,
            "is_active": is_active,
            "is_system": False,
            "data_range": data_range,
            "data_permissions": data_permissions,
            "created_by": created_by,
        }
        role = await self.create(role_data)

        if menu_ids:
            await self._assign_menus(role, menu_ids, tenant_id)

        if team_permissions:
            await self._assign_team_permissions(role, team_permissions, tenant_id)

        if menu_ids or team_permissions:
            await self.db.refresh(role)

        await bump_tenant_permissions_cache_version(tenant_id)
        return role

    async def update_role(
        self,
        role_id: int,
        tenant_id: int,
        name: str | None = None,
        code: str | None = None,
        description: str | None = None,
        sort_order: int | None = None,
        is_active: bool | None = None,
        data_range: int | None = None,
        data_permissions: int | None = None,
    ) -> Role:
        """Update role"""
        role = await self.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundError(message="Role not found")

        if code and code != role.code:
            existing = await self.get_by_code(code, tenant_id)
            if existing:
                raise ConflictError(message=f"Role code '{code}' already exists")

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if code is not None:
            update_data["code"] = code
        if description is not None:
            update_data["description"] = description
        if sort_order is not None:
            update_data["sort_order"] = sort_order
        if is_active is not None:
            update_data["is_active"] = is_active
        if data_range is not None:
            update_data["data_range"] = data_range
        if data_permissions is not None:
            update_data["data_permissions"] = data_permissions

        updated_role = await self.update(role, update_data, exclude_unset=False)
        await bump_tenant_permissions_cache_version(tenant_id)
        return updated_role

    async def delete_role(self, role_id: int, tenant_id: int) -> None:
        """Soft delete role"""
        role = await self.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundError(message="Role not found")

        if role.is_system:
            raise BusinessError(message="Cannot delete system role")

        await self.delete(role)
        await bump_tenant_permissions_cache_version(tenant_id)

    async def update_menus(
        self,
        role_id: int,
        tenant_id: int,
        menu_ids: list[int],
    ) -> Role:
        """Update role menus (replace all)"""
        role = await self.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundError(message="Role not found")

        await self._clear_menus(role_id, tenant_id)

        if menu_ids:
            await self._assign_menus(role, menu_ids, tenant_id)

        await self.db.flush()
        await self.db.refresh(role)
        await bump_tenant_permissions_cache_version(tenant_id)
        return role

    async def _assign_menus(
        self,
        role: Role,
        menu_ids: list[int],
        tenant_id: int,
    ) -> None:
        """Assign menus to role"""
        # 菜单行是逐租户的，授权必须限定在本租户内。
        # 原来这里注释写着"菜单是系统级、不按租户"并刻意不过滤，
        # 结果 A 租户的角色可以被授予 B 租户的菜单 id —— 越权写入 role_menus。
        expanded_menu_ids = await expand_menu_ids_with_ancestors(self.db, menu_ids)
        if not expanded_menu_ids:
            return
        menu_repo = RepositoryBase(self.db, Menu)
        menus = await menu_repo.get_list(
            page_size=0,
            where=[Menu.id.in_(expanded_menu_ids), Menu.tenant_id == tenant_id],
        )
        valid_menus = {m.id for m in menus}

        for menu_id in expanded_menu_ids:
            if menu_id in valid_menus:
                role_menu = RoleMenu(
                    role_id=role.id,
                    menu_id=menu_id,
                    tenant_id=tenant_id,
                )
                self.db.add(role_menu)

    async def _clear_menus(self, role_id: int, tenant_id: int) -> None:
        """Clear all menus from role"""
        stmt = select(RoleMenu).where(
            RoleMenu.role_id == role_id,
            RoleMenu.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        for role_menu in result.scalars():
            await self.db.delete(role_menu)

    async def update_team_permissions(
        self,
        role_id: int,
        tenant_id: int,
        team_permissions: list[dict[str, Any]],
    ) -> Role:
        """Update role team permissions (replace all)"""
        role = await self.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundError(message="Role not found")

        await self._clear_teams(role_id, tenant_id)

        if team_permissions:
            await self._assign_team_permissions(role, team_permissions, tenant_id)

        await self.db.flush()
        await self.db.refresh(role)
        return role

    async def _assign_team_permissions(
        self,
        role: Role,
        team_permissions: list[dict[str, Any]],
        tenant_id: int,
    ) -> None:
        """Assign teams with permissions to role"""
        team_ids = [tp["id"] for tp in team_permissions]
        team_repo = RepositoryBase(self.db, Team)
        teams = await team_repo.get_list(
            page_size=0,
            where=[Team.id.in_(team_ids), Team.tenant_id == tenant_id],
        )
        valid_team_ids = {t.id for t in teams}

        for team_perm in team_permissions:
            team_id = team_perm["id"]
            permissions = team_perm.get("permissions", 0)
            if team_id in valid_team_ids:
                role_team = RoleTeam(
                    role_id=role.id,
                    team_id=team_id,
                    tenant_id=tenant_id,
                    permissions=permissions,
                )
                self.db.add(role_team)

    async def _clear_teams(self, role_id: int, tenant_id: int) -> None:
        """Clear all teams from role"""
        stmt = select(RoleTeam).where(
            RoleTeam.role_id == role_id,
            RoleTeam.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        for role_team in result.scalars():
            await self.db.delete(role_team)

    async def get_role_team_permissions(self, role_id: int, tenant_id: int) -> list[dict[str, Any]]:
        """Get role team permissions"""
        stmt = select(RoleTeam).where(
            RoleTeam.role_id == role_id,
            RoleTeam.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return [
            {"id": rt.team_id, "permissions": rt.permissions}
            for rt in result.scalars()
        ]

    async def to_list_item(self, role: Role) -> dict[str, Any]:
        """Convert role to list item dict"""
        menu_ids: list[int] = []
        if hasattr(role, "menus") and role.menus:
            menu_ids = [
                menu.id for menu in role.menus if menu.deleted_at is None
            ]

        team_permissions = await self.get_role_team_permissions(role.id, role.tenant_id)

        return {
            "id": role.id,
            "name": role.name,
            "code": role.code,
            "description": role.description,
            "isSystem": role.is_system,
            "isActive": role.is_active,
            "sortOrder": role.sort_order,
            "menuIds": menu_ids,
            "dataRange": role.data_range,
            "dataPermissions": role.data_permissions,
            "teamPermissions": team_permissions,
            "createdAt": role.created_at.isoformat() if role.created_at else None,
        }

    @staticmethod
    def to_simple_item(role: Role) -> dict[str, Any]:
        """Convert role to simple item dict"""
        return {
            "id": role.id,
            "name": role.name,
            "code": role.code,
        }

    async def to_response(self, role: Role) -> dict[str, Any]:
        """Convert role to response dict"""
        menus = []
        if hasattr(role, "menus") and role.menus:
            menus = [
                {
                    "id": menu.id,
                    "title": menu.title,
                    "menuType": menu.menu_type,
                    "perms": menu.perms,
                }
                for menu in role.menus
                if menu.deleted_at is None
            ]

        team_permissions = await self.get_role_team_permissions(role.id, role.tenant_id)

        return {
            "id": role.id,
            "tenantId": role.tenant_id,
            "name": role.name,
            "code": role.code,
            "description": role.description,
            "isActive": role.is_active,
            "isSystem": role.is_system,
            "sortOrder": role.sort_order,
            "dataRange": role.data_range,
            "dataPermissions": role.data_permissions,
            "teamPermissions": team_permissions,
            "createdAt": role.created_at.isoformat() if role.created_at else None,
            "updatedAt": role.updated_at.isoformat() if role.updated_at else None,
            "menus": menus,
        }
