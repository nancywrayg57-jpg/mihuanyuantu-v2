"""
AOJU Backend - Team Models

团队管理数据模型
"""
from enum import IntEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import TenantBaseModel

if TYPE_CHECKING:
    from app.domain.users.models import User


class TeamStatus(IntEnum):
    """Team status enumeration"""
    DISABLED = 0  # 禁用
    ENABLED = 1   # 启用


class Team(TenantBaseModel):
    """
    Team Model
    
    团队模型，支持树形结构和租户隔离
    """
    __tablename__ = "teams"
    __table_args__ = {"comment": "团队表"}

    # 基本信息
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="团队名称"
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="团队编码/标识"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        default=TeamStatus.ENABLED,
        nullable=False,
        comment="状态: 0=禁用, 1=启用"
    )

    sort_order: Mapped[int | None] = mapped_column(
        Integer,
        default=0,
        comment="显示排序"
    )

    # 详细信息
    description: Mapped[str | None] = mapped_column(
        String(500),
        comment="团队描述"
    )

    leader: Mapped[str | None] = mapped_column(
        String(100),
        comment="团队负责人"
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        comment="联系电话"
    )

    email: Mapped[str | None] = mapped_column(
        String(100),
        comment="邮箱"
    )

    # 树形结构
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("teams.id", ondelete="CASCADE"),
        comment="上级团队ID"
    )

    # 创建人（用于数据权限控制）
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Created by user ID",
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="user_teams",
        back_populates="teams",
        lazy="selectin",
    )

    @property
    def is_enabled(self) -> bool:
        """Check if team is enabled"""
        return self.status == TeamStatus.ENABLED

    @property
    def is_disabled(self) -> bool:
        """Check if team is disabled"""
        return self.status == TeamStatus.DISABLED

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name='{self.name}', code='{self.code}', tenant_id={self.tenant_id})>"
