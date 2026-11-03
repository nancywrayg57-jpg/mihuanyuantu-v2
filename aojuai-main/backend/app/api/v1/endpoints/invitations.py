"""
AOJU Backend - Invitation Endpoints
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.api.deps import CurrentTenantAdmin, CurrentUser, DBSession, TenantCtx
from app.core.exceptions import BusinessError
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.auth.service import TenantService
from app.domain.invitations.schemas import InviteCodeIssueResponse, InvitationRecordItem, InvitationRelation, InvitationSummaryResponse
from app.domain.invitations.service import InvitationService

router = APIRouter()


class InvitationRecordQuery(BaseModel):
    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        20,
        ge=1,
        le=100,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    relation: InvitationRelation = Field("all")
    keyword: str | None = Field(
        default=None,
        validation_alias=AliasChoices("keyword", "q"),
    )
    invite_code: str | None = Field(
        default=None,
        validation_alias=AliasChoices("inviteCode", "invite_code"),
    )
    invite_code_status: str | None = Field(
        default=None,
        validation_alias=AliasChoices("inviteCodeStatus", "invite_code_status"),
    )
    inviter_keyword: str | None = Field(
        default=None,
        validation_alias=AliasChoices("inviterKeyword", "inviter_keyword"),
    )
    inviter_user_status: int | None = Field(
        default=None,
        validation_alias=AliasChoices("inviterUserStatus", "inviter_user_status"),
    )
    inviter_register_source: str | None = Field(
        default=None,
        validation_alias=AliasChoices("inviterRegisterSource", "inviter_register_source"),
    )
    invited_keyword: str | None = Field(
        default=None,
        validation_alias=AliasChoices("invitedKeyword", "invited_keyword"),
    )
    invited_user_status: int | None = Field(
        default=None,
        validation_alias=AliasChoices("invitedUserStatus", "invited_user_status"),
    )
    invited_register_source: str | None = Field(
        default=None,
        validation_alias=AliasChoices("invitedRegisterSource", "invited_register_source"),
    )
    inviter_reward_status: str | None = Field(
        default=None,
        validation_alias=AliasChoices("inviterRewardStatus", "inviter_reward_status"),
    )
    invitee_reward_status: str | None = Field(
        default=None,
        validation_alias=AliasChoices("inviteeRewardStatus", "invitee_reward_status"),
    )

    model_config = ConfigDict(populate_by_name=True)


@router.post("/my/code", response_model=ResponseBase[InviteCodeIssueResponse])
async def generate_my_invite_code(
    current_user: CurrentUser,
    db: DBSession,
    expires_days: int = 7,
) -> dict[str, Any]:
    tenant = await TenantService(db).get_by_id(current_user.tenant_id)
    if not tenant:
        raise BusinessError(message="Tenant not found")

    service = InvitationService(db)
    invite_code = await service.generate_code(
        tenant=tenant,
        inviter_user=current_user,
        expires_days=expires_days,
    )
    return SuccessResponse(
        data=service.to_code_response(invite_code, tenant=tenant, expires_in=max(1, min(int(expires_days or 7), 365))),
        message="邀请码已生成",
    )


@router.post("/my/codes/{invite_code_id}/recycle", response_model=ResponseBase[InviteCodeIssueResponse])
async def recycle_my_invite_code(
    invite_code_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    tenant = await TenantService(db).get_by_id(current_user.tenant_id)
    if not tenant:
        raise BusinessError(message="Tenant not found")

    service = InvitationService(db)
    invite_code = await service.recycle_code(
        tenant=tenant,
        inviter_user=current_user,
        invite_code_id=invite_code_id,
    )
    return SuccessResponse(
        data=service.to_code_response(invite_code, tenant=tenant),
        message="邀请码已回收",
    )


@router.get("/my/summary", response_model=ResponseBase[InvitationSummaryResponse])
async def get_my_invitation_summary(
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    tenant = await TenantService(db).get_by_id(current_user.tenant_id)
    if not tenant:
        raise BusinessError(message="Tenant not found")

    service = InvitationService(db)
    await service.process_due_rewards(tenant_id=current_user.tenant_id, user_id=current_user.id)
    return SuccessResponse(data=await service.build_user_summary(tenant=tenant, user_id=current_user.id))


@router.get("/my/records", response_model=ResponseBase[PageResponse[InvitationRecordItem]])
async def list_my_invitation_records(
    current_user: CurrentUser,
    db: DBSession,
    query: InvitationRecordQuery = Depends(),
) -> dict[str, Any]:
    service = InvitationService(db)
    await service.process_due_rewards(tenant_id=current_user.tenant_id, user_id=current_user.id)
    records, total = await service.list_records(
        tenant_id=current_user.tenant_id,
        page=query.page,
        page_size=query.page_size,
        user_id=current_user.id,
        relation=query.relation,
        keyword=query.keyword,
        invite_code=query.invite_code,
        invite_code_status=query.invite_code_status,
        inviter_keyword=query.inviter_keyword,
        inviter_user_status=query.inviter_user_status,
        inviter_register_source=query.inviter_register_source,
        invited_keyword=query.invited_keyword,
        invited_user_status=query.invited_user_status,
        invited_register_source=query.invited_register_source,
        inviter_reward_status=query.inviter_reward_status,
        invitee_reward_status=query.invitee_reward_status,
    )
    return SuccessResponse(
        data={
            "list": records,
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/admin/records", response_model=ResponseBase[PageResponse[InvitationRecordItem]])
async def list_admin_invitation_records(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: InvitationRecordQuery = Depends(),
) -> dict[str, Any]:
    _ = current_user
    service = InvitationService(db)
    await service.process_due_rewards(tenant_id=tenant_ctx.tenant_id)
    records, total = await service.list_records(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        keyword=query.keyword,
        invite_code=query.invite_code,
        invite_code_status=query.invite_code_status,
        inviter_keyword=query.inviter_keyword,
        inviter_user_status=query.inviter_user_status,
        inviter_register_source=query.inviter_register_source,
        invited_keyword=query.invited_keyword,
        invited_user_status=query.invited_user_status,
        invited_register_source=query.invited_register_source,
        inviter_reward_status=query.inviter_reward_status,
        invitee_reward_status=query.invitee_reward_status,
    )
    return SuccessResponse(
        data={
            "list": records,
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )
