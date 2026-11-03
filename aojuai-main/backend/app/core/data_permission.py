"""
AOJU Backend - Data Permission Module

数据权限控制模块，基于团队实现数据隔离。

数据操作权限 (data_permissions) - 位运算:
- 1 (0b001): 只读权限
- 2 (0b010): 编辑权限
- 4 (0b100): 删除权限

权限检查逻辑：
- 检查目标用户是否属于当前用户有权限的团队
- 如果目标用户属于有权限的团队，则当前用户可以操作该用户
- 超级管理员拥有全部权限
"""
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError

if TYPE_CHECKING:
    from app.domain.users.models import User



class DataRange(IntEnum):
    """数据权限范围枚举"""
    SELF_ONLY = 0       # 仅本人数据
    OWN_TEAM = 1        # 本团队数据
    TEAM_AND_BELOW = 2  # 本团队及以下
    CUSTOM_TEAMS = 3    # 自定义团队
    ALL = 4             # 全部数据


class DataPermission(IntEnum):
    """数据操作权限枚举（位运算）"""
    READ = 1    # 只读权限 0b001
    EDIT = 2    # 编辑权限 0b010
    DELETE = 4  # 删除权限 0b100


@dataclass
class DataScope:
    """
    数据权限范围对象

    Attributes:
        read_team_ids: 可读取的团队ID列表（["*"] 表示全部）
        edit_team_ids: 可编辑的团队ID列表（["*"] 表示全部）
        delete_team_ids: 可删除的团队ID列表（["*"] 表示全部）
        user_id: 用户ID（用于本人数据过滤）
        team_and_below_ids: 拥有"本团队及以下"权限的团队ID列表（用于判断是否可以在该团队下创建子团队）
    """
    read_team_ids: list[int | str] = field(default_factory=list)
    edit_team_ids: list[int | str] = field(default_factory=list)
    delete_team_ids: list[int | str] = field(default_factory=list)
    user_id: int | None = None
    team_and_below_ids: list[int] = field(default_factory=list)  # 拥有"本团队及以下"权限的团队ID列表

    @property
    def has_all_read_access(self) -> bool:
        """是否有全部数据读取权限"""
        return "*" in self.read_team_ids

    @property
    def has_all_edit_access(self) -> bool:
        """是否有全部数据编辑权限"""
        return "*" in self.edit_team_ids

    @property
    def has_all_delete_access(self) -> bool:
        """是否有全部数据删除权限"""
        return "*" in self.delete_team_ids

    def can_read(self, team_id: int) -> bool:
        """检查是否有指定团队的读取权限"""
        return self.has_all_read_access or team_id in self.read_team_ids

    def can_edit(self, team_id: int) -> bool:
        """检查是否有指定团队的编辑权限"""
        return self.has_all_edit_access or team_id in self.edit_team_ids

    def can_delete(self, team_id: int) -> bool:
        """检查是否有指定团队的删除权限"""
        return self.has_all_delete_access or team_id in self.delete_team_ids

    def can_create_child_team(self, parent_team_id: int) -> bool:
        """
        检查是否可以在指定团队下创建子团队

        只有当用户对父团队拥有"本团队及以下"权限时，才能在该团队下创建子团队。

        Args:
            parent_team_id: 父团队ID

        Returns:
            是否可以在该团队下创建子团队
        """
        # 如果有全部编辑权限，可以创建
        if self.has_all_edit_access:
            return True

        # 检查父团队是否在"本团队及以下"权限列表中
        return parent_team_id in self.team_and_below_ids

    async def check_read_permission(
        self,
        user_id: int,
        db: AsyncSession,
        raise_error: bool = True
    ) -> bool:
        """
        检查对目标用户的读取权限

        检查逻辑：目标用户是否属于当前用户有读取权限的团队

        Args:
            user_id: 目标用户ID
            db: 数据库会话
            raise_error: 无权限时是否抛出异常

        Returns:
            是否有权限

        Raises:
            ForbiddenError: 无权限且 raise_error=True 时抛出
        """
        return await self._check_permission(user_id, db, "read", raise_error)

    async def check_edit_permission(
        self,
        user_id: int,
        db: AsyncSession,
        raise_error: bool = True
    ) -> bool:
        """
        检查对目标用户的编辑权限

        检查逻辑：目标用户是否属于当前用户有编辑权限的团队

        Args:
            user_id: 目标用户ID
            db: 数据库会话
            raise_error: 无权限时是否抛出异常

        Returns:
            是否有权限

        Raises:
            ForbiddenError: 无权限且 raise_error=True 时抛出
        """
        return await self._check_permission(user_id, db, "edit", raise_error)

    async def check_delete_permission(
        self,
        user_id: int,
        db: AsyncSession,
        raise_error: bool = True
    ) -> bool:
        """
        检查对目标用户的删除权限

        检查逻辑：目标用户是否属于当前用户有删除权限的团队

        Args:
            user_id: 目标用户ID
            db: 数据库会话
            raise_error: 无权限时是否抛出异常

        Returns:
            是否有权限

        Raises:
            ForbiddenError: 无权限且 raise_error=True 时抛出
        """
        return await self._check_permission(user_id, db, "delete", raise_error)

    async def _check_permission(
        self,
        target_user_id: int,
        db: AsyncSession,
        operation: str,
        raise_error: bool = True
    ) -> bool:
        """
        内部方法：检查对目标用户的操作权限

        权限检查逻辑：
        1. 如果有全部权限，直接返回 True
        2. 如果是本人，直接返回 True
        3. 查询目标用户所属的团队，检查当前用户是否有这些团队的权限

        Args:
            target_user_id: 目标用户ID
            db: 数据库会话
            operation: 操作类型 (read/edit/delete)
            raise_error: 无权限时是否抛出异常

        Returns:
            是否有权限
        """
        from app.domain.users.models import UserTeam

        # 获取对应操作的权限检查方法
        if operation == "read":
            if self.has_all_read_access:
                return True
            check_func = self.can_read
        elif operation == "edit":
            if self.has_all_edit_access:
                return True
            check_func = self.can_edit
        elif operation == "delete":
            if self.has_all_delete_access:
                return True
            check_func = self.can_delete
        else:
            raise ValueError(f"Unknown operation: {operation}")

        # 如果是本人，允许访问
        if target_user_id == self.user_id:
            return True

        # 查询目标用户所属的团队
        stmt = select(UserTeam.team_id).where(UserTeam.user_id == target_user_id)
        result = await db.execute(stmt)
        target_team_ids = [row.team_id for row in result.fetchall()]

        # 如果用户没有团队，拒绝访问
        if not target_team_ids:
            if raise_error:
                operation_names = {"read": "查看", "edit": "编辑", "delete": "删除"}
                raise ForbiddenError(message=f"无权{operation_names.get(operation, operation)}该用户")
            return False

        # 检查是否有目标用户所属团队的权限
        has_permission = any(check_func(team_id) for team_id in target_team_ids)

        if not has_permission and raise_error:
            operation_names = {"read": "查看", "edit": "编辑", "delete": "删除"}
            raise ForbiddenError(message=f"无权{operation_names.get(operation, operation)}该用户")

        return has_permission
async def get_team_children_ids(db: AsyncSession, team_ids: list[int], tenant_id: int) -> list[int]:
    """
    递归获取团队及其所有子团队的ID

    Args:
        db: 数据库会话
        team_ids: 父团队ID列表
        tenant_id: 租户ID

    Returns:
        包含所有子团队ID的列表
    """
    if not team_ids:
        return []

    all_team_ids = set(team_ids)

    # 使用递归 CTE 查询所有子团队
    # 递归 CTE：PG / SQLite 均支持；IN + expanding 代替 PG 专有的 = ANY(array)
    sql = text("""
        WITH RECURSIVE team_tree AS (
            -- 基础查询：选择指定的团队
            SELECT id, parent_id
            FROM teams
            WHERE id IN :team_ids AND tenant_id = :tenant_id AND deleted_at IS NULL

            UNION ALL

            -- 递归查询：选择子团队
            SELECT t.id, t.parent_id
            FROM teams t
            INNER JOIN team_tree tt ON t.parent_id = tt.id
            WHERE t.tenant_id = :tenant_id AND t.deleted_at IS NULL
        )
        SELECT DISTINCT id FROM team_tree
    """).bindparams(bindparam("team_ids", expanding=True))

    result = await db.execute(sql, {"team_ids": team_ids, "tenant_id": tenant_id})
    rows = result.fetchall()

    for row in rows:
        all_team_ids.add(row.id)

    return list(all_team_ids)


async def get_user_data_scope(
    db: AsyncSession,
    user: "User",
    load_relations: bool = True
) -> DataScope:
    """
    获取用户的数据权限范围

    根据用户的角色配置，计算用户可以访问的团队列表和操作权限。

    Args:
        db: 数据库会话
        user: 用户对象
        load_relations: 是否加载用户的角色和团队关系

    Returns:
        DataScope: 数据权限范围对象，包含可读取、编辑、删除的团队ID列表
    """
    from app.domain.users.models import User
    from app.domain.roles.models import Role

    # 超级管理员拥有全部权限
    if user.is_superuser:
        return DataScope(
            read_team_ids=["*"],
            edit_team_ids=["*"],
            delete_team_ids=["*"],
            user_id=user.id
        )

    # 如果需要加载关系，重新查询用户
    if load_relations:
        stmt = (
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.teams)
            )
            .where(User.id == user.id, User.tenant_id == user.tenant_id)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return DataScope(user_id=user.id if user else None)

    # 检查用户是否有角色
    if not user.roles:
        return DataScope(user_id=user.id)

    # 用于存储团队ID和权限的映射 {team_id: permissions}
    # 使用位或运算合并同一团队的多个角色权限，取权限并集
    team_permissions_map: dict[int, int] = {}

    # 记录用户本人所属的团队ID（这些团队用户拥有"本团队及以下"权限）
    # 用于判断用户是否可以在这些团队下创建子团队
    team_and_below_ids: set[int] = set()

    # 遍历用户的每个角色，合并团队和权限
    for role in user.roles:
        if not role.is_active:
            continue

        role_data_range = role.data_range
        role_permissions = role.data_permissions

        if role_data_range == DataRange.SELF_ONLY:
            # 仅本人数据权限 - 不添加团队
            pass

        elif role_data_range == DataRange.OWN_TEAM:
            # 本团队数据权限
            for team in user.teams:
                team_id = team.id
                if team_id in team_permissions_map:
                    team_permissions_map[team_id] |= role_permissions
                else:
                    team_permissions_map[team_id] = role_permissions

        elif role_data_range == DataRange.TEAM_AND_BELOW:
            # 本团队及以下数据权限
            user_team_ids = [team.id for team in user.teams]

            # 获取所有子团队ID
            all_team_ids = await get_team_children_ids(db, user_team_ids, user.tenant_id)
            
            # 记录拥有"本团队及以下"权限的所有团队ID（包括子团队）
            # 用户可以在这些团队下创建子团队
            # 只有当角色包含编辑权限时，才记录为可创建子团队的团队
            if role_permissions & DataPermission.EDIT:
                team_and_below_ids.update(all_team_ids)

            for team_id in all_team_ids:
                if team_id in team_permissions_map:
                    team_permissions_map[team_id] |= role_permissions
                else:
                    team_permissions_map[team_id] = role_permissions

        elif role_data_range == DataRange.CUSTOM_TEAMS:
            # 自定义数据权限：查询角色-团队关联表
            sql = text(
                "SELECT team_id, permissions FROM role_teams "
                "WHERE role_id = :role_id"
            )
            result = await db.execute(sql, {"role_id": role.id})
            rows = result.fetchall()
            for row in rows:
                team_id = row.team_id
                permissions = row.permissions
                if team_id in team_permissions_map:
                    team_permissions_map[team_id] |= permissions
                else:
                    team_permissions_map[team_id] = permissions

        elif role_data_range == DataRange.ALL:
            # 全部数据权限
            return DataScope(
                read_team_ids=["*"],
                edit_team_ids=["*"],
                delete_team_ids=["*"],
                user_id=user.id,
                team_and_below_ids=[]  # 全部权限时不需要此列表
            )

    # 从 team_permissions_map 中提取各类权限的团队ID列表
    read_team_ids: list[int] = []
    edit_team_ids: list[int] = []
    delete_team_ids: list[int] = []

    for team_id, permissions in team_permissions_map.items():
        if permissions & DataPermission.READ:
            read_team_ids.append(team_id)
        if permissions & DataPermission.EDIT:
            edit_team_ids.append(team_id)
        if permissions & DataPermission.DELETE:
            delete_team_ids.append(team_id)

    # 当权限列表为空时，添加0以保证有数据（避免SQL查询问题）
    if not read_team_ids:
        read_team_ids = [0]
    if not edit_team_ids:
        edit_team_ids = [0]
    if not delete_team_ids:
        delete_team_ids = [0]

    return DataScope(
        read_team_ids=read_team_ids,
        edit_team_ids=edit_team_ids,
        delete_team_ids=delete_team_ids,
        user_id=user.id,
        team_and_below_ids=list(team_and_below_ids)
    )
