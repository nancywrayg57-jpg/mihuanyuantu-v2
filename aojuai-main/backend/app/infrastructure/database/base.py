"""
AOJU Backend - Base Models and Mixins
"""
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base
from app.infrastructure.database.types import PortableJSON, PortablePK, PortableDateTime


class TimestampMixin:
    """Timestamp mixin for created_at and updated_at"""

    created_at: Mapped[datetime] = mapped_column(
        PortableDateTime(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        onupdate=func.now(),
        nullable=True,
    )


class SoftDeleteMixin:
    """Soft delete mixin"""

    deleted_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class TenantMixin:
    """
    Multi-tenant mixin.
    All business tables MUST inherit this mixin.
    """

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="Tenant ID",
    )


class AuditMixin:
    """Audit mixin for tracking who created/updated"""

    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Created by user ID",
    )
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Updated by user ID",
    )


class ExtraMixin:
    """JSON extra field for dynamic attributes（PostgreSQL 落 JSONB，SQLite 落 JSON）"""

    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra attributes (JSON)",
    )


class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    """
    Base model with common fields.
    Use this for tables that don't need multi-tenant isolation.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        PortablePK,
        primary_key=True,
        autoincrement=True,
    )


class TenantBaseModel(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """
    Base model for multi-tenant tables.
    Use this for all business tables that need tenant isolation.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        PortablePK,
        primary_key=True,
        autoincrement=True,
    )


class AssociationBaseModel(Base, TenantMixin):
    """
    Base model for association/junction tables (many-to-many).
    Use this for tables with composite primary keys.
    Does NOT include id, timestamps, or soft delete.
    """

    __abstract__ = True
