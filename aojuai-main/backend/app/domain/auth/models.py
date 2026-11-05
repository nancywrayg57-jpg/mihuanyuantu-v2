"""
AOJU Backend - Tenant Models

Tenant is the top-level entity for multi-tenant isolation.
System-level entity, no tenant_id on itself.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import BaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON

if TYPE_CHECKING:
    pass


class Tenant(BaseModel):
    """
    Tenant Model - 租户

    Multi-tenant isolation root entity.
    """

    __tablename__ = "tenants"
    __table_args__ = (
        Index(
            "ix_tenants_code",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Tenant name",
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Tenant code (unique identifier)",
    )
    domain: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Custom domain for tenant",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Tenant description",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Is tenant active",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="Subscription expiry date",
    )

    # Configuration
    config: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Tenant configuration",
    )
    # Example config:
    # {
    #   "theme": "default",
    #   "logo": "https://...",
    #   "features": ["assistant", "speech"],
    #   "assistant": { "enabled": true, "model": "..." },
    #   "branding": { "primary_color": "#2563EB" },
    #   "registration": {
    #     "enabled": true,           # 是否允许自主注册
    #     "require_audit": true,     # 是否需要审核
    #     "default_role": "user"     # 默认角色
    #   }
    # }

    # Quota
    quota: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Tenant quota limits",
    )
    # Example quota:
    # {
    #   "max_users": 100,
    #   "max_ai_apps": 10,
    #   "max_ai_calls_per_month": 10000,
    #   "storage_gb": 50
    # }

    # Contact
    contact_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Contact person name",
    )
    contact_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Contact phone",
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Contact email",
    )

    # Relationships (commented out due to circular dependency issues)
    # Will be handled through explicit queries
    # users: Mapped[list["User"]] = relationship(...)
    # organizations: Mapped[list["Organization"]] = relationship(...)

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, code={self.code}, name={self.name})>"

    # Helper properties for registration config
    @property
    def registration_enabled(self) -> bool:
        """Check if self-registration is enabled"""
        reg_config = self.config.get("registration", {})
        return reg_config.get("enabled", True)

    @property
    def registration_require_audit(self) -> bool:
        """Check if registration requires audit"""
        reg_config = self.config.get("registration", {})
        # Support both camelCase (from frontend) and snake_case keys
        return reg_config.get("requireAudit", reg_config.get("require_audit", True))

    @property
    def registration_default_role(self) -> str:
        """Get default role for new registrations"""
        reg_config = self.config.get("registration", {})
        # Support both camelCase (from frontend) and snake_case keys
        return reg_config.get("defaultRole", reg_config.get("default_role", "user"))

    @property
    def registration_invitation(self) -> dict[str, Any]:
        """Get invitation registration config."""
        reg_config = self.config.get("registration", {})
        invitation = reg_config.get("invitation")
        return invitation if isinstance(invitation, dict) else {}
