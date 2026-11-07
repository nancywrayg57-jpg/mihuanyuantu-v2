"""Tenant-scoped merchant profile binding."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel


class RealphotosMerchantProfile(TenantBaseModel):
    """一租户多账号绑定；预审冻结独立于登录锁定。"""

    __tablename__ = "cap_realphotos_merchant_profiles"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_merchant_profiles_tenant_user",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos merchant profiles"},
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pre_review_frozen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    copy_latch_batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    copy_latch_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
