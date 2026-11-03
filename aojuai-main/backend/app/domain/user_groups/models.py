"""
AOJU Backend - User Group Models

User groups for organizing users (separate from roles).
Supports unlimited hierarchy using materialized path pattern.
Example: 集团 -> 分公司 -> 团队 -> 小组
"""
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from app.infrastructure.database.types import PortableJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import AssociationBaseModel, TenantBaseModel

if TYPE_CHECKING:
    from app.domain.users.models import User


class UserGroup(TenantBaseModel):
    """
    User Group Model - 用户分组

    Groups for organizing users (marketing, development, etc.)
    Supports unlimited hierarchy using materialized path.
    Different from roles which are for permissions.
    """

    __tablename__ = "user_groups"

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Group name",
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Group code (unique within tenant)",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Group description",
    )

    # Hierarchy (materialized path pattern)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("user_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent group ID",
    )
    path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="",
        index=True,
        comment="Materialized path (e.g., '/1/2/3/')",
    )
    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Hierarchy level (1=root)",
    )

    # Display
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
        comment="Is active",
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
    parent: Mapped["UserGroup | None"] = relationship(
        "UserGroup",
        remote_side="UserGroup.id",
        back_populates="children",
    )
    children: Mapped[list["UserGroup"]] = relationship(
        "UserGroup",
        back_populates="parent",
        lazy="selectin",
    )
    members: Mapped[list["UserGroupMember"]] = relationship(
        "UserGroupMember",
        back_populates="group",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<UserGroup(id={self.id}, code={self.code}, name={self.name}, level={self.level})>"

    def update_path(self, parent: "UserGroup | None" = None) -> None:
        """Update materialized path based on parent"""
        if parent:
            self.path = f"{parent.path}{parent.id}/"
            self.level = parent.level + 1
        else:
            self.path = "/"
            self.level = 1

    @property
    def ancestor_ids(self) -> list[int]:
        """Get list of ancestor IDs from path"""
        if not self.path or self.path == "/":
            return []
        parts = self.path.strip("/").split("/")
        return [int(p) for p in parts if p]


class UserGroupMember(AssociationBaseModel):
    """
    User Group Member - 用户分组成员

    Many-to-many relationship between users and groups.
    """

    __tablename__ = "user_group_members"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="User ID",
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_groups.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Group ID",
    )
    is_leader: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is group leader",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="group_memberships",
        lazy="joined",
    )
    group: Mapped["UserGroup"] = relationship(
        "UserGroup",
        back_populates="members",
        lazy="joined",
    )
