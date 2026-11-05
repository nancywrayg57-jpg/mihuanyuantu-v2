"""
AOJU Backend - Assistant Billing Helpers

统一 AI 计费底座能力：
- 优先按 provider usage 统计 token
- usage 缺失时按字符估算 token（约 2 字符/1 token）
- 按 token / 积分比例扣除用户积分，支持固定积分兜底
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.domain.credits.billing import (
    DEFAULT_MINIMUM_PRECHECK_CREDITS,
    DEFAULT_POINTS_TOKEN_RATIO,
    charge_usage_with_pricing_mode,
    ensure_user_credit_precheck,
)
from app.domain.credits.billing import (
    calc_points_from_tokens as calc_credit_points_from_tokens,
)
from app.domain.credits.billing import (
    estimate_tokens_from_text as estimate_credit_tokens_from_text,
)
from app.domain.credits.billing import (
    resolve_token_usage as resolve_credit_token_usage,
)
from app.domain.credits.service import CreditService

DEFAULT_FALLBACK_CREDITS_PER_CALL = Decimal("1")


def _to_decimal(value: Any, fallback: Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return fallback
    return parsed


def _quantize_points(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class AssistantBillingPolicy:
    enabled: bool
    points_token_ratio: Decimal
    fallback_credits_per_call: Decimal
    minimum_precheck_credits: Decimal


@dataclass(frozen=True)
class AssistantBillingResult:
    charged: bool
    amount: Decimal
    input_tokens: int
    output_tokens: int
    total_tokens: int
    account_id: int | None = None
    transaction_id: int | None = None


def build_billing_policy(
    *,
    deduct_credits: bool,
    points_token_ratio: Any,
    credits_per_call: Any,
    minimum_precheck_credits: Any = DEFAULT_MINIMUM_PRECHECK_CREDITS,
) -> AssistantBillingPolicy:
    ratio = _to_decimal(points_token_ratio, DEFAULT_POINTS_TOKEN_RATIO)
    if ratio <= 0:
        ratio = Decimal("0")

    fallback = _to_decimal(credits_per_call, DEFAULT_FALLBACK_CREDITS_PER_CALL)
    if fallback < 0:
        fallback = Decimal("0")
    fallback = _quantize_points(fallback)

    minimum = _to_decimal(minimum_precheck_credits, DEFAULT_MINIMUM_PRECHECK_CREDITS)
    if minimum < 0:
        minimum = Decimal("0")
    minimum = _quantize_points(minimum)

    return AssistantBillingPolicy(
        enabled=bool(deduct_credits),
        points_token_ratio=ratio,
        fallback_credits_per_call=fallback,
        minimum_precheck_credits=minimum,
    )


def estimate_tokens_from_text(text: str) -> int:
    return estimate_credit_tokens_from_text(text)


def resolve_token_usage(
    *,
    usage: dict[str, Any] | None,
    prompt_text: str,
    completion_text: str,
) -> tuple[int, int]:
    return resolve_credit_token_usage(
        usage=usage,
        prompt_text=prompt_text,
        completion_text=completion_text,
    )


def calc_points_from_tokens(total_tokens: int, ratio: Decimal) -> Decimal:
    return calc_credit_points_from_tokens(total_tokens, ratio)


def build_prompt_text_from_messages(messages: list[dict[str, str]]) -> str:
    rows: list[str] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower() or "user"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        rows.append(f"{role}: {content}")
    return "\n".join(rows)


def build_billing_result_payload(
    billing: AssistantBillingResult | None,
    *,
    enabled: bool,
    billing_mode: str = "token_usage",
) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "charged": bool(billing and billing.charged),
        "billingMode": str(billing_mode or "token_usage"),
        "amount": str(billing.amount) if billing else "0",
        "inputTokens": int(billing.input_tokens) if billing else 0,
        "outputTokens": int(billing.output_tokens) if billing else 0,
        "totalTokens": int(billing.total_tokens) if billing else 0,
        "accountId": int(getattr(billing, "account_id", None)) if billing and getattr(billing, "account_id", None) else None,
        "transactionId": int(getattr(billing, "transaction_id", None)) if billing and getattr(billing, "transaction_id", None) else None,
    }


async def ensure_credit_precheck(
    *,
    credit_service: CreditService,
    tenant_id: int,
    user_id: int,
    policy: AssistantBillingPolicy,
) -> int | None:
    if not policy.enabled:
        return None
    return await ensure_user_credit_precheck(
        credit_service=credit_service,
        tenant_id=tenant_id,
        user_id=user_id,
        minimum=policy.minimum_precheck_credits,
    )


async def charge_credits_by_usage(
    *,
    credit_service: CreditService,
    tenant_id: int,
    user_id: int,
    policy: AssistantBillingPolicy,
    reference_type: str,
    prompt_text: str,
    completion_text: str,
    usage: dict[str, Any] | None = None,
    reference_id: int | None = None,
    remark: str | None = None,
    operator_id: int | None = None,
    extra: dict[str, Any] | None = None,
    account_id: int | None = None,
    idempotency_key: str | None = None,
) -> AssistantBillingResult:
    input_tokens, output_tokens = resolve_token_usage(
        usage=usage,
        prompt_text=prompt_text,
        completion_text=completion_text,
    )
    total_tokens = input_tokens + output_tokens

    if not policy.enabled:
        return AssistantBillingResult(
            charged=False,
            amount=Decimal("0"),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    points = calc_points_from_tokens(total_tokens, policy.points_token_ratio)
    if points <= 0 and policy.fallback_credits_per_call > 0:
        points = _quantize_points(policy.fallback_credits_per_call)

    # 统一积分策略：legacy 与此前完全一致；shadow/unified 由 credits.billing 按租户模式结算
    charge = await charge_usage_with_pricing_mode(
        credit_service=credit_service,
        tenant_id=tenant_id,
        user_id=user_id,
        legacy_points=points,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        remark=remark,
        operator_id=operator_id,
        account_id=account_id,
        extra={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "points_token_ratio": str(policy.points_token_ratio),
            **(extra or {}),
        },
    )
    if not charge.charged:
        return AssistantBillingResult(
            charged=False,
            amount=Decimal("0"),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    return AssistantBillingResult(
        charged=True,
        amount=charge.amount,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        account_id=charge.account_id,
        transaction_id=charge.transaction_id,
    )
