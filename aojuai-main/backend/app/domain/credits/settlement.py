"""统一结算 primitive：即时结算 / 硬预算预留（reserve → complete | refund）。

设计：devdocs/plans/UNIFIED_CREDIT_PRICING_PLAN_20260826.md §4.3（codex 评审后）。

- 唯一结算者：调用方是业务根动作，传入已解析好的付费人 `payer_user_id`
  （这里不做"扣创建者还是访问者"的判断）。
- 三种模式：
  legacy  → 只按调用方给的旧算法金额扣（金额算法不变），流水附用量快照；
  shadow  → 同 legacy 扣费，同时把统一费率算出的结果写进 `extra.billing.shadow`（不改余额）；
  unified → 只按统一费率结算；合并后不足 0.01 → 免费（不落流水）。
- 硬预算预留：`reserve()` 先扣上限；`complete()` 只退差额，**不追扣**；实际超过预留
  最多收预留额并记 `unbilledOverrun`；`refund_all()` 失败/取消全退。
  幂等键固定为 `{base}:reserve` / `{base}:complete` / `{base}:refund`。
- 预留时固定 `priceVersion`，任务中途费率变化不影响本次结算（complete 用传入的费率表，
  调用方应传预留时冻结的那份；未传则用当前生效费率并在明细里标 priceVersionDrift）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.core.logger import get_logger
from app.domain.credits.models import CreditTransaction
from app.domain.credits.pricing import PriceItem, PricedUsage, PricingContext, price_usage, quantize_points
from app.domain.credits.pricing_mode import PricingMode
from app.domain.credits.service import CreditService
from app.domain.credits.usage import UsageCollector, current_usage_collector
from app.infrastructure.database.portable_sql import escalate_to_write_lock

logger = get_logger(__name__)

MIN_CHARGE = Decimal("0.01")


@dataclass(slots=True)
class SettlementContext:
    tenant_id: int
    payer_user_id: int
    reference_type: str
    idempotency_base: str
    reference_id: int | None = None
    operator_id: int | None = None
    remark: str | None = None
    account_id: int | None = None
    tenant_timezone: str = "UTC"
    extra: dict[str, Any] = field(default_factory=dict)
    # 少数任务需要按失败阶段区分补偿键；为空时保持历史 `{base}:refund`。
    refund_idempotency_key: str | None = None


@dataclass(slots=True)
class SettlementResult:
    mode: PricingMode
    charged: bool
    amount: Decimal
    transaction_id: int | None = None
    refund_transaction_id: int | None = None
    refunded: Decimal = Decimal(0)
    unified_points: Decimal | None = None
    unbilled_overrun: Decimal = Decimal(0)
    free: bool = False
    fallback_rate: bool = False
    billing: dict[str, Any] = field(default_factory=dict)


def _collector_or_current(collector: UsageCollector | None) -> UsageCollector | None:
    return collector if collector is not None else current_usage_collector()


def price_collector(
    collector: UsageCollector | None,
    price_items: list[PriceItem],
    pricing_context: PricingContext | None = None,
) -> PricedUsage:
    """只对尚未被其它流水结算的事件计价（嵌套 planner/子任务先结算过的会被跳过）。"""
    events = collector.unsettled_events() if collector is not None else []
    return price_usage(events, price_items, context=pricing_context)


def _unsettled_view(collector: UsageCollector | None) -> UsageCollector | None:
    if collector is None:
        return None
    view = UsageCollector(stage=collector.stage, label=collector.label)
    view.events = collector.unsettled_events()
    return view


def build_billing_extra(
    *,
    mode: PricingMode,
    priced: PricedUsage | None,
    price_version: str | None,
    collector: UsageCollector | None,
    legacy_amount: Decimal | None = None,
    pricing_context: PricingContext | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"pricingMode": mode, "priceVersion": price_version}
    if pricing_context is not None:
        payload["tenantTimezone"] = pricing_context.tenant_timezone
    if legacy_amount is not None:
        payload["legacyAmount"] = str(quantize_points(legacy_amount))
    if priced is not None:
        priced_payload = priced.to_dict()
        if mode == "shadow":
            payload["shadow"] = priced_payload
        else:
            payload.update({"points": priced_payload["points"], "items": priced_payload["items"], "unpriced": priced_payload["unpriced"], "fallbackRate": priced_payload["fallbackRate"]})
    view = _unsettled_view(collector)
    if view is not None and view.events:
        payload["totals"] = view.totals()
        payload["byModel"] = view.by_model()
        payload["byStage"] = view.by_stage()
    return payload


async def _get_account_id(credit_service: CreditService, ctx: SettlementContext) -> int:
    if ctx.account_id:
        return int(ctx.account_id)
    account = await credit_service.init_user_account(tenant_id=int(ctx.tenant_id), user_id=int(ctx.payer_user_id))
    ctx.account_id = int(account.id)
    return ctx.account_id


async def settle_immediate(
    credit_service: CreditService,
    ctx: SettlementContext,
    *,
    mode: PricingMode,
    price_items: list[PriceItem],
    price_version: str | None,
    legacy_amount: Decimal | None = None,
    collector: UsageCollector | None = None,
    maximum_amount: Decimal | None = None,
) -> SettlementResult:
    """对话类根动作完成后按实际用量结算一次。"""
    col = _collector_or_current(collector)
    if maximum_amount is not None and (not maximum_amount.is_finite() or maximum_amount < 0):
        raise ValueError("maximum_amount must be finite and nonnegative")
    # SQLite 轻量档：本函数是"读幂等键 → 锁账户 → 写"，必须在第一条读之前进入写事务（PG 下 no-op）。
    await escalate_to_write_lock(credit_service.db)
    existing = await credit_service.get_transaction_by_idempotency_key(
        tenant_id=int(ctx.tenant_id), idempotency_key=f"{ctx.idempotency_base}:settle"
    )
    if existing is not None:
        ctx.account_id = int(existing.account_id)
        if col is not None:
            col.mark_settled(int(existing.id))
        prior_billing = dict((existing.extra or {}).get("billing") or {})
        return SettlementResult(
            mode=mode, charged=True, amount=Decimal(existing.amount),
            transaction_id=int(existing.id),
            unified_points=Decimal(str(prior_billing.get("points", existing.amount))),
            unbilled_overrun=Decimal(str(prior_billing.get("unbilledOverrun") or "0")),
            billing=prior_billing,
        )
    pricing_context = PricingContext(tenant_timezone=ctx.tenant_timezone)
    priced = price_collector(col, price_items, pricing_context) if mode in {"shadow", "unified"} else None
    if mode == "unified":
        actual = priced.points if priced else Decimal(0)
    else:
        actual = quantize_points(legacy_amount or Decimal(0))
    amount = min(actual, maximum_amount) if maximum_amount is not None else actual
    if amount < MIN_CHARGE:
        amount = Decimal(0)
    billing = build_billing_extra(mode=mode, priced=priced, price_version=price_version, collector=col, legacy_amount=legacy_amount if mode != "unified" else None, pricing_context=pricing_context)
    overrun = max(Decimal(0), actual - amount) if maximum_amount is not None else Decimal(0)
    if maximum_amount is not None:
        billing.update({"actualAmount": str(actual), "chargedAmount": str(amount), "unbilledOverrun": str(overrun)})
    if amount < MIN_CHARGE:
        return SettlementResult(
            mode=mode, charged=False, amount=Decimal(0),
            unified_points=priced.points if priced else None,
            unbilled_overrun=overrun, free=True,
            fallback_rate=bool(priced and priced.used_fallback), billing=billing,
        )
    account_id = await _get_account_id(credit_service, ctx)
    tx = await credit_service.consume(
        tenant_id=int(ctx.tenant_id),
        account_id=account_id,
        amount=amount,
        reference_type=ctx.reference_type,
        reference_id=ctx.reference_id,
        idempotency_key=f"{ctx.idempotency_base}:settle",
        remark=ctx.remark,
        operator_id=ctx.operator_id,
        extra={**ctx.extra, "billing": billing},
    )
    if col is not None:
        col.mark_settled(int(tx.id))
    # consume also arbitrates concurrent requests using the same idempotency key.
    billing = dict((tx.extra or {}).get("billing") or billing)
    return SettlementResult(
        mode=mode,
        charged=True,
        amount=Decimal(tx.amount),
        transaction_id=int(tx.id),
        unified_points=priced.points if priced else None,
        unbilled_overrun=Decimal(str(billing.get("unbilledOverrun") or "0")),
        fallback_rate=bool(priced and priced.used_fallback),
        billing=billing,
    )


async def reserve(
    credit_service: CreditService,
    ctx: SettlementContext,
    *,
    amount: Decimal,
    mode: PricingMode,
    price_version: str | None,
) -> CreditTransaction:
    """任务类根动作入队时按上限预扣（幂等：`{base}:reserve`）。"""
    quantized = quantize_points(amount)
    if quantized < MIN_CHARGE:
        raise ValueError("预留额必须 ≥ 0.01")
    account_id = await _get_account_id(credit_service, ctx)
    return await credit_service.consume(
        tenant_id=int(ctx.tenant_id),
        account_id=account_id,
        amount=quantized,
        reference_type=ctx.reference_type,
        reference_id=ctx.reference_id,
        idempotency_key=f"{ctx.idempotency_base}:reserve",
        remark=ctx.remark,
        operator_id=ctx.operator_id,
        extra={
            **ctx.extra,
            "billing": {
                "pricingMode": mode,
                "priceVersion": price_version,
                "tenantTimezone": ctx.tenant_timezone,
                "reserved": str(quantized),
                "status": "reserved",
            },
        },
    )


async def complete(
    credit_service: CreditService,
    ctx: SettlementContext,
    *,
    reserve_tx: CreditTransaction,
    mode: PricingMode,
    price_items: list[PriceItem],
    price_version: str | None,
    legacy_actual: Decimal | None = None,
    collector: UsageCollector | None = None,
) -> SettlementResult:
    """任务完成：只退差额、不追扣；超出预留最多收预留额并记 unbilledOverrun。幂等：`{base}:complete`。"""
    col = _collector_or_current(collector)
    reserved = quantize_points(Decimal(reserve_tx.amount))
    prior = dict(((reserve_tx.extra or {}).get("billing") or {}))
    if prior.get("status") == "refunded":
        # 已整笔退回（失败/取消补偿先到）：不能再结算，否则会对已退金额再记 charged
        return SettlementResult(mode=mode, charged=False, amount=Decimal(0), transaction_id=int(reserve_tx.id), refunded=Decimal(str(prior.get("refunded") or reserved)), billing=prior)
    if prior.get("status") == "completed":
        # 重复 complete（重试/重放）：返回上次结果，不再计算、不再退款
        return SettlementResult(
            mode=mode, charged=Decimal(str(prior.get("charged") or 0)) >= MIN_CHARGE, amount=Decimal(str(prior.get("charged") or 0)),
            transaction_id=int(reserve_tx.id), refund_transaction_id=(int(prior["refundTransactionId"]) if prior.get("refundTransactionId") else None),
            refunded=Decimal(str(prior.get("refunded") or 0)), unbilled_overrun=Decimal(str(prior.get("unbilledOverrun") or 0)), billing=prior,
        )
    pricing_context = PricingContext(tenant_timezone=ctx.tenant_timezone)
    priced = price_collector(col, price_items, pricing_context) if mode in {"shadow", "unified"} else None
    if mode == "unified":
        actual = priced.points if priced else Decimal(0)
    else:
        actual = quantize_points(legacy_actual if legacy_actual is not None else reserved)
    charge = min(actual, reserved)
    overrun = actual - reserved if actual > reserved else Decimal(0)
    refund_amount = reserved - charge
    billing = build_billing_extra(mode=mode, priced=priced, price_version=price_version, collector=col, legacy_amount=legacy_actual if mode != "unified" else None, pricing_context=pricing_context)
    billing.update({"status": "completed", "reserved": str(reserved), "actual": str(actual), "charged": str(charge), "refunded": str(refund_amount)})
    frozen_version = ((reserve_tx.extra or {}).get("billing") or {}).get("priceVersion")
    if frozen_version and price_version and frozen_version != price_version:
        billing["priceVersionDrift"] = {"reserved": frozen_version, "settled": price_version}
    if overrun > 0:
        billing["unbilledOverrun"] = str(overrun)
        logger.warning(
            "credit_settlement_overrun",
            tenant_id=ctx.tenant_id,
            reference_type=ctx.reference_type,
            reference_id=ctx.reference_id,
            reserved=str(reserved),
            actual=str(actual),
        )
    refund_tx_id: int | None = None
    if refund_amount >= MIN_CHARGE:
        refund_tx = await credit_service.refund(
            tenant_id=int(ctx.tenant_id),
            transaction_id=int(reserve_tx.id),
            amount=refund_amount,
            idempotency_key=f"{ctx.idempotency_base}:complete",
            remark=ctx.remark,
            operator_id=ctx.operator_id,
            extra={"billing": billing, "reason": "settle_difference"},
        )
        refund_tx_id = int(refund_tx.id)
        billing["refundTransactionId"] = refund_tx_id
    if col is not None:
        col.mark_settled(int(reserve_tx.id))
    # 结算结果回写到预留流水的 extra（预留 → 完成的状态在同一条流水上可见）
    extra = dict(reserve_tx.extra or {})
    extra["billing"] = {**(extra.get("billing") or {}), **billing}
    reserve_tx.extra = extra
    flag_modified(reserve_tx, "extra")
    return SettlementResult(
        mode=mode,
        charged=charge >= MIN_CHARGE,
        amount=charge,
        transaction_id=int(reserve_tx.id),
        refund_transaction_id=refund_tx_id,
        refunded=refund_amount if refund_tx_id else Decimal(0),
        unified_points=priced.points if priced else None,
        unbilled_overrun=overrun,
        fallback_rate=bool(priced and priced.used_fallback),
        billing=billing,
    )


async def refund_all(
    credit_service: CreditService,
    ctx: SettlementContext,
    *,
    reserve_tx: CreditTransaction,
    reason: str,
) -> CreditTransaction | None:
    """失败/取消：全额退回预留（幂等：`{base}:refund`）。已部分退过的只退剩余。"""
    reserved = quantize_points(Decimal(reserve_tx.amount))
    prior = ((reserve_tx.extra or {}).get("billing") or {})
    if prior.get("status") == "completed":
        # 任务已按实际用量完成结算：已消费部分不能因后到的失败补偿被退回
        return None
    already = Decimal(str(prior.get("refunded") or "0"))
    remaining = reserved - already
    if remaining < MIN_CHARGE:
        return None
    refund_tx = await credit_service.refund(
        tenant_id=int(ctx.tenant_id),
        transaction_id=int(reserve_tx.id),
        amount=remaining,
        idempotency_key=ctx.refund_idempotency_key or f"{ctx.idempotency_base}:refund",
        remark=ctx.remark,
        operator_id=ctx.operator_id,
        extra={"reason": reason, "autoRefund": True},
    )
    extra = dict(reserve_tx.extra or {})
    extra["billing"] = {**(extra.get("billing") or {}), "status": "refunded", "refunded": str(reserved), "refundReason": reason}
    reserve_tx.extra = extra
    flag_modified(reserve_tx, "extra")
    return refund_tx


__all__ = [
    "MIN_CHARGE",
    "SettlementContext",
    "SettlementResult",
    "build_billing_extra",
    "complete",
    "price_collector",
    "refund_all",
    "reserve",
    "settle_immediate",
]
