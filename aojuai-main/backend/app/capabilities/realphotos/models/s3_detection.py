"""S3 redo settings and immutable per-chain snapshots."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel


class RealphotosRedoSetting(TenantBaseModel):
    """商家自动重做设置。提交任务时再复制为链快照。"""

    __tablename__ = "cap_realphotos_redo_settings"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_redo_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos auto redo settings"},
    )

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    extra_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RealphotosChainPolicy(TenantBaseModel):
    """提交时不可变的自动重做快照。"""

    __tablename__ = "cap_realphotos_chain_policies"
    __table_args__ = ({"comment": "realphotos chain redo snapshots"},)

    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="submit", server_default="submit")
