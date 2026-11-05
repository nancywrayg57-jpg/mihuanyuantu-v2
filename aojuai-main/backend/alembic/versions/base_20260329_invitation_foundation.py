"""base invitation foundation

Revision ID: base_20260329_invitation_foundation
Revises: base_20260323_speech_foundation
Create Date: 2026-03-29

Goals:
- add tenant-level invitation code table
- add invitation registration/reward snapshot table
- support delayed credit rewards and invite code purchase
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

from alembic import op

revision: str = "base_20260329_invitation_foundation"
down_revision: str | None = "base_20260323_speech_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)

    if not inspector.has_table("invite_codes"):
        op.create_table(
            "invite_codes",
            sa.Column("inviter_user_id", sa.BigInteger(), nullable=False, comment="发起邀请的用户ID"),
            sa.Column("code", sa.String(length=64), nullable=False, comment="邀请码"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active", comment="状态"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="过期时间"),
            sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1", comment="最多可使用次数"),
            sa.Column("used_count", sa.Integer(), nullable=False, server_default="0", comment="已使用次数"),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True, comment="最后一次使用时间"),
            sa.Column(
                "extra",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="{}",
                comment="扩展字段",
            ),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_invite_codes_code"),
            comment="邀请码表",
        )
        op.create_index("ix_invite_codes_tenant_id", "invite_codes", ["tenant_id"], unique=False)
        op.create_index("ix_invite_codes_inviter_user_id", "invite_codes", ["inviter_user_id"], unique=False)
        op.create_index("ix_invite_codes_code", "invite_codes", ["code"], unique=False)
        op.create_index("ix_invite_codes_status", "invite_codes", ["status"], unique=False)

    if not inspector.has_table("invite_registrations"):
        op.create_table(
            "invite_registrations",
            sa.Column("invite_code_id", sa.BigInteger(), nullable=True, comment="邀请码ID"),
            sa.Column("inviter_user_id", sa.BigInteger(), nullable=False, comment="邀请人用户ID"),
            sa.Column("invited_user_id", sa.BigInteger(), nullable=False, comment="被邀请注册用户ID"),
            sa.Column("invite_code", sa.String(length=64), nullable=True, comment="邀请码快照"),
            sa.Column("inviter_reward_credits", sa.Numeric(18, 2), nullable=False, server_default="0", comment="邀请人奖励积分快照"),
            sa.Column("invitee_reward_credits", sa.Numeric(18, 2), nullable=False, server_default="0", comment="被邀请人奖励积分快照"),
            sa.Column("reward_delay_days", sa.Integer(), nullable=False, server_default="0", comment="奖励延迟天数"),
            sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, comment="达到可发奖励时间"),
            sa.Column("inviter_reward_status", sa.String(length=20), nullable=False, server_default="pending", comment="邀请人奖励状态"),
            sa.Column("invitee_reward_status", sa.String(length=20), nullable=False, server_default="pending", comment="被邀请人奖励状态"),
            sa.Column("inviter_reward_issued_at", sa.DateTime(timezone=True), nullable=True, comment="邀请人奖励发放时间"),
            sa.Column("invitee_reward_issued_at", sa.DateTime(timezone=True), nullable=True, comment="被邀请人奖励发放时间"),
            sa.Column("inviter_credit_tx_id", sa.BigInteger(), nullable=True, comment="邀请人奖励积分流水ID"),
            sa.Column("invitee_credit_tx_id", sa.BigInteger(), nullable=True, comment="被邀请人奖励积分流水ID"),
            sa.Column(
                "extra",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="{}",
                comment="扩展字段",
            ),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
            sa.ForeignKeyConstraint(["invite_code_id"], ["invite_codes.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("invited_user_id", name="uq_invite_registrations_invited_user_id"),
            comment="邀请注册记录表",
        )
        op.create_index("ix_invite_registrations_tenant_id", "invite_registrations", ["tenant_id"], unique=False)
        op.create_index("ix_invite_registrations_invite_code_id", "invite_registrations", ["invite_code_id"], unique=False)
        op.create_index("ix_invite_registrations_inviter_user_id", "invite_registrations", ["inviter_user_id"], unique=False)
        op.create_index("ix_invite_registrations_invite_code", "invite_registrations", ["invite_code"], unique=False)
        op.create_index("ix_invite_registrations_available_at", "invite_registrations", ["available_at"], unique=False)
        op.create_index(
            "ix_invite_registrations_inviter_reward_status",
            "invite_registrations",
            ["inviter_reward_status"],
            unique=False,
        )
        op.create_index(
            "ix_invite_registrations_invitee_reward_status",
            "invite_registrations",
            ["invitee_reward_status"],
            unique=False,
        )
        op.create_index("ix_invite_registrations_inviter_credit_tx_id", "invite_registrations", ["inviter_credit_tx_id"], unique=False)
        op.create_index("ix_invite_registrations_invitee_credit_tx_id", "invite_registrations", ["invitee_credit_tx_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector: Inspector = sa.inspect(bind)

    if inspector.has_table("invite_registrations"):
        op.drop_index("ix_invite_registrations_invitee_credit_tx_id", table_name="invite_registrations")
        op.drop_index("ix_invite_registrations_inviter_credit_tx_id", table_name="invite_registrations")
        op.drop_index("ix_invite_registrations_invitee_reward_status", table_name="invite_registrations")
        op.drop_index("ix_invite_registrations_inviter_reward_status", table_name="invite_registrations")
        op.drop_index("ix_invite_registrations_available_at", table_name="invite_registrations")
        op.drop_index("ix_invite_registrations_invite_code", table_name="invite_registrations")
        op.drop_index("ix_invite_registrations_inviter_user_id", table_name="invite_registrations")
        op.drop_index("ix_invite_registrations_invite_code_id", table_name="invite_registrations")
        op.drop_index("ix_invite_registrations_tenant_id", table_name="invite_registrations")
        op.drop_table("invite_registrations")

    if inspector.has_table("invite_codes"):
        op.drop_index("ix_invite_codes_status", table_name="invite_codes")
        op.drop_index("ix_invite_codes_code", table_name="invite_codes")
        op.drop_index("ix_invite_codes_inviter_user_id", table_name="invite_codes")
        op.drop_index("ix_invite_codes_tenant_id", table_name="invite_codes")
        op.drop_table("invite_codes")
