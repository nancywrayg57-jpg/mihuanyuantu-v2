"""Speech billing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.credits.billing import charge_user_credits, ensure_user_credit_precheck, quantize_points
from app.domain.credits.service import CreditService

SPEECH_TTS_CREDITS_PER_CHARACTER = Decimal("0.01")


@dataclass(frozen=True)
class SpeechTextBillingResult:
    charged: bool
    amount: Decimal
    character_count: int
    transaction_id: int | None = None


def count_speech_billing_characters(text: str) -> int:
    return len(str(text or ""))


def calc_speech_text_credits(text: str, *, credits_per_character: Decimal = SPEECH_TTS_CREDITS_PER_CHARACTER) -> Decimal:
    character_count = count_speech_billing_characters(text)
    if character_count <= 0 or credits_per_character <= 0:
        return Decimal("0")
    return quantize_points(Decimal(character_count) * credits_per_character)


async def charge_speech_text_credits(
    *,
    credit_service: CreditService,
    tenant_id: int,
    user_id: int | None,
    text: str,
    reference_type: str,
    reference_id: int | None = None,
    provider_id: str | None = None,
    model: str | None = None,
    voice: str | None = None,
    operator_id: int | None = None,
    idempotency_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> SpeechTextBillingResult:
    character_count = count_speech_billing_characters(text)
    amount = calc_speech_text_credits(text)
    if amount <= 0:
        return SpeechTextBillingResult(charged=False, amount=Decimal("0"), character_count=character_count)

    account_id = await ensure_user_credit_precheck(
        credit_service=credit_service,
        tenant_id=tenant_id,
        user_id=user_id,
        minimum=amount,
    )
    result = await charge_user_credits(
        credit_service=credit_service,
        tenant_id=tenant_id,
        user_id=user_id,
        amount=amount,
        reference_type=reference_type,
        reference_id=reference_id,
        remark="语音合成消耗",
        operator_id=operator_id,
        account_id=account_id,
        idempotency_key=idempotency_key,
        extra={
            "module": "speech",
            "billingMetric": "input_characters",
            "characterCount": character_count,
            "creditsPerCharacter": str(SPEECH_TTS_CREDITS_PER_CHARACTER),
            "providerId": provider_id,
            "model": model,
            "voice": voice,
            **(extra or {}),
        },
    )
    return SpeechTextBillingResult(
        charged=bool(result.charged),
        amount=result.amount,
        character_count=character_count,
        transaction_id=result.transaction_id,
    )
