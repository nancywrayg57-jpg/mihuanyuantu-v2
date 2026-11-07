"""Platform supplier contracts. Credential values are never stored here."""

from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON


class RealphotosProviderContract(TenantBaseModel):
    """One enabled configuration per duty. No raw API key column."""

    __tablename__ = "cap_realphotos_provider_contracts"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_provider_duty",
            "duty",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos supplier contracts without secrets"},
    )

    duty: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    config_version: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(200), nullable=False)
    capabilities: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gap_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
