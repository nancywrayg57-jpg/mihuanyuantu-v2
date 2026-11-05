"""
AOJU Backend - Organization Models

Organization represents teams in a tree structure.
"""
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON

if TYPE_CHECKING:
    from app.domain.users.models import User


class Organization(TenantBaseModel):
    """
    Organization Model - 组织架构/团队

    Tree structure using materialized path pattern.
    """

    __tablename__ = "organizations"

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Organization name",
    )
    code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Organization code",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Organization description",
    )

    # Tree Structure
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent organization ID",
    )
    path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="Materialized path (e.g., '1/2/3')",
    )
    level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Tree level (1 = root)",
    )

    # Sorting & Status
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Sort order within same parent",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Is organization active",
    )

    # Leader
    leader_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Team leader user ID",
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
    # Note: tenant relationship removed due to ForeignKey issues
    parent: Mapped["Organization | None"] = relationship(
        "Organization",
        remote_side="Organization.id",
        back_populates="children",
        lazy="joined",
    )
    children: Mapped[list["Organization"]] = relationship(
        "Organization",
        back_populates="parent",
        lazy="selectin",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        foreign_keys="User.organization_id",
        lazy="selectin",
    )
    leader: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[leader_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, level={self.level})>"
