"""S6 pre-review audit, tickets, account logs, and preset overrides.

No supplier client lives in these tables. Fixture rows are in-process only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON


class RealphotosContentReview(TenantBaseModel):
    """内容预审审计。不确定的 passed 必须为 false。"""

    __tablename__ = "cap_realphotos_content_reviews"
    __table_args__ = ({"comment": "realphotos content review audit"},)

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    subject: Mapped[str] = mapped_column(String(16), nullable=False)
    image_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    counts_for_streak: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RealphotosImageLock(TenantBaseModel):
    __tablename__ = "cap_realphotos_image_locks"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_image_lock",
            "tenant_id",
            "owner_account_id",
            "image_identity",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos locked image identities"},
    )

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    image_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)


class RealphotosReviewStreak(TenantBaseModel):
    __tablename__ = "cap_realphotos_review_streaks"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_review_streak_user",
            "tenant_id",
            "owner_account_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "consecutive distinct content-review failures"},
    )

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    identities: Mapped[list] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default="[]"
    )


class RealphotosSupportTicket(TenantBaseModel):
    __tablename__ = "cap_realphotos_support_tickets"
    __table_args__ = ({"comment": "realphotos tech-support tickets"},)

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ticket_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # BROWSER-E2E-FIX F2 / FR-022: terminal state audit
    resolved_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolution_outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="")


class RealphotosAccountLog(TenantBaseModel):
    """用户账号成功变更。没有密码列。"""

    __tablename__ = "cap_realphotos_account_logs"
    __table_args__ = ({"comment": "realphotos account change log"},)

    operator_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    before_state: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    after_state: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="success")


class RealphotosDevicePreset(TenantBaseModel):
    __tablename__ = "cap_realphotos_device_presets"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_device_preset_code",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos device preset overrides and admin presets"},
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)
    brand: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    iso: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    shutter: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    aperture: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    focal_length: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    gps_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="admin")
    # PRODUCT-GAP A3 / A7 — prompts + MakerNote (admin 2026-11-07 authorized write).
    ai_positive_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_negative_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    maker_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    legacy_source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    legacy_template_ref: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    legacy_visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    legacy_review_bucket: Mapped[str] = mapped_column(String(64), nullable=False, default="")


class RealphotosPresetVersion(TenantBaseModel):
    __tablename__ = "cap_realphotos_preset_versions"
    __table_args__ = ({"comment": "preset version snapshots"},)

    preset_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
