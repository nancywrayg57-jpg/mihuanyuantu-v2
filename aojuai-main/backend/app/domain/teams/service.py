"""
AOJU Backend - Team Service

团队管理业务逻辑层

数据权限说明：
- 团队管理的数据权限与用户管理不同
- 用户管理：检查用户所属团队是否在有权限的团队列表中
- 团队管理：直接检查团队ID本身是否在有权限的团队列表中
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.domain.teams.models import Team, TeamStatus
from app.domain.teams.schemas import TeamCreate, TeamUpdate
from app.infrastructure.repository import RepositoryBase

DEFAULT_TEAM_CODE = "__default__"
DEFAULT_TEAM_NAME = "默认团队"
DEFAULT_TEAM_DESCRIPTION = "系统默认团队（未分组用户）"


class TeamService(RepositoryBase[Team]):
    """
    团队业务逻辑层
    
    继承 RepositoryBase 获得通用的 CRUD 方法，
    同时提供团队相关的业务逻辑处理。
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db, Team)

    # ==================== 查询方法 ====================

    async def get_team_by_id(
        self,
        team_id: int,
        tenant_id: int
    ) -> Team | None:
        """根据 ID 获取团队（限定租户）"""
        return await self.get_one(
            where=[
                Team.id == team_id,
                Team.tenant_id == tenant_id
            ]
        )

    async def get_by_code(
        self,
        code: str,
        tenant_id: int
    ) -> Team | None:
        """根据团队编码获取团队（限定租户）"""
        return await self.get_one(
            where=[Team.tenant_id == tenant_id],
            code=code
        )

    async def get_team_ids_by_tenant(self, tenant_id: int, team_ids: list[int]) -> list[int]:
        """Return existing team IDs within tenant (soft-deleted excluded)."""
        if not team_ids:
            return []

        from sqlalchemy import select

        stmt = (
            select(Team.id)
            .where(
                Team.tenant_id == tenant_id,
                Team.id.in_(team_ids),
                Team.deleted_at.is_(None),
            )
            .order_by(Team.id)
        )
        result = await self.db.execute(stmt)
        return [int(team_id) for team_id in result.scalars().all()]

    async def get_existing_team_ids(self, *, tenant_id: int, team_ids: list[int]) -> set[int]:
        """Return existing team IDs within tenant (soft-deleted excluded)."""
        return set(await self.get_team_ids_by_tenant(tenant_id, team_ids))

    async def ensure_default_team(
        self,
        *,
        tenant_id: int,
        created_by: int | None = None,
    ) -> Team:
        """Ensure tenant has a default team (idempotent)."""
        existing = await self.get_by_code(DEFAULT_TEAM_CODE, tenant_id)
        if existing:
            if existing.status != int(TeamStatus.ENABLED):
                await self.update(existing, {"status": int(TeamStatus.ENABLED)}, exclude_unset=False)
                await self.db.flush()
                await self.db.refresh(existing)
            return existing

        team = await self.create(
            {
                "tenant_id": tenant_id,
                "name": DEFAULT_TEAM_NAME,
                "code": DEFAULT_TEAM_CODE,
                "status": int(TeamStatus.ENABLED),
                "sort_order": 0,
                "description": DEFAULT_TEAM_DESCRIPTION,
                "leader": None,
                "phone": None,
                "email": None,
                "parent_id": None,
                "created_by": created_by,
            }
        )
        await self.db.flush()
        await self.db.refresh(team)
        return team

    async def list_teams(
        self,
        tenant_id: int,
        name: str | None = None,
        code: str | None = None,
        status: int | None = None,
        parent_id: int | None = None,
        team_ids: list[int] | None = None,
    ) -> list[Team]:
        """
        获取团队列表（不分页，用于树形结构）
        
        Args:
            tenant_id: 租户ID
            name: 团队名称（模糊查询）
            code: 团队编码（模糊查询）
            status: 团队状态
            parent_id: 父团队ID
            team_ids: 数据权限过滤的团队ID列表（None表示不过滤，直接过滤团队ID本身）
        """
        where = [Team.tenant_id == tenant_id]
        filters = {}

        if name:
            filters["name"] = ("like", name)
        if code:
            filters["code"] = ("like", code)
        if status is not None:
            filters["status"] = status
        if parent_id is not None:
            filters["parent_id"] = parent_id

        # 数据权限过滤：直接过滤团队ID本身（团队管理与用户管理不同）
        if team_ids is not None and len(team_ids) > 0:
            where.append(Team.id.in_(team_ids))

        teams = await self.get_list(
            page_size=0,  # 不分页
            where=where,
            order_by="sort_order",
            order_desc=False,
            **filters
        )

        return teams

    async def get_tree_list(
        self,
        tenant_id: int,
        status: int | None = None,
        team_ids: list[int] | None = None,
    ) -> list[dict]:
        """
        获取团队树形列表
        
        Args:
            tenant_id: 租户ID
            status: 团队状态
            team_ids: 数据权限过滤的团队ID列表（None表示不过滤，直接过滤团队ID本身）
        """
        # 获取所有团队
        where = [Team.tenant_id == tenant_id]
        if status is not None:
            where.append(Team.status == status)

        # 数据权限过滤：直接过滤团队ID本身
        if team_ids is not None and len(team_ids) > 0:
            where.append(Team.id.in_(team_ids))

        teams = await self.get_list(
            page_size=0,
            where=where,
            order_by="sort_order",
            order_desc=False
        )

        # 构建树形结构
        return self._build_tree(teams)

    async def get_children_ids(
        self,
        team_id: int,
        tenant_id: int,
        include_self: bool = True
    ) -> list[int]:
        """获取团队及其所有子团队的ID列表"""
        result = [team_id] if include_self else []

        # 获取所有团队
        all_teams = await self.list_teams(tenant_id=tenant_id)

        # 递归获取子团队
        await self._get_children_recursive(team_id, all_teams, result)

        return result

    async def _get_children_recursive(
        self,
        parent_id: int,
        all_teams: list[Team],
        result: list[int]
    ) -> None:
        """递归获取子团队ID"""
        children = [team for team in all_teams if team.parent_id == parent_id]
        for child in children:
            result.append(child.id)
            await self._get_children_recursive(child.id, all_teams, result)

    # ==================== 创建方法 ====================

    async def create_team(
        self,
        data: TeamCreate,
        tenant_id: int,
        created_by: int | None = None,
    ) -> Team:
        """
        创建团队
        
        Args:
            data: 团队创建数据
            tenant_id: 租户ID
            created_by: 创建人用户ID
        """
        # 验证团队编码唯一性
        existing = await self.get_by_code(data.code, tenant_id)
        if existing:
            raise ConflictError(message=f"团队编码 '{data.code}' 已存在")

        # 验证父团队存在性
        if data.parent_id:
            parent = await self.get_team_by_id(data.parent_id, tenant_id)
            if not parent:
                raise NotFoundError(message="上级团队不存在")

            # 检查父团队是否被禁用
            if parent.status == TeamStatus.DISABLED:
                raise BusinessError(message="上级团队已被禁用，无法在其下创建子团队")

        # 创建团队
        team = await self.create({
            "tenant_id": tenant_id,
            "name": data.name,
            "code": data.code,
            "status": data.status,
            "sort_order": data.sort_order,
            "description": data.description,
            "leader": data.leader,
            "phone": data.phone,
            "email": data.email,
            "parent_id": data.parent_id,
            "created_by": created_by,
        })

        await self.db.flush()
        await self.db.refresh(team)

        return team

    # ==================== 更新方法 ====================

    async def update_team(
        self,
        team_id: int,
        data: TeamUpdate,
        tenant_id: int
    ) -> Team:
        """
        更新团队
        
        parent_id 的特殊处理：
        - 不传此字段：不修改上级团队
        - 传 0：设为顶级团队（parent_id = None）
        - 传正整数：移动到指定团队下
        """
        team = await self.get_team_by_id(team_id, tenant_id)
        if not team:
            raise NotFoundError(message="团队不存在")

        # 验证团队编码唯一性（如果修改了编码）
        if data.code and data.code != team.code:
            existing = await self.get_by_code(data.code, tenant_id)
            if existing:
                raise ConflictError(message=f"团队编码 '{data.code}' 已存在")

        # 处理父团队更新
        # 只有当用户明确传了 parent_id 字段时才处理
        if "parent_id" in data.model_fields_set:
            new_parent_id = data.parent_id

            # parent_id = 0 表示设为顶级团队
            if new_parent_id == 0:
                new_parent_id = None

            # 验证父团队
            if new_parent_id is not None:
                # 不能将团队设置为自己的子团队
                if new_parent_id == team_id:
                    raise BusinessError(message="不能将团队设置为自己的上级团队")

                # 验证父团队存在
                parent = await self.get_team_by_id(new_parent_id, tenant_id)
                if not parent:
                    raise NotFoundError(message="上级团队不存在")

                # 检查是否会形成循环引用
                children_ids = await self.get_children_ids(team_id, tenant_id)
                if new_parent_id in children_ids:
                    raise BusinessError(message="不能将团队移动到其子团队下")

            # 更新 parent_id（可能是 None 或正整数）
            data.parent_id = new_parent_id

        # 更新团队（exclude_unset=True 确保只更新用户明确传的字段）
        update_data = data.model_dump(exclude_unset=True)

        # 如果 parent_id 在 update_data 中但值是 0，需要转换为 None
        if "parent_id" in update_data and update_data["parent_id"] == 0:
            update_data["parent_id"] = None

        await self.update(team, update_data)

        await self.db.flush()
        await self.db.refresh(team)

        return team

    # ==================== 删除方法 ====================

    async def delete_team(
        self,
        team_id: int,
        tenant_id: int
    ) -> None:
        """删除团队（软删除）"""
        team = await self.get_team_by_id(team_id, tenant_id)
        if not team:
            raise NotFoundError(message="团队不存在")

        # 检查是否有子团队
        children = await self.list_teams(
            tenant_id=tenant_id,
            parent_id=team_id
        )
        if children:
            raise BusinessError(message="该团队下存在子团队，无法删除")

        # TODO: 检查是否有用户关联
        # 这需要在用户模块实现后添加

        # 软删除
        await self.delete(team)

    async def delete_teams_batch(
        self,
        team_ids: list[int],
        tenant_id: int
    ) -> None:
        """批量删除团队"""
        for team_id in team_ids:
            await self.delete_team(team_id, tenant_id)

    # ==================== 辅助方法 ====================

    def _build_tree(
        self,
        teams: list[Team],
        parent_id: int | None = None
    ) -> list[dict]:
        """
        构建树形结构
        
        当进行数据权限过滤时，团队的父团队可能不在列表中，
        这时需要将这些团队也作为根节点显示。
        """
        tree = []
        team_ids = {team.id for team in teams}

        for team in teams:
            # 如果是顶级团队，或者父团队不在当前列表中，作为根节点
            if team.parent_id == parent_id or (
                team.parent_id is not None and team.parent_id not in team_ids
            ):
                node = self.to_tree_node(team)
                children = self._build_tree_children(teams, team.id, team_ids)
                if children:
                    node["children"] = children
                tree.append(node)

        return tree

    def _build_tree_children(
        self,
        teams: list[Team],
        parent_id: int,
        team_ids: set[int]
    ) -> list[dict]:
        """递归构建子节点"""
        children = []

        for team in teams:
            if team.parent_id == parent_id:
                node = self.to_tree_node(team)
                sub_children = self._build_tree_children(teams, team.id, team_ids)
                if sub_children:
                    node["children"] = sub_children
                children.append(node)

        return children

    def _build_options_tree(
        self,
        teams: list[Team],
        parent_id: int | None = None
    ) -> list[dict]:
        """
        构建选项树形结构
        
        当进行数据权限过滤时，团队的父团队可能不在列表中，
        这时需要将这些团队也作为根节点显示。
        """
        tree = []
        team_ids = {team.id for team in teams}

        for team in teams:
            # 如果是顶级团队，或者父团队不在当前列表中，作为根节点
            if team.parent_id == parent_id or (
                team.parent_id is not None and team.parent_id not in team_ids
            ):
                option = {
                    "value": team.id,
                    "label": team.name,
                    "disabled": team.status == TeamStatus.DISABLED,
                }
                children = self._build_options_tree_children(teams, team.id, team_ids)
                if children:
                    option["children"] = children
                tree.append(option)

        return tree

    def _build_options_tree_children(
        self,
        teams: list[Team],
        parent_id: int,
        team_ids: set[int]
    ) -> list[dict]:
        """递归构建子选项节点"""
        children = []

        for team in teams:
            if team.parent_id == parent_id:
                option = {
                    "value": team.id,
                    "label": team.name,
                    "disabled": team.status == TeamStatus.DISABLED,
                }
                sub_children = self._build_options_tree_children(teams, team.id, team_ids)
                if sub_children:
                    option["children"] = sub_children
                children.append(option)

        return children

    async def get_tree_options(
        self,
        tenant_id: int,
        include_disabled: bool = False,
        team_ids: list[int] | None = None,
    ) -> list[dict]:
        """
        获取团队树形选项（用于下拉选择）
        
        Args:
            tenant_id: 租户ID
            include_disabled: 是否包含禁用的团队
            team_ids: 数据权限过滤的团队ID列表（None表示不过滤，直接过滤团队ID本身）
        """
        where = [Team.tenant_id == tenant_id]
        if not include_disabled:
            where.append(Team.status == TeamStatus.ENABLED)

        # 数据权限过滤：直接过滤团队ID本身
        if team_ids is not None and len(team_ids) > 0:
            where.append(Team.id.in_(team_ids))

        teams = await self.get_list(
            page_size=0,
            where=where,
            order_by="sort_order",
            order_desc=False
        )

        return self._build_options_tree(teams)

    # ==================== 数据转换方法 ====================

    @staticmethod
    def to_response(team: Team) -> dict:
        """转换为响应格式"""
        return {
            "id": team.id,
            "name": team.name,
            "code": team.code,
            "status": team.status,
            "sortOrder": team.sort_order,
            "description": team.description,
            "leader": team.leader,
            "phone": team.phone,
            "email": team.email,
            "parentId": team.parent_id,
            "tenantId": team.tenant_id,
            "createdAt": team.created_at.isoformat() if team.created_at else None,
            "updatedAt": team.updated_at.isoformat() if team.updated_at else None,
        }

    @staticmethod
    def to_list_item(team: Team) -> dict:
        """转换为列表项格式"""
        return TeamService.to_response(team)

    @staticmethod
    def to_tree_node(team: Team) -> dict:
        """转换为树节点格式"""
        node = TeamService.to_response(team)
        node["children"] = []
        return node
