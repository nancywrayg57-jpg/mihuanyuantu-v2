"""Manual recharge orders. Order support confirms or rejects. No scan-to-pay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.constants import INBOX_TTL_DAYS
from app.capabilities.realphotos.models import RealphotosInboxMessage, RealphotosRechargeOrder
from app.capabilities.realphotos.permissions import ROLE_ORDER_SUPPORT
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.s1_catalog import credits_for_tier_yuan, price_formula
from app.core.exceptions import BusinessError, NotFoundError
from app.domain.roles.models import Role
from app.domain.users.models import UserRole


def is_recharge_inbox_event(event_key: str | None, title: str | None = None) -> bool:
    key = str(event_key or "")
    if key.startswith("recharge:"):
        return True
    # 补发副本 event_key=resend:{id}:{ts}，用标题识别充值通知
    return "充值" in str(title or "")


class RealphotosRechargeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_order(
        self,
        *,
        tenant_id: int,
        requester_user_id: int,
        tier_yuan: int,
        voucher_note: str,
        idempotency_key: str,
    ) -> RealphotosRechargeOrder:
        note = str(voucher_note or "").strip()
        key = str(idempotency_key or "").strip()
        if not note or not key:
            raise BusinessError(message="缺少凭证备注或幂等键", code="INPUT_INVALID")
        points = credits_for_tier_yuan(int(tier_yuan))
        if points <= 0:
            raise BusinessError(message="充值档位不在 100/300/500/1000/3000 元", code="TIER_REJECTED")
        existing = (
            await self.db.execute(
                select(RealphotosRechargeOrder).where(
                    RealphotosRechargeOrder.tenant_id == int(tenant_id),
                    RealphotosRechargeOrder.idempotency_key == key,
                    RealphotosRechargeOrder.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        order = RealphotosRechargeOrder(
            tenant_id=int(tenant_id),
            requester_user_id=int(requester_user_id),
            tier_yuan=int(tier_yuan),
            credit_points=points,
            price_formula=price_formula(),
            voucher_note=note,
            status="pending",
            idempotency_key=key,
        )
        self.db.add(order)
        await self.db.flush()
        await self._notify_order_support_pending(order)
        return order

    async def _notify_order_support_pending(self, order: RealphotosRechargeOrder) -> None:
        """站内通知订单客服：仅充值待确认类（IA_C7）。"""
        recipients = (
            await self.db.execute(
                select(UserRole.user_id, UserRole.tenant_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    Role.code == ROLE_ORDER_SUPPORT,
                    Role.deleted_at.is_(None),
                )
            )
        ).all()
        now = datetime.now(UTC)
        expires = now + timedelta(days=INBOX_TTL_DAYS)
        for user_id, recipient_tenant_id in recipients:
            event_key = f"recharge:{int(order.id)}:pending:user:{int(user_id)}"
            exists = (
                await self.db.execute(
                    select(RealphotosInboxMessage.id).where(
                        RealphotosInboxMessage.tenant_id == int(recipient_tenant_id),
                        RealphotosInboxMessage.event_key == event_key,
                        RealphotosInboxMessage.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue
            self.db.add(
                RealphotosInboxMessage(
                    tenant_id=int(recipient_tenant_id),
                    recipient_user_id=int(user_id),
                    event_key=event_key,
                    title="商家充值待确认",
                    body=(
                        f"租户 {int(order.tenant_id)} 申请 {int(order.tier_yuan)} 元"
                        f" / {int(order.credit_points)} 积分，请确认或拒单。"
                    ),
                    expires_at=expires,
                )
            )
        await self.db.flush()

    async def list_pending(self, *, limit: int = 50) -> list[RealphotosRechargeOrder]:
        """订单客服跨租户看待处理单。不含原图。"""
        rows = await self.db.execute(
            select(RealphotosRechargeOrder)
            .where(
                RealphotosRechargeOrder.status == "pending",
                RealphotosRechargeOrder.deleted_at.is_(None),
            )
            .order_by(RealphotosRechargeOrder.id.asc())
            .limit(max(1, min(int(limit), 100)))
        )
        return list(rows.scalars().all())

    async def confirm(self, *, order_id: int, operator_user_id: int) -> RealphotosRechargeOrder:
        order = await self._order(order_id)
        if order.status == "confirmed":
            return order
        if order.status != "pending":
            raise BusinessError(message="订单不可确认", code="ORDER_STATE")
        await RealphotosCreditService(self.db).confirm_recharge(
            tenant_id=int(order.tenant_id),
            amount=int(order.credit_points),
            operator_user_id=int(operator_user_id),
            target_user_id=int(order.requester_user_id),
            event_key=f"recharge:{int(order.id)}:confirm",
            reference={"orderId": int(order.id), "tierYuan": int(order.tier_yuan)},
        )
        order.status = "confirmed"
        order.confirmed_by_user_id = int(operator_user_id)
        await self.db.flush()
        return order

    async def reject(self, *, order_id: int, operator_user_id: int, reason: str) -> RealphotosRechargeOrder:
        text = str(reason or "").strip()
        if not text:
            raise BusinessError(message="拒单必须填写原因", code="INPUT_INVALID")
        order = await self._order(order_id)
        if order.status == "rejected":
            return order
        if order.status != "pending":
            raise BusinessError(message="订单不可拒绝", code="ORDER_STATE")
        order.status = "rejected"
        order.reject_reason = text
        order.confirmed_by_user_id = int(operator_user_id)
        await self.db.flush()
        return order

    async def _order(self, order_id: int) -> RealphotosRechargeOrder:
        order = (
            await self.db.execute(
                select(RealphotosRechargeOrder).where(
                    RealphotosRechargeOrder.id == int(order_id),
                    RealphotosRechargeOrder.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if order is None:
            raise NotFoundError(message="充值订单不存在")
        return order
