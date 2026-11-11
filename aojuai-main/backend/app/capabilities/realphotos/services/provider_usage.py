"""Call-time upstream usage metering. Never derive cost from customer credits."""

from __future__ import annotations

import json
import secrets
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.models.provider_usage import RealphotosProviderUsage
from app.core.config import settings


def _parse_unit_costs() -> dict[str, dict[str, Any]]:
    raw = str(getattr(settings, "REALPHOTOS_UNIT_COSTS_JSON", "") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        out[str(key)] = value
    return out


def lookup_unit_price(*, duty: str, model_id: str) -> dict[str, Any] | None:
    table = _parse_unit_costs()
    model = str(model_id or "").strip()
    for key in (f"{duty}|{model}", duty, f"{duty}|*"):
        row = table.get(key)
        if row is not None:
            return row
    return None


class RealphotosProviderUsageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_call(
        self,
        *,
        duty: str,
        provider: str,
        model_id: str,
        config_version: str = "",
        tenant_id: int | None = None,
        units: Decimal | float | int = 1,
        unit_name: str = "call",
        trace_id: str | None = None,
        request_id: str | None = None,
        task_id: int | None = None,
        attempt_id: int | None = None,
        note: str = "",
        fixture: bool = False,
    ) -> RealphotosProviderUsage | None:
        """Write one usage row for a real upstream attempt.

        Fixture / non-egress paths must pass fixture=True and are skipped
        (never recorded as known cost).
        """
        if fixture:
            return None
        price = lookup_unit_price(duty=str(duty), model_id=str(model_id or ""))
        try:
            unit_qty = Decimal(str(units))
        except (InvalidOperation, ValueError):
            unit_qty = Decimal("1")
        unit_cost: Decimal | None = None
        amount: Decimal | None = None
        currency = "CNY"
        if price is None:
            cost_status = "unavailable"
        else:
            raw_cost = price.get("unit_cost", price.get("unitCost"))
            if raw_cost is None or str(raw_cost).strip() == "":
                cost_status = "unavailable"
            else:
                try:
                    unit_cost = Decimal(str(raw_cost))
                    amount = unit_cost * unit_qty
                    cost_status = "known"
                    currency = str(price.get("currency") or "CNY")
                    unit_name = str(price.get("unit_name") or price.get("unitName") or unit_name)
                except (InvalidOperation, ValueError):
                    cost_status = "unknown"
                    unit_cost = None
                    amount = None
        row = RealphotosProviderUsage(
            tenant_id=int(tenant_id or 0),
            duty=str(duty),
            provider=str(provider or ""),
            model_id=str(model_id or ""),
            config_version=str(config_version or ""),
            trace_id=str(trace_id or secrets.token_hex(8)),
            request_id=str(request_id or secrets.token_hex(8)),
            units=unit_qty,
            unit_name=str(unit_name or "call"),
            unit_cost=unit_cost,
            currency=currency,
            amount=amount,
            cost_status=cost_status,
            task_id=int(task_id) if task_id is not None else None,
            attempt_id=int(attempt_id) if attempt_id is not None else None,
            note=str(note or ""),
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def ops_cost_summary(self) -> dict[str, Any]:
        """Aggregate known amounts; never invent 0 when price/call missing."""
        rows = (
            await self.db.execute(
                select(RealphotosProviderUsage).where(RealphotosProviderUsage.deleted_at.is_(None))
            )
        ).scalars().all()
        known_amount = Decimal("0")
        known_count = 0
        unknown_count = 0
        unavailable_count = 0
        for row in rows:
            status = str(row.cost_status or "")
            if status == "known" and row.amount is not None:
                known_amount += Decimal(str(row.amount))
                known_count += 1
            elif status == "unknown":
                unknown_count += 1
            else:
                unavailable_count += 1
        total_rows = known_count + unknown_count + unavailable_count
        if known_count > 0:
            return {
                "cost": float(known_amount),
                "costReason": None,
                "costKnownAmount": float(known_amount),
                "costKnownCount": known_count,
                "costUnknownCount": unknown_count + unavailable_count,
                "costSource": "cap_realphotos_provider_usage.amount where cost_status=known",
                "creditsNotUsed": True,
            }
        if total_rows == 0:
            return {
                "cost": None,
                "costReason": "no_upstream_calls",
                "costKnownAmount": None,
                "costKnownCount": 0,
                "costUnknownCount": 0,
                "costSource": "cap_realphotos_provider_usage",
                "creditsNotUsed": True,
            }
        return {
            "cost": None,
            "costReason": "unit_price_missing",
            "costKnownAmount": None,
            "costKnownCount": 0,
            "costUnknownCount": unknown_count + unavailable_count,
            "costSource": "cap_realphotos_provider_usage",
            "creditsNotUsed": True,
        }

    async def count_rows(self) -> int:
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(RealphotosProviderUsage)
                .where(RealphotosProviderUsage.deleted_at.is_(None))
            )
            or 0
        )
