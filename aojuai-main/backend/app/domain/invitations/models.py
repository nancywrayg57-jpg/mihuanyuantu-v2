"""
AOJU Backend - Invitation Models
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, text
from app.infrastructure.database.types import PortableJSON, PortableDateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Numeric

from app.infrastructure.database.base import TenantBaseModel


class InviteCodeStatus(str, Enum):
    """Invitation code lifecycle status."""

    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"
    DISABLED = "disabled"


class InviteRewardStatus(str, Enum):
    """Per-side reward issuing status."""

    PENDING = "pending"
    ISSUED = "issued"
    SKIPPED = "skipped"


class InviteCode(TenantBaseModel):
    """Invitation code / registration link."""

    __tablename__ = "invite_codes"
    __table_args__ = (
        Index(
            "uq_invite_codes_code",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "邀请码表"},
    )

    inviter_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="发起邀请的用户ID",
    )

    code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="邀请码",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InviteCodeStatus.ACTIVE.value,
        server_default=InviteCodeStatus.ACTIVE.value,
        index=True,
        comment="状态 active|exhausted|expired|disabled",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="过期时间",
    )

    max_uses: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="最多可使用次数",
    )

    used_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="已使用次数",
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="最后一次使用时间",
    )

    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="扩展字段",
    )


class InviteRegistration(TenantBaseModel):
    """Invitation registration record with reward snapshot."""

    __tablename__ = "invite_registrations"
    __table_args__ = (
        Index(
            "uq_invite_registrations_invited_user_id",
            "invited_user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"comment": "邀请注册记录表"},
    )

    invite_code_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("invite_codes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="邀请码ID",
    )

    inviter_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="邀请人用户ID",
    )

    invited_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="被邀请注册用户ID",
    )

    invite_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="邀请码快照",
    )

    inviter_reward_credits: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="邀请人奖励积分快照",
    )

    invitee_reward_credits: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="被邀请人奖励积分快照",
    )

    reward_delay_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="奖励发放延迟天数",
    )

    available_at: Mapped[datetime] = mapped_column(
        PortableDateTime(),
        nullable=False,
        index=True,
        comment="达到可发奖励时间",
    )

    inviter_reward_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InviteRewardStatus.PENDING.value,
        server_default=InviteRewardStatus.PENDING.value,
        index=True,
        comment="邀请人奖励状态 pending|issued|skipped",
    )

    invitee_reward_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InviteRewardStatus.PENDING.value,
        server_default=InviteRewardStatus.PENDING.value,
        index=True,
        comment="被邀请人奖励状态 pending|issued|skipped",
    )

    inviter_reward_issued_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="邀请人奖励发放时间",
    )

    invitee_reward_issued_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(),
        nullable=True,
        comment="被邀请人奖励发放时间",
    )

    inviter_credit_tx_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="邀请人奖励积分流水ID",
    )

    invitee_credit_tx_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="被邀请人奖励积分流水ID",
    )

    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="扩展字段",
    )
