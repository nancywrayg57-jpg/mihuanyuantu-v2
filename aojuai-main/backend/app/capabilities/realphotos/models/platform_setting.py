"""Platform-wide key/value settings. Not the supplier secret store."""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel


class RealphotosPlatformSetting(TenantBaseModel):
    """One live row per setting_key. Lookup is by key, not by merchant tenant."""

    __tablename__ = "cap_realphotos_platform_settings"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_platform_setting_key",
            "setting_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos platform key-value settings"},
    )

    setting_key: Mapped[str] = mapped_column(String(64), nullable=False)
    setting_value: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
