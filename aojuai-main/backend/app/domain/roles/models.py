"""
AOJU Backend - Role Models

Role model for RBAC permission system.
Follows itrainer design: roles associate with menus (not separate permissions).
Data permissions follow itrainer design with data_range and data_permissions fields.
"""
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import AssociationBaseModel, TenantBaseModel
from app.infrastructure.database.types import PortableJSON

if TYPE_CHECKING:
    from app.domain.menus.models import Menu
    from app.domain.teams.models import Team
    from app.domain.users.models import User


class DataRangeEnum(IntEnum):
    """
    数据权限范围枚举
    
    Follows itrainer design:
    - 0: 仅本人数据
    - 1: 本团队数据
    - 2: 本团队及以下数据
    - 3: 自定义团队数据
    - 4: 全部数据
    """
    SELF = 0          # 仅本人
    TEAM = 1          # 本团队
    DEPT = 1          # 兼容旧命名
    TEAM_BELOW = 2    # 本团队及以下
    DEPT_BELOW = 2    # 兼容旧命名
    CUSTOM = 3        # 自定义团队
    ALL = 4           # 全部


class DataPermissionFlag(IntEnum):
    """
    数据操作权限标志（位运算）
    
    Follows itrainer design:
    - 1: 只读
    - 2: 编辑
    - 4: 删除
    
    可组合使用，如 3 = 只读+编辑, 7 = 只读+编辑+删除
    """
    READ = 1    # 只读
    EDIT = 2    # 编辑
    DELETE = 4  # 删除


class Role(TenantBaseModel):
    """
    Role Model - 角色

    RBAC role entity with permission associations.
    Follows itrainer design for data permissions.
    """

    __tablename__ = "roles"

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Role name",
    )

    # Audit
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Created by user ID",
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Role code (e.g., 'admin', 'user')",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Role description",
    )

    # Sorting & Status
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Sort order",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Is role active",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is system built-in role (cannot be deleted)",
    )

    # Data Permissions (itrainer design)
    data_range: Mapped[int] = mapped_column(
        Integer,
        default=DataRangeEnum.ALL,
        nullable=False,
        comment="数据权限范围: 0=仅本人, 1=本团队, 2=本团队及以下, 3=自定义团队, 4=全部",
    )
    data_permissions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="数据操作权限(位运算: 1=只读, 2=编辑, 4=删除)",
    )

    # Extra
    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra attributes",
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
        lazy="selectin",
    )
    menus: Mapped[list["Menu"]] = relationship(
        "Menu",
        secondary="role_menus",
        back_populates="roles",
        lazy="selectin",
    )
    teams: Mapped[list["Team"]] = relationship(
        "Team",
        secondary="role_teams",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, code={self.code}, name={self.name})>"


class RoleMenu(AssociationBaseModel):
    """
    Role-Menu Association - 角色菜单关联表
    
    使用复合主键 (role_id, menu_id)，不需要单独的 id 字段
    """

    __tablename__ = "role_menus"

    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Role ID",
    )
    menu_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("menus.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Menu ID",
    )


class RoleTeam(AssociationBaseModel):
    """
    Role-Team Association - 角色团队关联表
    
    用于自定义团队数据权限（当 data_range=3 时）
    使用复合主键 (role_id, team_id)，不需要单独的 id 字段
    """

    __tablename__ = "role_teams"

    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Role ID",
    )
    team_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Team ID",
    )
    permissions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="数据操作权限(位运算: 1=只读, 2=编辑, 4=删除)",
    )
