"""S5 generation, prompt templates, and prompt optimization. No processing task."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON


class RealphotosGenerationTask(TenantBaseModel):
    """生图任务。成功只入库，不创建图片处理任务。"""

    __tablename__ = "cap_realphotos_generation_tasks"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_generation_idem",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "realphotos generation tasks"},
    )

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    positive_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    template_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requested_seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supplier_trace: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )


class RealphotosGenerationItem(TenantBaseModel):
    """生图逐张结果。失败张 asset_id 为空且不扣费。"""

    __tablename__ = "cap_realphotos_generation_items"
    __table_args__ = ({"comment": "realphotos generation items"},)

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    credits_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_height: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RealphotosPromptTemplate(TenantBaseModel):
    """提示词模板。选用不扣积分。"""

    __tablename__ = "cap_realphotos_prompt_templates"
    __table_args__ = ({"comment": "realphotos prompt templates"},)

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    positive_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scope: Mapped[str] = mapped_column(String(16), nullable=False)


class RealphotosPromptOptimization(TenantBaseModel):
    """提示词优化记录。成功扣 1，确认不再扣。"""

    __tablename__ = "cap_realphotos_prompt_optimizations"
    __table_args__ = ({"comment": "realphotos prompt optimizations"},)

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    optimized_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
