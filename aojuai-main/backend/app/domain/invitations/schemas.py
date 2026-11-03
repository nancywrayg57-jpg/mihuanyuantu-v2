"""
AOJU Backend - Invitation Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.tenant_config_namespaces import get_tenant_config_namespace, safe_tenant_config_dict


class InvitationConfig(BaseModel):
    """Invitation registration configuration."""

    enabled: bool = Field(False, description="是否启用邀请注册")
    inviter_reward_credits: int = Field(0, alias="inviterRewardCredits", ge=0, description="邀请人奖励积分")
    invitee_reward_credits: int = Field(0, alias="inviteeRewardCredits", ge=0, description="被邀请人奖励积分")
    reward_delay_days: int = Field(0, alias="rewardDelayDays", ge=0, le=3650, description="奖励延迟天数")
    max_invites_per_user: int = Field(50, alias="maxInvitesPerUser", ge=0, description="单个用户最大邀请人数")
    invite_code_cost_credits: int = Field(
        0,
        alias="inviteCodeCostCredits",
        ge=0,
        description="生成邀请码扣减积分",
    )

    model_config = ConfigDict(populate_by_name=True)


class InviteCodeItem(BaseModel):
    id: int
    invite_code: str = Field(alias="inviteCode")
    status: str
    expires_at: datetime | None = Field(None, alias="expiresAt")
    max_uses: int = Field(alias="maxUses")
    used_count: int = Field(alias="usedCount")
    remaining_uses: int = Field(alias="remainingUses")
    cost_credits: int = Field(alias="costCredits")
    register_path: str = Field(alias="registerPath")
    created_at: datetime | None = Field(None, alias="createdAt")
    last_used_at: datetime | None = Field(None, alias="lastUsedAt")
    invited_user_id: int | None = Field(None, alias="invitedUserId")
    invited_username: str | None = Field(None, alias="invitedUsername")
    invited_nickname: str | None = Field(None, alias="invitedNickname")
    invited_at: datetime | None = Field(None, alias="invitedAt")
    can_recycle: bool = Field(False, alias="canRecycle")
    recycled_at: datetime | None = Field(None, alias="recycledAt")
    refunded_credits: int = Field(0, alias="refundedCredits")
    refunded_at: datetime | None = Field(None, alias="refundedAt")

    model_config = ConfigDict(populate_by_name=True)


class InviteCodeIssueResponse(InviteCodeItem):
    expires_in: int = Field(alias="expiresIn")
    tenant_code: str = Field(alias="tenantCode")
    tenant_name: str = Field(alias="tenantName")

    model_config = ConfigDict(populate_by_name=True)


class InvitationSummaryResponse(BaseModel):
    config: InvitationConfig = Field(default_factory=InvitationConfig)
    user_can_invite: bool = Field(alias="userCanInvite")
    used_invite_count: int = Field(alias="usedInviteCount")
    active_reserved_invite_quota: int = Field(alias="activeReservedInviteQuota")
    remaining_invite_quota: int = Field(alias="remainingInviteQuota")
    total_related_records: int = Field(alias="totalRelatedRecords")
    issued_inviter_reward_credits: str = Field(alias="issuedInviterRewardCredits")
    issued_invitee_reward_credits: str = Field(alias="issuedInviteeRewardCredits")
    pending_inviter_reward_credits: str = Field(alias="pendingInviterRewardCredits")
    pending_invitee_reward_credits: str = Field(alias="pendingInviteeRewardCredits")
    codes: list[InviteCodeItem] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


InvitationRelation = Literal["all", "sent", "received"]


class InvitationRecordItem(BaseModel):
    id: int
    relation: str | None = None
    invite_code: str | None = Field(None, alias="inviteCode")
    invite_code_status: str | None = Field(None, alias="inviteCodeStatus")
    inviter_user_id: int | None = Field(None, alias="inviterUserId")
    inviter_username: str | None = Field(None, alias="inviterUsername")
    inviter_nickname: str | None = Field(None, alias="inviterNickname")
    inviter_email: str | None = Field(None, alias="inviterEmail")
    inviter_phone: str | None = Field(None, alias="inviterPhone")
    inviter_user_status: int | None = Field(None, alias="inviterUserStatus")
    inviter_register_source: str | None = Field(None, alias="inviterRegisterSource")
    inviter_created_at: datetime | None = Field(None, alias="inviterCreatedAt")
    invited_user_id: int | None = Field(None, alias="invitedUserId")
    invited_username: str | None = Field(None, alias="invitedUsername")
    invited_nickname: str | None = Field(None, alias="invitedNickname")
    invited_email: str | None = Field(None, alias="invitedEmail")
    invited_phone: str | None = Field(None, alias="invitedPhone")
    invited_user_status: int | None = Field(None, alias="invitedUserStatus")
    invited_register_source: str | None = Field(None, alias="invitedRegisterSource")
    invited_created_at: datetime | None = Field(None, alias="invitedCreatedAt")
    inviter_reward_credits: str = Field(alias="inviterRewardCredits")
    invitee_reward_credits: str = Field(alias="inviteeRewardCredits")
    reward_delay_days: int = Field(alias="rewardDelayDays")
    available_at: datetime | None = Field(None, alias="availableAt")
    inviter_reward_status: str = Field(alias="inviterRewardStatus")
    invitee_reward_status: str = Field(alias="inviteeRewardStatus")
    inviter_reward_issued_at: datetime | None = Field(None, alias="inviterRewardIssuedAt")
    invitee_reward_issued_at: datetime | None = Field(None, alias="inviteeRewardIssuedAt")
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


def get_invitation_config(raw_config: Any) -> InvitationConfig:
    """Read invitation config from tenant config safely."""

    source = getattr(raw_config, "config", raw_config)
    config = safe_tenant_config_dict(source)
    registration = get_tenant_config_namespace(config, ("registration",))
    invitation = safe_tenant_config_dict(registration.get("invitation"))
    return InvitationConfig.model_validate(invitation or {})
