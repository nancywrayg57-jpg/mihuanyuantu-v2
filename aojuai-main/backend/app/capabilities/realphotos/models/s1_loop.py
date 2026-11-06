"""S1 single-image loop tables (physical prefix cap_realphotos_)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableDateTime, PortableJSON


class RealphotosAsset(TenantBaseModel):
    """资源原图。长期保留，直到软删。"""

    __tablename__ = "cap_realphotos_assets"
    __table_args__ = (
        Index("ix_cap_realphotos_assets_tenant_owner", "tenant_id", "owner_account_id"),
        {"comment": "realphotos source assets"},
    )

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="local_upload")


class RealphotosBatch(TenantBaseModel):
    """S1 批次固定 1 张。"""

    __tablename__ = "cap_realphotos_batches"
    __table_args__ = ({"comment": "realphotos processing batches"},)

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False)
    preset_code: Mapped[str] = mapped_column(String(64), nullable=False)


class RealphotosTaskChain(TenantBaseModel):
    """单张链。S1 不创建自动重做轮次。"""

    __tablename__ = "cap_realphotos_task_chains"
    __table_args__ = ({"comment": "realphotos task chains"},)

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class RealphotosImageTask(TenantBaseModel):
    """图片处理任务。状态名对齐 SM-001 的 S1 可达子集。"""

    __tablename__ = "cap_realphotos_image_tasks"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_image_tasks_idem",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_cap_realphotos_image_tasks_asset", "tenant_id", "asset_id", "status"),
        {"comment": "realphotos image processing tasks"},
    )

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    preset_code: Mapped[str] = mapped_column(String(64), nullable=False)
    preset_snapshot: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    pre_review_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="pass")
    detection_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="pass")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    output_object_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_expires_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    output_byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    failure_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    credit_disposition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pipeline_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="stub-s1", server_default="stub-s1"
    )


class RealphotosTaskSnapshot(TenantBaseModel):
    """提交时预设快照副本。"""

    __tablename__ = "cap_realphotos_task_snapshots"
    __table_args__ = ({"comment": "realphotos preset snapshots"},)

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    snapshot: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )


class RealphotosStageResult(TenantBaseModel):
    """五层占位阶段记录。不是真实五层验收。"""

    __tablename__ = "cap_realphotos_stage_results"
    __table_args__ = ({"comment": "realphotos placeholder stage results"},)

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    stage_code: Mapped[str] = mapped_column(String(8), nullable=False)
    stage_status: Mapped[str] = mapped_column(String(32), nullable=False)


class RealphotosDetectionResult(TenantBaseModel):
    """规则替身报告。键名对齐 Gemini 方案。"""

    __tablename__ = "cap_realphotos_detection_results"
    __table_args__ = ({"comment": "realphotos fixture detection results"},)

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    noise: Mapped[int] = mapped_column(Integer, nullable=False)
    depth_of_field: Mapped[int] = mapped_column(Integer, nullable=False)
    lighting: Mapped[int] = mapped_column(Integer, nullable=False)
    color_realism: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_realism: Mapped[int] = mapped_column(Integer, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    detector: Mapped[str] = mapped_column(
        String(32), nullable=False, default="fixture", server_default="fixture"
    )


class RealphotosCreditReservation(TenantBaseModel):
    """单张冻结。state: reserved | consumed | released | held。"""

    __tablename__ = "cap_realphotos_credit_reservations"
    __table_args__ = ({"comment": "realphotos credit reservations"},)

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    operator_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class RealphotosRechargeOrder(TenantBaseModel):
    """人工充值订单。无跳转支付。"""

    __tablename__ = "cap_realphotos_recharge_orders"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_recharge_idem",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos manual recharge orders"},
    )

    requester_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tier_yuan: Mapped[int] = mapped_column(Integer, nullable=False)
    credit_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_formula: Mapped[str] = mapped_column(String(80), nullable=False)
    voucher_note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    confirmed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class RealphotosInboxMessage(TenantBaseModel):
    """站内消息。按接收账号隔离，自创建起 30 天。"""

    __tablename__ = "cap_realphotos_inbox_messages"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_inbox_event",
            "tenant_id",
            "event_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos inbox messages"},
    )

    recipient_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(PortableDateTime(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
