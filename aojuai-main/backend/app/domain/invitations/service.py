"""
AOJU Backend - Invitation Service
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import BusinessError
from app.core.logger import get_logger
from app.domain.auth.models import Tenant
from app.domain.credits.service import CreditService
from app.domain.invitations.models import InviteCode, InviteCodeStatus, InviteRegistration, InviteRewardStatus
from app.domain.invitations.schemas import InvitationConfig, InvitationRelation, get_invitation_config
from app.domain.users.models import User, UserStatus
from app.infrastructure.database.portable_sql import escalate_to_write_lock
from app.infrastructure.database.types import greatest_of
from app.infrastructure.repository import RepositoryBase

logger = get_logger(__name__)

INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class InvitationService:
    """Invitation registration business service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.code_repo = RepositoryBase(db, InviteCode)
        self.registration_repo = RepositoryBase(db, InviteRegistration)
        self.tenant_repo = RepositoryBase(db, Tenant)
        self.user_repo = RepositoryBase(db, User)

    @staticmethod
    def _decimal_str(value: Decimal | int | None) -> str:
        if value is None:
            return "0"
        return str(value if isinstance(value, Decimal) else Decimal(str(value)))

    @staticmethod
    def _build_register_path(code: str) -> str:
        return f"/register?invite={quote(str(code).strip())}"

    @staticmethod
    def _normalize_query_str(value: str | None) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _build_user_keyword_filter(user_alias: Any, keyword: str) -> Any:
        like_keyword = f"%{keyword}%"
        conditions = [
            user_alias.username.ilike(like_keyword),
            user_alias.nickname.ilike(like_keyword),
            user_alias.email.ilike(like_keyword),
            user_alias.phone.ilike(like_keyword),
        ]
        if keyword.isdigit():
            conditions.append(user_alias.id == int(keyword))
        return or_(*conditions)

    async def _sync_code_status(self, invite_code: InviteCode) -> InviteCode:
        if invite_code.status == InviteCodeStatus.DISABLED.value:
            return invite_code

        now = datetime.now(UTC)
        next_status = invite_code.status
        if invite_code.expires_at and invite_code.expires_at <= now:
            next_status = InviteCodeStatus.EXPIRED.value
        elif int(invite_code.used_count or 0) >= int(invite_code.max_uses or 0):
            next_status = InviteCodeStatus.EXHAUSTED.value
        else:
            next_status = InviteCodeStatus.ACTIVE.value

        if invite_code.status != next_status:
            invite_code.status = next_status
            await self.db.flush()
        return invite_code

    async def _generate_unique_code(self, *, length: int = 10) -> str:
        for _ in range(10):
            candidate = "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(length))
            existing = await self.code_repo.get_one(where=[InviteCode.code == candidate], raise_not_found=False)
            if not existing:
                return candidate
        raise BusinessError(message="生成邀请码失败，请稍后重试")

    def get_config(self, tenant: Tenant | dict[str, Any]) -> InvitationConfig:
        return get_invitation_config(getattr(tenant, "config", tenant))

    async def get_code_by_value(self, code: str, *, for_update: bool = False) -> InviteCode | None:
        normalized = str(code or "").strip()
        if not normalized:
            return None

        stmt = select(InviteCode).where(
            InviteCode.code == normalized,
            InviteCode.deleted_at.is_(None),
        )
        if for_update:
            stmt = stmt.with_for_update()
            await escalate_to_write_lock(self.db)

        result = await self.db.execute(stmt)
        invite_code = result.scalar_one_or_none()
        if not invite_code:
            return None

        return await self._sync_code_status(invite_code)

    async def resolve_code_context(
        self,
        code: str,
        *,
        for_update: bool = False,
    ) -> tuple[InviteCode, Tenant, User] | None:
        invite_code = await self.get_code_by_value(code, for_update=for_update)
        if not invite_code or invite_code.status != InviteCodeStatus.ACTIVE.value:
            return None

        tenant = await self.tenant_repo.get_by_id(invite_code.tenant_id, raise_not_found=False)
        if not tenant or not tenant.is_active:
            return None

        inviter = await self.user_repo.get_one(
            where=[
                User.id == invite_code.inviter_user_id,
                User.tenant_id == invite_code.tenant_id,
            ],
            raise_not_found=False,
        )
        if not inviter:
            return None

        return invite_code, tenant, inviter

    async def count_invited_users(self, *, tenant_id: int, inviter_user_id: int) -> int:
        stmt = select(func.count(InviteRegistration.id)).where(
            InviteRegistration.tenant_id == tenant_id,
            InviteRegistration.inviter_user_id == inviter_user_id,
            InviteRegistration.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def count_active_reserved_uses(self, *, tenant_id: int, inviter_user_id: int) -> int:
        now = datetime.now(UTC)
        remaining_uses_expr = greatest_of(InviteCode.max_uses - InviteCode.used_count, 0)
        stmt = select(func.coalesce(func.sum(remaining_uses_expr), 0)).where(
            InviteCode.tenant_id == tenant_id,
            InviteCode.inviter_user_id == inviter_user_id,
            InviteCode.deleted_at.is_(None),
            InviteCode.status != InviteCodeStatus.DISABLED.value,
            remaining_uses_expr > 0,
            or_(InviteCode.expires_at.is_(None), InviteCode.expires_at > now),
        )
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def _count_related_records(self, *, tenant_id: int, user_id: int) -> int:
        stmt = select(func.count(InviteRegistration.id)).where(
            InviteRegistration.tenant_id == tenant_id,
            InviteRegistration.deleted_at.is_(None),
            or_(
                InviteRegistration.inviter_user_id == user_id,
                InviteRegistration.invited_user_id == user_id,
            ),
        )
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def _sum_reward_amount(
        self,
        *,
        tenant_id: int,
        user_id: int,
        side: str,
        status: str,
    ) -> Decimal:
        if side == "inviter":
            column = InviteRegistration.inviter_reward_credits
            user_column = InviteRegistration.inviter_user_id
            status_column = InviteRegistration.inviter_reward_status
        else:
            column = InviteRegistration.invitee_reward_credits
            user_column = InviteRegistration.invited_user_id
            status_column = InviteRegistration.invitee_reward_status

        stmt = select(func.coalesce(func.sum(column), 0)).where(
            InviteRegistration.tenant_id == tenant_id,
            InviteRegistration.deleted_at.is_(None),
            user_column == user_id,
            status_column == status,
        )
        result = await self.db.execute(stmt)
        value = result.scalar()
        return value if isinstance(value, Decimal) else Decimal(str(value or 0))

    def to_code_response(
        self,
        invite_code: InviteCode,
        *,
        tenant: Tenant,
        expires_in: int | None = None,
        usage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        extra = invite_code.extra or {}
        usage_payload = usage or {}
        can_recycle = (
            int(invite_code.used_count or 0) <= 0
            and not extra.get("refundTxId")
            and invite_code.status != InviteCodeStatus.DISABLED.value
        )
        return {
            "id": invite_code.id,
            "inviteCode": invite_code.code,
            "status": invite_code.status,
            "expiresAt": invite_code.expires_at.isoformat() if invite_code.expires_at else None,
            "maxUses": int(invite_code.max_uses or 0),
            "usedCount": int(invite_code.used_count or 0),
            "remainingUses": max(int(invite_code.max_uses or 0) - int(invite_code.used_count or 0), 0),
            "costCredits": int(extra.get("costCredits") or 0),
            "registerPath": self._build_register_path(invite_code.code),
            "createdAt": invite_code.created_at.isoformat() if invite_code.created_at else None,
            "lastUsedAt": invite_code.last_used_at.isoformat() if invite_code.last_used_at else None,
            "invitedUserId": usage_payload.get("invitedUserId"),
            "invitedUsername": usage_payload.get("invitedUsername"),
            "invitedNickname": usage_payload.get("invitedNickname"),
            "invitedAt": usage_payload.get("invitedAt"),
            "canRecycle": can_recycle,
            "recycledAt": extra.get("recycledAt"),
            "refundedCredits": int(extra.get("refundedCredits") or 0),
            "refundedAt": extra.get("refundedAt"),
            "tenantCode": tenant.code,
            "tenantName": tenant.name,
            "expiresIn": expires_in if expires_in is not None else int(extra.get("expiresIn") or 0),
        }

    async def list_user_codes(
        self,
        *,
        tenant: Tenant,
        user_id: int,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(InviteCode)
            .where(
                InviteCode.tenant_id == tenant.id,
                InviteCode.inviter_user_id == user_id,
                InviteCode.deleted_at.is_(None),
            )
            .order_by(InviteCode.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        codes = list(result.scalars().all())

        usage_by_code_id: dict[int, dict[str, Any]] = {}
        code_ids = [int(code.id) for code in codes if getattr(code, "id", None) is not None]
        if code_ids:
            invited_alias = aliased(User)
            usage_stmt = (
                select(
                    InviteRegistration.invite_code_id.label("invite_code_id"),
                    InviteRegistration.invited_user_id.label("invited_user_id"),
                    InviteRegistration.created_at.label("invited_at"),
                    invited_alias.username.label("invited_username"),
                    invited_alias.nickname.label("invited_nickname"),
                )
                .select_from(InviteRegistration)
                .outerjoin(
                    invited_alias,
                    and_(
                        invited_alias.id == InviteRegistration.invited_user_id,
                        invited_alias.deleted_at.is_(None),
                    ),
                )
                .where(
                    InviteRegistration.tenant_id == tenant.id,
                    InviteRegistration.deleted_at.is_(None),
                    InviteRegistration.invite_code_id.in_(code_ids),
                )
                .order_by(InviteRegistration.id.desc())
            )
            usage_result = await self.db.execute(usage_stmt)
            for row in usage_result.all():
                invite_code_id = row._mapping.get("invite_code_id")
                if invite_code_id is None:
                    continue
                normalized_code_id = int(invite_code_id)
                if normalized_code_id in usage_by_code_id:
                    continue
                usage_by_code_id[normalized_code_id] = {
                    "invitedUserId": row._mapping.get("invited_user_id"),
                    "invitedUsername": row._mapping.get("invited_username"),
                    "invitedNickname": row._mapping.get("invited_nickname"),
                    "invitedAt": (
                        row._mapping.get("invited_at").isoformat()
                        if row._mapping.get("invited_at")
                        else None
                    ),
                }

        payload: list[dict[str, Any]] = []
        for invite_code in codes:
            await self._sync_code_status(invite_code)
            expires_in = int((invite_code.extra or {}).get("expiresIn") or 0)
            payload.append(
                self.to_code_response(
                    invite_code,
                    tenant=tenant,
                    expires_in=expires_in,
                    usage=usage_by_code_id.get(int(invite_code.id)),
                )
            )
        return payload

    async def build_user_summary(self, *, tenant: Tenant, user_id: int) -> dict[str, Any]:
        config = self.get_config(tenant)
        used_invite_count = await self.count_invited_users(tenant_id=tenant.id, inviter_user_id=user_id)
        active_reserved_invite_quota = await self.count_active_reserved_uses(
            tenant_id=tenant.id,
            inviter_user_id=user_id,
        )
        remaining_invite_quota = max(
            int(config.max_invites_per_user or 0) - used_invite_count - active_reserved_invite_quota,
            0,
        )

        return {
            "config": config.model_dump(by_alias=True),
            "userCanInvite": bool(
                config.enabled and remaining_invite_quota > 0
            ),
            "usedInviteCount": used_invite_count,
            "activeReservedInviteQuota": active_reserved_invite_quota,
            "remainingInviteQuota": remaining_invite_quota,
            "totalRelatedRecords": await self._count_related_records(tenant_id=tenant.id, user_id=user_id),
            "issuedInviterRewardCredits": self._decimal_str(
                await self._sum_reward_amount(
                    tenant_id=tenant.id,
                    user_id=user_id,
                    side="inviter",
                    status=InviteRewardStatus.ISSUED.value,
                )
            ),
            "issuedInviteeRewardCredits": self._decimal_str(
                await self._sum_reward_amount(
                    tenant_id=tenant.id,
                    user_id=user_id,
                    side="invitee",
                    status=InviteRewardStatus.ISSUED.value,
                )
            ),
            "pendingInviterRewardCredits": self._decimal_str(
                await self._sum_reward_amount(
                    tenant_id=tenant.id,
                    user_id=user_id,
                    side="inviter",
                    status=InviteRewardStatus.PENDING.value,
                )
            ),
            "pendingInviteeRewardCredits": self._decimal_str(
                await self._sum_reward_amount(
                    tenant_id=tenant.id,
                    user_id=user_id,
                    side="invitee",
                    status=InviteRewardStatus.PENDING.value,
                )
            ),
            "codes": await self.list_user_codes(tenant=tenant, user_id=user_id),
        }

    async def generate_code(
        self,
        *,
        tenant: Tenant,
        inviter_user: User,
        expires_days: int = 7,
    ) -> InviteCode:
        config = self.get_config(tenant)
        if not config.enabled:
            raise BusinessError(message="当前租户未启用邀请注册")

        used_invite_count = await self.count_invited_users(tenant_id=tenant.id, inviter_user_id=inviter_user.id)
        active_reserved_invite_quota = await self.count_active_reserved_uses(
            tenant_id=tenant.id,
            inviter_user_id=inviter_user.id,
        )
        remaining_invite_quota = max(
            int(config.max_invites_per_user or 0) - used_invite_count - active_reserved_invite_quota,
            0,
        )
        if remaining_invite_quota <= 0:
            raise BusinessError(message="当前账号的邀请名额已用完")

        normalized_expires_days = max(1, min(int(expires_days or 7), 365))
        purchase_tx_id: int | None = None

        if int(config.invite_code_cost_credits or 0) > 0:
            credit_service = CreditService(self.db)
            account = await credit_service.get_user_account(
                tenant_id=tenant.id,
                user_id=inviter_user.id,
            )
            if not account:
                account = await credit_service.init_user_account(
                    tenant_id=tenant.id,
                    user_id=inviter_user.id,
                    operator_id=inviter_user.id,
                )

            tx = await credit_service.consume(
                tenant_id=tenant.id,
                account_id=account.id,
                amount=Decimal(str(config.invite_code_cost_credits)),
                reference_type="invite_code_purchase",
                remark="生成邀请码",
                operator_id=inviter_user.id,
                extra={"inviterUserId": inviter_user.id},
            )
            purchase_tx_id = int(tx.id)

        now = datetime.now(UTC)
        code = await self.code_repo.create(
            {
                "tenant_id": tenant.id,
                "inviter_user_id": inviter_user.id,
                "code": await self._generate_unique_code(),
                "status": InviteCodeStatus.ACTIVE.value,
                "expires_at": now + timedelta(days=normalized_expires_days),
                "max_uses": 1,
                "used_count": 0,
                "last_used_at": None,
                "extra": {
                    "costCredits": int(config.invite_code_cost_credits or 0),
                    "expiresIn": normalized_expires_days,
                    "purchaseTxId": purchase_tx_id,
                },
            }
        )

        logger.info(
            "invite_code_generated",
            tenant_id=tenant.id,
            inviter_user_id=inviter_user.id,
            invite_code_id=code.id,
            max_uses=1,
            remaining_invite_quota_before=remaining_invite_quota,
            expires_days=normalized_expires_days,
            purchase_tx_id=purchase_tx_id,
        )
        return code

    async def recycle_code(
        self,
        *,
        tenant: Tenant,
        inviter_user: User,
        invite_code_id: int,
    ) -> InviteCode:
        stmt = (
            select(InviteCode)
            .where(
                InviteCode.id == invite_code_id,
                InviteCode.tenant_id == tenant.id,
                InviteCode.inviter_user_id == inviter_user.id,
                InviteCode.deleted_at.is_(None),
            )
            .with_for_update()
        )
        await escalate_to_write_lock(self.db)
        result = await self.db.execute(stmt)
        invite_code = result.scalar_one_or_none()
        if not invite_code:
            raise BusinessError(message="邀请码不存在")

        await self._sync_code_status(invite_code)
        extra = dict(invite_code.extra or {})

        if int(invite_code.used_count or 0) > 0:
            raise BusinessError(message="已使用的邀请码不能回收")
        if extra.get("refundTxId"):
            raise BusinessError(message="邀请码已回收")
        if invite_code.status == InviteCodeStatus.DISABLED.value:
            raise BusinessError(message="邀请码已停用")

        refunded_credits = 0
        refund_tx_id: int | None = None
        purchase_tx_id = extra.get("purchaseTxId")
        cost_credits = int(extra.get("costCredits") or 0)
        recycled_at = datetime.now(UTC)

        if purchase_tx_id and cost_credits > 0:
            credit_service = CreditService(self.db)
            refund_tx = await credit_service.refund(
                tenant_id=tenant.id,
                transaction_id=int(purchase_tx_id),
                amount=Decimal(str(cost_credits)),
                remark="回收邀请码退回积分",
                operator_id=inviter_user.id,
                extra={
                    "inviteCodeId": invite_code.id,
                    "refundReason": "invite_code_recycle",
                },
            )
            refund_tx_id = int(refund_tx.id)
            refunded_credits = cost_credits

        extra.update(
            {
                "recycledAt": recycled_at.isoformat(),
                "refundTxId": refund_tx_id,
                "refundedCredits": refunded_credits,
                "refundedAt": recycled_at.isoformat() if refund_tx_id else None,
            }
        )
        invite_code.status = InviteCodeStatus.DISABLED.value
        invite_code.extra = extra
        await self.db.flush()

        logger.info(
            "invite_code_recycled",
            tenant_id=tenant.id,
            inviter_user_id=inviter_user.id,
            invite_code_id=invite_code.id,
            refund_tx_id=refund_tx_id,
            refunded_credits=refunded_credits,
        )
        return invite_code

    async def create_registration_from_code(
        self,
        *,
        invite_code: InviteCode,
        tenant: Tenant,
        invited_user: User,
    ) -> InviteRegistration:
        await self._sync_code_status(invite_code)
        if invite_code.status != InviteCodeStatus.ACTIVE.value:
            raise BusinessError(message="邀请码无效或已失效")

        if invite_code.tenant_id != tenant.id:
            raise BusinessError(message="邀请码与租户不匹配")

        config = self.get_config(tenant)
        if not config.enabled:
            raise BusinessError(message="当前租户未启用邀请注册")

        inviter_stmt = (
            select(User)
            .where(
                User.id == invite_code.inviter_user_id,
                User.tenant_id == tenant.id,
                User.deleted_at.is_(None),
            )
            # User.organization is joined eagerly; limit the lock target to users so
            # PostgreSQL does not reject FOR UPDATE on the nullable join side.
            .with_for_update(of=User)
        )
        await escalate_to_write_lock(self.db)
        inviter_result = await self.db.execute(inviter_stmt)
        inviter = inviter_result.scalar_one_or_none()
        if not inviter:
            raise BusinessError(message="邀请人不存在")
        if inviter.id == invited_user.id:
            raise BusinessError(message="不能使用自己的邀请码")

        if int(invite_code.used_count or 0) >= int(invite_code.max_uses or 0):
            invite_code.status = InviteCodeStatus.EXHAUSTED.value
            await self.db.flush()
            raise BusinessError(message="邀请码已达使用上限")

        now = datetime.now(UTC)
        available_at = now + timedelta(days=int(config.reward_delay_days or 0))

        record = await self.registration_repo.create(
            {
                "tenant_id": tenant.id,
                "invite_code_id": invite_code.id,
                "inviter_user_id": inviter.id,
                "invited_user_id": invited_user.id,
                "invite_code": invite_code.code,
                "inviter_reward_credits": Decimal(str(config.inviter_reward_credits or 0)),
                "invitee_reward_credits": Decimal(str(config.invitee_reward_credits or 0)),
                "reward_delay_days": int(config.reward_delay_days or 0),
                "available_at": available_at,
                "inviter_reward_status": (
                    InviteRewardStatus.PENDING.value
                    if int(config.inviter_reward_credits or 0) > 0
                    else InviteRewardStatus.SKIPPED.value
                ),
                "invitee_reward_status": (
                    InviteRewardStatus.PENDING.value
                    if int(config.invitee_reward_credits or 0) > 0
                    else InviteRewardStatus.SKIPPED.value
                ),
                "extra": {
                    "inviterUsername": inviter.username,
                    "invitedUsername": invited_user.username,
                },
            }
        )

        invite_code.used_count = int(invite_code.used_count or 0) + 1
        invite_code.last_used_at = now
        if int(invite_code.used_count or 0) >= int(invite_code.max_uses or 0):
            invite_code.status = InviteCodeStatus.EXHAUSTED.value

        await self.db.flush()

        logger.info(
            "invite_registration_created",
            tenant_id=tenant.id,
            invite_code_id=invite_code.id,
            invitation_record_id=record.id,
            inviter_user_id=inviter.id,
            invited_user_id=invited_user.id,
        )
        return record

    async def process_due_rewards(
        self,
        *,
        tenant_id: int,
        user_id: int | None = None,
        limit: int = 200,
    ) -> int:
        stmt = (
            select(InviteRegistration)
            .where(
                InviteRegistration.tenant_id == tenant_id,
                InviteRegistration.deleted_at.is_(None),
                InviteRegistration.available_at <= datetime.now(UTC),
                or_(
                    InviteRegistration.inviter_reward_status == InviteRewardStatus.PENDING.value,
                    InviteRegistration.invitee_reward_status == InviteRewardStatus.PENDING.value,
                ),
            )
            .order_by(InviteRegistration.id)
            .limit(limit)
        )
        if user_id is not None:
            stmt = stmt.where(
                or_(
                    InviteRegistration.inviter_user_id == user_id,
                    InviteRegistration.invited_user_id == user_id,
                )
            )

        result = await self.db.execute(stmt)
        records = list(result.scalars().all())
        if not records:
            return 0

        credit_service = CreditService(self.db)
        changed = 0
        user_cache: dict[int, User | None] = {}

        async def _get_user(target_user_id: int) -> User | None:
            if target_user_id not in user_cache:
                user_cache[target_user_id] = await self.user_repo.get_one(
                    where=[
                        User.id == target_user_id,
                        User.tenant_id == tenant_id,
                    ],
                    raise_not_found=False,
                )
            return user_cache[target_user_id]

        for record in records:
            invitee = await _get_user(record.invited_user_id)
            if not invitee or invitee.status != UserStatus.ENABLED:
                continue

            inviter = await _get_user(record.inviter_user_id)

            if (
                record.inviter_reward_status == InviteRewardStatus.PENDING.value
                and inviter
                and Decimal(record.inviter_reward_credits or 0) > 0
            ):
                try:
                    inviter_account = await credit_service.get_user_account(
                        tenant_id=tenant_id,
                        user_id=record.inviter_user_id,
                    )
                    if not inviter_account:
                        inviter_account = await credit_service.init_user_account(
                            tenant_id=tenant_id,
                            user_id=record.inviter_user_id,
                            operator_id=None,
                        )
                    tx = await credit_service.bonus(
                        tenant_id=tenant_id,
                        account_id=inviter_account.id,
                        amount=Decimal(record.inviter_reward_credits),
                        operator_id=None,
                        remark=f"邀请用户 {invitee.username} 注册奖励",
                        extra={
                            "inviteRegistrationId": record.id,
                            "rewardSide": "inviter",
                            "counterpartyUserId": invitee.id,
                        },
                    )
                    record.inviter_reward_status = InviteRewardStatus.ISSUED.value
                    record.inviter_reward_issued_at = datetime.now(UTC)
                    record.inviter_credit_tx_id = tx.id
                    changed += 1
                except Exception as exc:
                    logger.warning(
                        "invite_reward_issue_failed",
                        tenant_id=tenant_id,
                        invitation_record_id=record.id,
                        reward_side="inviter",
                        error=str(exc),
                    )

            if (
                record.invitee_reward_status == InviteRewardStatus.PENDING.value
                and Decimal(record.invitee_reward_credits or 0) > 0
            ):
                try:
                    invitee_account = await credit_service.get_user_account(
                        tenant_id=tenant_id,
                        user_id=record.invited_user_id,
                    )
                    if not invitee_account:
                        invitee_account = await credit_service.init_user_account(
                            tenant_id=tenant_id,
                            user_id=record.invited_user_id,
                            operator_id=None,
                        )
                    tx = await credit_service.bonus(
                        tenant_id=tenant_id,
                        account_id=invitee_account.id,
                        amount=Decimal(record.invitee_reward_credits),
                        operator_id=None,
                        remark="受邀注册奖励",
                        extra={
                            "inviteRegistrationId": record.id,
                            "rewardSide": "invitee",
                            "counterpartyUserId": record.inviter_user_id,
                        },
                    )
                    record.invitee_reward_status = InviteRewardStatus.ISSUED.value
                    record.invitee_reward_issued_at = datetime.now(UTC)
                    record.invitee_credit_tx_id = tx.id
                    changed += 1
                except Exception as exc:
                    logger.warning(
                        "invite_reward_issue_failed",
                        tenant_id=tenant_id,
                        invitation_record_id=record.id,
                        reward_side="invitee",
                        error=str(exc),
                    )

        if changed > 0:
            await self.db.flush()

        return changed

    async def list_records(
        self,
        *,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        user_id: int | None = None,
        relation: InvitationRelation = "all",
        keyword: str | None = None,
        invite_code: str | None = None,
        invite_code_status: str | None = None,
        inviter_keyword: str | None = None,
        inviter_user_status: int | None = None,
        inviter_register_source: str | None = None,
        invited_keyword: str | None = None,
        invited_user_status: int | None = None,
        invited_register_source: str | None = None,
        inviter_reward_status: str | None = None,
        invitee_reward_status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        inviter_alias = aliased(User)
        invited_alias = aliased(User)

        stmt = (
            select(
                InviteRegistration,
                InviteCode.status.label("invite_code_status"),
                inviter_alias.username.label("inviter_username"),
                inviter_alias.nickname.label("inviter_nickname"),
                inviter_alias.email.label("inviter_email"),
                inviter_alias.phone.label("inviter_phone"),
                inviter_alias.status.label("inviter_user_status"),
                inviter_alias.register_source.label("inviter_register_source"),
                inviter_alias.created_at.label("inviter_created_at"),
                invited_alias.username.label("invited_username"),
                invited_alias.nickname.label("invited_nickname"),
                invited_alias.email.label("invited_email"),
                invited_alias.phone.label("invited_phone"),
                invited_alias.status.label("invited_user_status"),
                invited_alias.register_source.label("invited_register_source"),
                invited_alias.created_at.label("invited_created_at"),
            )
            .select_from(InviteRegistration)
            .outerjoin(InviteCode, InviteCode.id == InviteRegistration.invite_code_id)
            .outerjoin(
                inviter_alias,
                and_(
                    inviter_alias.id == InviteRegistration.inviter_user_id,
                    inviter_alias.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                invited_alias,
                and_(
                    invited_alias.id == InviteRegistration.invited_user_id,
                    invited_alias.deleted_at.is_(None),
                ),
            )
            .where(
                InviteRegistration.tenant_id == tenant_id,
                InviteRegistration.deleted_at.is_(None),
            )
        )

        if user_id is not None:
            if relation == "sent":
                stmt = stmt.where(InviteRegistration.inviter_user_id == user_id)
            elif relation == "received":
                stmt = stmt.where(InviteRegistration.invited_user_id == user_id)
            else:
                stmt = stmt.where(
                    or_(
                        InviteRegistration.inviter_user_id == user_id,
                        InviteRegistration.invited_user_id == user_id,
                    )
                )

        normalized_keyword = self._normalize_query_str(keyword)
        if normalized_keyword:
            stmt = stmt.where(
                or_(
                    InviteRegistration.invite_code.ilike(f"%{normalized_keyword}%"),
                    self._build_user_keyword_filter(inviter_alias, normalized_keyword),
                    self._build_user_keyword_filter(invited_alias, normalized_keyword),
                )
            )

        normalized_invite_code = self._normalize_query_str(invite_code)
        if normalized_invite_code:
            stmt = stmt.where(InviteRegistration.invite_code.ilike(f"%{normalized_invite_code}%"))

        normalized_invite_code_status = (self._normalize_query_str(invite_code_status) or "").lower()
        if normalized_invite_code_status and normalized_invite_code_status != "all":
            stmt = stmt.where(InviteCode.status == normalized_invite_code_status)

        normalized_inviter_keyword = self._normalize_query_str(inviter_keyword)
        if normalized_inviter_keyword:
            stmt = stmt.where(self._build_user_keyword_filter(inviter_alias, normalized_inviter_keyword))

        if inviter_user_status is not None:
            stmt = stmt.where(inviter_alias.status == int(inviter_user_status))

        normalized_inviter_register_source = (self._normalize_query_str(inviter_register_source) or "").lower()
        if normalized_inviter_register_source and normalized_inviter_register_source != "all":
            stmt = stmt.where(inviter_alias.register_source == normalized_inviter_register_source)

        normalized_invited_keyword = self._normalize_query_str(invited_keyword)
        if normalized_invited_keyword:
            stmt = stmt.where(self._build_user_keyword_filter(invited_alias, normalized_invited_keyword))

        if invited_user_status is not None:
            stmt = stmt.where(invited_alias.status == int(invited_user_status))

        normalized_invited_register_source = (self._normalize_query_str(invited_register_source) or "").lower()
        if normalized_invited_register_source and normalized_invited_register_source != "all":
            stmt = stmt.where(invited_alias.register_source == normalized_invited_register_source)

        normalized_inviter_reward_status = (self._normalize_query_str(inviter_reward_status) or "").lower()
        if normalized_inviter_reward_status and normalized_inviter_reward_status != "all":
            stmt = stmt.where(InviteRegistration.inviter_reward_status == normalized_inviter_reward_status)

        normalized_invitee_reward_status = (self._normalize_query_str(invitee_reward_status) or "").lower()
        if normalized_invitee_reward_status and normalized_invitee_reward_status != "all":
            stmt = stmt.where(InviteRegistration.invitee_reward_status == normalized_invitee_reward_status)

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        count_result = await self.db.execute(count_stmt)
        total = int(count_result.scalar() or 0)

        stmt = stmt.order_by(InviteRegistration.id.desc())
        if page_size > 0:
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        rows = result.all()

        payload: list[dict[str, Any]] = []
        for row in rows:
            record: InviteRegistration = row[0]
            if user_id is not None:
                current_relation = "sent" if int(record.inviter_user_id) == int(user_id) else "received"
            else:
                current_relation = None

            payload.append(
                {
                    "id": record.id,
                    "relation": current_relation,
                    "inviteCode": record.invite_code,
                    "inviteCodeStatus": row._mapping.get("invite_code_status"),
                    "inviterUserId": record.inviter_user_id,
                    "inviterUsername": row._mapping.get("inviter_username"),
                    "inviterNickname": row._mapping.get("inviter_nickname"),
                    "inviterEmail": row._mapping.get("inviter_email"),
                    "inviterPhone": row._mapping.get("inviter_phone"),
                    "inviterUserStatus": row._mapping.get("inviter_user_status"),
                    "inviterRegisterSource": row._mapping.get("inviter_register_source"),
                    "inviterCreatedAt": (
                        row._mapping.get("inviter_created_at").isoformat()
                        if row._mapping.get("inviter_created_at")
                        else None
                    ),
                    "invitedUserId": record.invited_user_id,
                    "invitedUsername": row._mapping.get("invited_username"),
                    "invitedNickname": row._mapping.get("invited_nickname"),
                    "invitedEmail": row._mapping.get("invited_email"),
                    "invitedPhone": row._mapping.get("invited_phone"),
                    "invitedUserStatus": row._mapping.get("invited_user_status"),
                    "invitedRegisterSource": row._mapping.get("invited_register_source"),
                    "invitedCreatedAt": (
                        row._mapping.get("invited_created_at").isoformat()
                        if row._mapping.get("invited_created_at")
                        else None
                    ),
                    "inviterRewardCredits": self._decimal_str(record.inviter_reward_credits),
                    "inviteeRewardCredits": self._decimal_str(record.invitee_reward_credits),
                    "rewardDelayDays": record.reward_delay_days,
                    "availableAt": record.available_at.isoformat() if record.available_at else None,
                    "inviterRewardStatus": record.inviter_reward_status,
                    "inviteeRewardStatus": record.invitee_reward_status,
                    "inviterRewardIssuedAt": (
                        record.inviter_reward_issued_at.isoformat() if record.inviter_reward_issued_at else None
                    ),
                    "inviteeRewardIssuedAt": (
                        record.invitee_reward_issued_at.isoformat() if record.invitee_reward_issued_at else None
                    ),
                    "createdAt": record.created_at.isoformat() if record.created_at else None,
                }
            )

        return payload, total
