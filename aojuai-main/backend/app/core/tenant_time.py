from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth.models import Tenant

DEFAULT_TENANT_TIMEZONE = "UTC"


def is_valid_timezone(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        ZoneInfo(text)
        return True
    except Exception:
        return False


def normalize_tenant_timezone(value: Any, default: str = DEFAULT_TENANT_TIMEZONE) -> str:
    text = str(value or "").strip()
    if is_valid_timezone(text):
        return text
    return default


def validate_tenant_timezone(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timezone is required")
    if not is_valid_timezone(text):
        raise ValueError("invalid timezone")
    return text


def resolve_tenant_timezone_from_config(config: dict[str, Any] | None, default: str = DEFAULT_TENANT_TIMEZONE) -> str:
    source = config if isinstance(config, dict) else {}
    for key in ("timezone", "timeZone", "tz"):
        value = source.get(key)
        if is_valid_timezone(str(value or "").strip()):
            return str(value).strip()
    return default


def tenant_now(timezone_name: str, now_utc: datetime | None = None) -> datetime:
    tz_name = normalize_tenant_timezone(timezone_name)
    current = now_utc or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(ZoneInfo(tz_name))


def tenant_today(timezone_name: str, now_utc: datetime | None = None) -> date:
    return tenant_now(timezone_name, now_utc).date()


async def get_tenant_timezone(
    db: AsyncSession,
    *,
    tenant_id: int,
    default: str = DEFAULT_TENANT_TIMEZONE,
) -> str:
    config = await db.scalar(
        select(Tenant.config).where(
            Tenant.id == tenant_id,
            Tenant.deleted_at.is_(None),
        )
    )
    return resolve_tenant_timezone_from_config(config, default=default)


async def get_tenant_today(
    db: AsyncSession,
    *,
    tenant_id: int,
    default_timezone: str = DEFAULT_TENANT_TIMEZONE,
) -> date:
    tz_name = await get_tenant_timezone(db, tenant_id=tenant_id, default=default_timezone)
    return tenant_today(tz_name)
