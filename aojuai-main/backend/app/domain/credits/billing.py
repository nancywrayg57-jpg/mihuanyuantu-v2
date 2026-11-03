"""
AOJU Backend - Credits Billing Core

平台级积分结算底座：
- 统一解析扣费主体
- 统一 token / usage 换算
- 统一执行积分预检与扣费
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.core.exceptions import BusinessError
from app.domain.credits.models import CreditAccount, CreditAccountStatus
from app.domain.credits.service import CreditService

DEFAULT_POINTS_TOKEN_RATIO = Decimal("1000")
DEFAULT_MINIMUM_PRECHECK_CREDITS = Decimal("0.01")


def _to_decimal(value: Any, fallback: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return fallback


def _strict_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BusinessError(message="无效的积分金额") from exc


def quantize_points(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CreditBillingSubjectContext:
    access_user_id: int | None
    owner_user_id: int | None = None
    explicit_billing_user_id: int | None = None
    is_shared_access: bool = False
    exempt_owner_direct_use: bool = False


@dataclass(frozen=True)
class CreditChargeResult:
    charged: bool
    amount: Decimal
    account_id: int | None = None
    transaction_id: int | None = None
    actual_amount: Decimal | None = None
    unbilled_overrun: Decimal = Decimal("0")


def normalize_points_token_ratio(value: Any, default: Decimal = DEFAULT_POINTS_TOKEN_RATIO) -> Decimal:
    ratio = _to_decimal(value, default)
    return ratio if ratio > 0 else Decimal("0")


def resolve_billing_user_id(context: CreditBillingSubjectContext) -> int | None:
    effective = context.explicit_billing_user_id
    if effective is None:
        effective = context.access_user_id
    if effective is None:
        return None

    if (
        context.exempt_owner_direct_use
        and not context.is_shared_access
        and context.owner_user_id is not None
        and context.access_user_id is not None
        and int(context.owner_user_id) == int(context.access_user_id)
        and int(effective) == int(context.access_user_id)
    ):
        return None

    return int(effective)


def resolve_usage_actor_user_id(
    context: CreditBillingSubjectContext,
    *,
    billing_user_id: int | None,
) -> int | None:
    if not context.is_shared_access:
        return context.access_user_id
    return billing_user_id


def estimate_tokens_from_text(text: str) -> int:
    normalized = str(text or "")
    if not normalized.strip():
        return 0
    return max(1, len(normalized) // 2)


def resolve_token_usage(
    *,
    usage: dict[str, Any] | None,
    prompt_text: str,
    completion_text: str,
) -> tuple[int, int]:
    payload = usage or {}

    def _to_int(value: Any) -> int:
        try:
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return 0
            return int(value)
        except Exception:
            try:
                return int(float(value))
            except Exception:
                return 0

    prompt_tokens = _to_int(
        payload.get("prompt_tokens")
        or payload.get("input_tokens")
        or payload.get("promptTokenCount")
        or payload.get("inputTokenCount")
    )
    completion_tokens = _to_int(
        payload.get("completion_tokens")
        or payload.get("output_tokens")
        or payload.get("completionTokenCount")
        or payload.get("candidatesTokenCount")
        or payload.get("outputTokenCount")
    )
    total_tokens = _to_int(payload.get("total_tokens") or payload.get("totalTokenCount") or payload.get("totalToken"))

    est_prompt = estimate_tokens_from_text(prompt_text)
    est_completion = estimate_tokens_from_text(completion_text)

    if total_tokens > 0:
        if prompt_tokens > 0 and completion_tokens == 0:
            derived = max(total_tokens - prompt_tokens, 0)
            completion_tokens = derived if derived > 0 else est_completion
        elif completion_tokens > 0 and prompt_tokens == 0:
            derived = max(total_tokens - completion_tokens, 0)
            prompt_tokens = derived if derived > 0 else est_prompt
        elif prompt_tokens == 0 and completion_tokens == 0:
            if est_prompt > 0:
                prompt_tokens = min(est_prompt, total_tokens)
                completion_tokens = max(total_tokens - prompt_tokens, 0)
            else:
                completion_tokens = total_tokens
    else:
        if prompt_tokens == 0:
            prompt_tokens = est_prompt
        if completion_tokens == 0:
            completion_tokens = est_completion

    return max(prompt_tokens, 0), max(completion_tokens, 0)


def calc_points_from_tokens(total_tokens: int, ratio: Decimal) -> Decimal:
    if ratio <= 0 or total_tokens <= 0:
        return Decimal("0")
    points = quantize_points(Decimal(str(total_tokens)) / ratio)
    return points if points > 0 else Decimal("0")


async def get_or_init_user_credit_account(
    *,
    credit_service: CreditService,
    tenant_id: int,
    user_id: int,
) -> CreditAccount:
    account = await credit_service.get_user_account(tenant_id=tenant_id, user_id=user_id)
    if account is None:
        account = await credit_service.init_user_account(tenant_id=tenant_id, user_id=user_id)
    return account


def ensure_credit_account_usable(
    *,
    account: CreditAccount,
    minimum: Decimal = DEFAULT_MINIMUM_PRECHECK_CREDITS,
) -> None:
    if account.status != CreditAccountStatus.ACTIVE.value:
        raise BusinessError(message="积分账户已冻结，无法使用", code="CREDIT_ACCOUNT_FROZEN")
    if (account.balance or Decimal("0")) < minimum:
        raise BusinessError(message="积分余额不足，请先充值", code="INSUFFICIENT_CREDITS")


async def ensure_user_credit_precheck(
    *,
    credit_service: CreditService,
    tenant_id: int,
    user_id: int | None,
    minimum: Decimal = DEFAULT_MINIMUM_PRECHECK_CREDITS,
) -> int | None:
    if user_id is None:
        return None
    account = await get_or_init_user_credit_account(
        credit_service=credit_service,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    ensure_credit_account_usable(account=account, minimum=minimum)
    return int(account.id)


async def charge_user_credits(
    *,
    credit_service: CreditService,
    tenant_id: int,
    user_id: int | None,
    amount: Decimal | int | str,
    reference_type: str,
    reference_id: int | None = None,
    remark: str | None = None,
    operator_id: int | None = None,
    extra: dict[str, Any] | None = None,
    account_id: int | None = None,
    idempotency_key: str | None = None,
) -> CreditChargeResult:
    if user_id is None:
        return CreditChargeResult(charged=False, amount=Decimal("0"))

    normalized = _strict_decimal(amount)
    if normalized <= 0:
        return CreditChargeResult(charged=False, amount=Decimal("0"))

    account = None
    if account_id is not None:
        account = await credit_service.get_account_by_id(account_id, tenant_id)
    if account is None:
        account = await get_or_init_user_credit_account(
            credit_service=credit_service,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    transaction = await credit_service.consume(
        tenant_id=tenant_id,
        account_id=int(account.id),
        amount=normalized,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        remark=remark,
        operator_id=operator_id,
        extra=extra,
    )

    billing = (transaction.extra or {}).get("billing") or {}
    return CreditChargeResult(
        charged=True,
        amount=Decimal(transaction.amount),
        account_id=int(transaction.account_id),
        transaction_id=int(transaction.id),
        actual_amount=Decimal(str(billing.get("actualAmount", transaction.amount))),
        unbilled_overrun=Decimal(str(billing.get("unbilledOverrun") or "0")),
    )


async def _charge_capped_legacy(
    *, credit_service: CreditService, tenant_id: int, user_id: int,
    legacy_points: Decimal, maximum_amount: Decimal | None,
    reference_type: str, reference_id: int | None, idempotency_key: str | None,
    remark: str | None, operator_id: int | None, account_id: int | None,
    extra: dict[str, Any] | None,
) -> CreditChargeResult:
    # SQLite 轻量档：下面是"读幂等键 → 锁账户 → 写"，必须在第一条读之前进入写事务（PG 下 no-op）。
    from app.infrastructure.database.portable_sql import escalate_to_write_lock

    await escalate_to_write_lock(credit_service.db)
    if idempotency_key:
        previous = await credit_service.get_transaction_by_idempotency_key(
            tenant_id=tenant_id, idempotency_key=idempotency_key,
        )
        if previous is not None:
            billing = (previous.extra or {}).get("billing") or {}
            return CreditChargeResult(
                charged=True, amount=Decimal(previous.amount), account_id=int(previous.account_id),
                transaction_id=int(previous.id),
                actual_amount=Decimal(str(billing.get("actualAmount", previous.amount))),
                unbilled_overrun=Decimal(str(billing.get("unbilledOverrun") or "0")),
            )
    actual = max(Decimal(0), quantize_points(legacy_points))
    amount = min(actual, maximum_amount) if maximum_amount is not None else actual
    overrun = actual - amount
    if amount <= 0:
        return CreditChargeResult(charged=False, amount=Decimal(0), actual_amount=actual, unbilled_overrun=overrun)
    metadata = dict(extra or {})
    if maximum_amount is not None:
        metadata["billing"] = {
            **dict(metadata.get("billing") or {}), "actualAmount": str(actual),
            "chargedAmount": str(amount), "unbilledOverrun": str(overrun),
        }
    return await charge_user_credits(
        credit_service=credit_service, tenant_id=tenant_id, user_id=user_id, amount=amount,
        reference_type=reference_type, reference_id=reference_id, idempotency_key=idempotency_key,
        remark=remark, operator_id=operator_id, account_id=account_id, extra=metadata,
    )


async def resolve_pricing_context(credit_service: CreditService, *, tenant_id: int) -> tuple[str, list, str]:
    """(pricingMode, 生效费率项, priceVersion)。放在这里避免各模块各自拼三个调用。"""
    from app.domain.credits.price_service import list_effective_price_items, pricebook_version
    from app.domain.credits.pricing_mode import get_tenant_pricing_mode

    mode = await get_tenant_pricing_mode(credit_service.db, tenant_id=int(tenant_id))
    if mode == "legacy":
        return mode, [], pricebook_version()
    items = await list_effective_price_items(credit_service.db, tenant_id=int(tenant_id))
    return mode, items, pricebook_version()


async def resolve_rate_context(
    credit_service: CreditService,
    *,
    tenant_id: int,
    conservative: bool = False,
):
    """Resolve the tenant-local clock used by scheduled rates.

    Provider schedules may still declare a fixed timezone such as UTC; tenant-local
    schedules use this context. Reserve estimates set ``conservative`` to charge the
    maximum configured band and refund the difference after completion.
    """
    from app.core.tenant_time import get_tenant_timezone
    from app.domain.credits.pricing import PricingContext

    timezone_name = await get_tenant_timezone(
        credit_service.db,
        tenant_id=int(tenant_id),
    )
    return PricingContext(
        tenant_timezone=timezone_name,
        conservative=bool(conservative),
    )


async def charge_usage_with_pricing_mode(
    *,
    credit_service: CreditService,
    tenant_id: int,
    user_id: int,
    legacy_points: Decimal,
    reference_type: str,
    reference_id: int | None = None,
    idempotency_key: str | None = None,
    remark: str | None = None,
    operator_id: int | None = None,
    extra: dict[str, Any] | None = None,
    account_id: int | None = None,
    maximum_amount: Decimal | None = None,
) -> CreditChargeResult:
    """按租户计价模式扣费（统一积分策略 P2 的模块接入点）。

    legacy  → 与 charge_user_credits 完全一致（legacy_points ≤ 0 不扣）；
    shadow  → 仍扣 legacy_points，同时把统一费率结果写进流水 extra.billing.shadow；
    unified → 忽略 legacy_points，按根收集器实际用量 × 费率结算（不足 0.01 免费）。
    模块级"是否计费"开关由调用方在进入前判断，这里不再看。
    """
    import uuid

    from app.domain.credits.settlement import SettlementContext, settle_immediate

    if maximum_amount is not None:
        if not maximum_amount.is_finite() or maximum_amount < 0:
            raise ValueError("maximum_amount must be finite and nonnegative")
        maximum_amount = quantize_points(maximum_amount)
    mode, items, version = await resolve_pricing_context(credit_service, tenant_id=int(tenant_id))
    if mode == "legacy":
        return await _charge_capped_legacy(
            credit_service=credit_service,
            tenant_id=tenant_id,
            user_id=user_id,
            legacy_points=legacy_points,
            maximum_amount=maximum_amount,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            remark=remark,
            operator_id=operator_id,
            extra=extra,
            account_id=account_id,
        )
    from app.domain.credits.usage import current_usage_collector

    collector = current_usage_collector()
    if mode == "unified" and (collector is None or not collector.events):
        # 没有任何模型/按件事件的动作（固定费：出题策略、按次工具等）在 unified 下仍按旧固定金额扣，
        # 流水标 basis=flat_fallback，便于灰度期识别"没接计量的动作"
        rate_context = await resolve_rate_context(credit_service, tenant_id=int(tenant_id))
        return await _charge_capped_legacy(
            credit_service=credit_service, tenant_id=tenant_id, user_id=user_id,
            legacy_points=legacy_points, maximum_amount=maximum_amount,
            reference_type=reference_type, reference_id=reference_id, idempotency_key=idempotency_key, remark=remark,
            operator_id=operator_id, account_id=account_id,
            extra={
                **(extra or {}),
                "billing": {
                    "pricingMode": mode,
                    "basis": "flat_fallback",
                    "legacyAmount": str(legacy_points),
                    "tenantTimezone": rate_context.tenant_timezone,
                },
            },
        )
    rate_context = await resolve_rate_context(credit_service, tenant_id=int(tenant_id))
    ctx = SettlementContext(
        tenant_id=int(tenant_id),
        payer_user_id=int(user_id),
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_base=str(idempotency_key or f"{reference_type}:{reference_id or ''}:{uuid.uuid4().hex}"),
        operator_id=operator_id,
        remark=remark,
        account_id=account_id,
        tenant_timezone=rate_context.tenant_timezone,
        extra=dict(extra or {}),
    )
    result = await settle_immediate(
        credit_service,
        ctx,
        mode=mode,  # type: ignore[arg-type]
        price_items=items,
        price_version=version,
        legacy_amount=legacy_points if mode == "shadow" else None,
        maximum_amount=maximum_amount,
    )
    return CreditChargeResult(
        charged=result.charged, amount=result.amount, account_id=ctx.account_id,
        transaction_id=result.transaction_id,
        actual_amount=Decimal(str(result.billing.get("actualAmount", result.amount))),
        unbilled_overrun=result.unbilled_overrun,
    )
