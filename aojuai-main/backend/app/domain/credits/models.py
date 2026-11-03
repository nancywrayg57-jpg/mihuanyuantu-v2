"""
AOJU Backend - Credits Models

积分账户与流水数据模型（多租户隔离）
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Numeric

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON


class CreditAccountType(str, Enum):
    """Credit account type"""

    TENANT = "tenant"
    USER = "user"


class CreditAccountStatus(str, Enum):
    """Credit account status"""

    ACTIVE = "active"
    FROZEN = "frozen"


class CreditTransactionType(str, Enum):
    """Credit transaction type"""

    RECHARGE = "recharge"
    CONSUME = "consume"
    REFUND = "refund"
    TRANSFER = "transfer"
    BONUS = "bonus"
    ADJUST = "adjust"


class CreditTransactionDirection(str, Enum):
    """Credit transaction direction"""

    IN = "in"
    OUT = "out"


class CreditAccount(TenantBaseModel):
    """
    Credit Account Model

    - user_id 可为空：为空表示租户账户
    - account_type: tenant / user
    """

    __tablename__ = "credit_accounts"
    __table_args__ = {"comment": "积分账户表"}

    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="User ID (nullable for tenant account)",
    )

    account_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Account type: tenant | user",
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Current balance",
    )

    total_earned: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Total earned amount",
    )

    total_spent: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Total spent amount",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CreditAccountStatus.ACTIVE.value,
        server_default=CreditAccountStatus.ACTIVE.value,
        index=True,
        comment="Status: active | frozen",
    )

    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra attributes (JSONB)",
    )

    transactions: Mapped[list["CreditTransaction"]] = relationship(
        "CreditTransaction",
        back_populates="account",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<CreditAccount(id={self.id}, tenant_id={self.tenant_id}, "
            f"account_type={self.account_type}, user_id={self.user_id}, balance={self.balance})>"
        )


class CreditTransaction(TenantBaseModel):
    """Credit Transaction Model (流水)"""

    __tablename__ = "credit_transactions"
    __table_args__ = (
        Index(
            "uq_credit_transactions_tenant_idempotency_key",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
            sqlite_where=text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
        ),
        {"comment": "积分流水表"},
    )

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("credit_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Credit account ID",
    )

    transaction_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Transaction type",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        comment="Amount (positive)",
    )

    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Direction: in | out",
    )

    balance_before: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        comment="Balance before transaction",
    )

    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        comment="Balance after transaction",
    )

    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Business reference type, e.g., ai_practice, order",
    )

    reference_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Business reference ID",
    )

    idempotency_key: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        comment="幂等扣费键，同租户内唯一（为空表示不启用幂等）",
    )

    remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Remark",
    )

    operator_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Operator user ID",
    )

    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra attributes (JSONB)",
    )

    account: Mapped[CreditAccount] = relationship(
        "CreditAccount",
        back_populates="transactions",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<CreditTransaction(id={self.id}, tenant_id={self.tenant_id}, "
            f"account_id={self.account_id}, type={self.transaction_type}, "
            f"direction={self.direction}, amount={self.amount})>"
        )


class CreditPriceItem(TenantBaseModel):
    """租户级积分费率覆盖项（平台默认价来自代码内 pricebook，不落库）。

    只按模型名/件名匹配，不做模型目录、授权、凭据。语义见 credits/pricing.py。
    """

    __tablename__ = "credit_price_items"
    __table_args__ = (Index("ix_credit_price_items_type", "item_type"),)

    item_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="llm/image/tool_call/tts/asr/flat")
    match_key: Mapped[str] = mapped_column(String(200), nullable=False, comment="模型名或 glob；image 模型[/size/quality]；tool 键[@模型]")
    input_points_per_1k: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal(0), server_default="0")
    output_points_per_1k: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal(0), server_default="0")
    cached_points_per_1k: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="NULL=输入价×10%")
    cache_write_points_per_1k: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="缓存写入价；NULL=按输入价")
    points_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal(0), server_default="0")
    unit_divisor: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="tts 默认 1000 字符、asr 默认 60 秒")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    remark: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    extra: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False, default=dict, server_default=text("'{}'"))


# NOTE: credit_rules 在 nextjs-plugins 已判定为死表并停止使用；base 保留模型以免 autogenerate 判定 drop，
# 待 base 自己的迁移基线决定是否删表。
class CreditRule(TenantBaseModel):
    """Credit rule model (optional)"""

    __tablename__ = "credit_rules"
    __table_args__ = {"comment": "积分规则表"}

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Rule name",
    )

    rule_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Rule type: consume | earn | bonus",
    )

    module: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Applicable module",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        comment="Credit amount",
    )

    condition: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Trigger condition (JSONB)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
        comment="Is active",
    )
