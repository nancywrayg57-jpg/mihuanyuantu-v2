"""
AOJU Backend - User Models

User model with role associations.
Compatible with vue-pure-admin frontend.
"""
from datetime import UTC, datetime
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import AssociationBaseModel, TenantBaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON

if TYPE_CHECKING:
    from app.domain.organizations.models import Organization
    from app.domain.roles.models import Role
    from app.domain.teams.models import Team
    from app.domain.user_groups.models import UserGroupMember


class UserStatus(IntEnum):
    """User status enumeration"""
    DISABLED = 0      # 禁用
    ENABLED = 1       # 正常
    PENDING = 2       # 待审核（注册待审核）
    REJECTED = 3      # 审核拒绝


class UserSex(IntEnum):
    """User sex enumeration"""
    UNKNOWN = 0       # 未知
    MALE = 1          # 男性
    FEMALE = 2        # 女性


class RegisterSource(str):
    """User registration source constants"""
    ADMIN = "admin"   # 管理员创建
    SELF = "self"     # 自助注册
    INVITE = "invite" # 邀请注册


class User(TenantBaseModel):
    """
    User Model - 用户

    Core user entity with authentication and profile info.
    """

    __tablename__ = "users"

    # Authentication
    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Login username",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password",
    )

    # Profile
    nickname: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Display nickname",
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Avatar URL",
    )
    email: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Email address",
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Phone number",
    )
    sex: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Sex: 0=unknown, 1=male, 2=female",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="User bio/description",
    )

    # Status
    status: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Status: 0=disabled, 1=enabled, 2=pending, 3=rejected",
    )

    # Registration & Audit
    register_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="admin",
        comment="Registration source: admin, self, invite",
    )
    audit_remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Audit remark (for approval/rejection)",
    )
    audited_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Audit timestamp",
    )
    audited_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Audited by user ID",
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is superuser (bypass all permissions)",
    )

    # Organization
    organization_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Organization/Team ID",
    )

    # Security
    last_login_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Last login timestamp",
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Last login IP address",
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Failed login attempts",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Account locked until this time",
    )

    # Extra
    remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Admin remark",
    )
    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra attributes",
    )

    # Relationships
    # Note: tenant relationship removed due to ForeignKey issues
    # tenant_id is used directly for filtering
    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        back_populates="users",
        foreign_keys=[organization_id],
        lazy="joined",
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )
    teams: Mapped[list["Team"]] = relationship(
        "Team",
        secondary="user_teams",
        back_populates="users",
        lazy="selectin",
    )
    group_memberships: Mapped[list["UserGroupMember"]] = relationship(
        "UserGroupMember",
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"

    @property
    def is_active(self) -> bool:
        """Check if user is active and not locked"""
        if self.status != UserStatus.ENABLED:
            return False
        return not (self.locked_until and self.locked_until > datetime.now(UTC))

    @property
    def is_pending(self) -> bool:
        """Check if user is pending approval"""
        return self.status == UserStatus.PENDING


class UserRole(AssociationBaseModel):
    """
    User-Role Association - 用户角色关联

    Many-to-many relationship between users and roles.
    """

    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="User ID",
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Role ID",
    )


class UserTeam(AssociationBaseModel):
    """
    User-Team Association - 用户团队关联

    Many-to-many relationship between users and teams.
    """

    __tablename__ = "user_teams"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="User ID",
    )
    team_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Team ID",
    )
