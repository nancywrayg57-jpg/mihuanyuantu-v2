"""
AOJU Backend - Neutral public-share helpers.

This module provides the minimum reusable substrate for public-link features
that can later be adopted by `nextjs-*` branches without forcing a shared
table design up front.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ForbiddenError
from app.core.security import hash_password, verify_password_cached

ShareModelT = TypeVar("ShareModelT")


def normalize_public_share_datetime(value: Any) -> datetime | None:
    """Normalize a share-related datetime-like value to timezone-aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _read_public_share_value(source: Any, name: str) -> Any:
    if isinstance(source, dict):
        return source.get(name) if name in source else None
    if hasattr(source, name):
        return getattr(source, name)
    return None


def extract_public_share_value(source: Any, *names: str) -> Any:
    for name in names:
        value = _read_public_share_value(source, name)
        if value is not None:
            return value
    return None


def pick_public_share_text(source: Any, *names: str) -> str | None:
    for name in names:
        value = _read_public_share_value(source, name)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def materialize_public_share_field_aliases(
    target: dict[str, Any],
    *,
    field_names: tuple[str, ...],
    source: Any | None = None,
    text_only: bool = False,
) -> dict[str, Any]:
    if not isinstance(target, dict) or not field_names:
        return target

    raw_source = target if source is None else source
    value = (
        pick_public_share_text(raw_source, *field_names)
        if text_only
        else extract_public_share_value(raw_source, *field_names)
    )
    if value is None:
        return target

    canonical = field_names[0]
    target[canonical] = value
    for alias in field_names[1:]:
        target.setdefault(alias, value)
    return target


def materialize_public_share_aliases(
    target: dict[str, Any],
    *,
    alias_groups: tuple[tuple[str, ...], ...],
    source: Any | None = None,
    text_only: bool = False,
) -> dict[str, Any]:
    for field_names in alias_groups:
        materialize_public_share_field_aliases(
            target,
            field_names=field_names,
            source=source,
            text_only=text_only,
        )
    return target


def build_optional_password_hash(password: str | None) -> str | None:
    raw = str(password or "").strip()
    return hash_password(raw) if raw else None


def apply_optional_password_hash(
    target: Any,
    *,
    password_in_payload: bool,
    password_value: str | None,
    password_attr: str = "password_hash",
) -> None:
    if not password_in_payload:
        return
    if password_value == "":
        setattr(target, password_attr, None)
        return
    if password_value is not None:
        setattr(target, password_attr, build_optional_password_hash(password_value))


async def generate_public_share_token(
    *,
    token_exists: Callable[[str], Awaitable[bool]],
    token_bytes: int = 32,
    attempts: int = 10,
    failure_message: str = "分享链接生成失败，请稍后重试",
    token_factory: Callable[[int], str] | None = None,
) -> str:
    factory = token_factory or secrets.token_urlsafe
    for _ in range(attempts):
        token = factory(token_bytes)
        if not await token_exists(token):
            return token
    raise BusinessError(message=failure_message)


async def get_public_share_by_token(
    db: AsyncSession,
    *,
    model: type[ShareModelT],
    token: str,
    options: list[Any] | None = None,
    token_attr: str = "token",
    deleted_attr: str = "deleted_at",
    active_attr: str | None = None,
) -> ShareModelT | None:
    normalized = str(token or "").strip()
    if not normalized:
        return None

    stmt = select(model).where(
        getattr(model, token_attr) == normalized,
        getattr(model, deleted_attr).is_(None),
    )
    if active_attr and hasattr(model, active_attr):
        stmt = stmt.where(getattr(model, active_attr) == True)  # noqa: E712 - SQLAlchemy boolean comparison
    if options:
        stmt = stmt.options(*options)

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def generate_model_public_share_token(
    db: AsyncSession,
    *,
    model: type[Any],
    token_attr: str = "token",
    deleted_attr: str = "deleted_at",
    token_bytes: int = 32,
    attempts: int = 10,
    failure_message: str = "分享链接生成失败，请稍后重试",
    token_factory: Callable[[int], str] | None = None,
) -> str:
    async def token_exists(token: str) -> bool:
        exists = await db.scalar(
            select(getattr(model, "id")).where(
                getattr(model, token_attr) == token,
                getattr(model, deleted_attr).is_(None),
            )
        )
        return bool(exists)

    return await generate_public_share_token(
        token_exists=token_exists,
        token_bytes=token_bytes,
        attempts=attempts,
        failure_message=failure_message,
        token_factory=token_factory,
    )


def _resolve_active_window(settings: Any) -> tuple[datetime | None, datetime | None]:
    if not isinstance(settings, dict):
        return None, None

    availability = settings.get("availability")
    availability = availability if isinstance(availability, dict) else {}

    active_from = (
        settings.get("activeFrom")
        or settings.get("active_from")
        or availability.get("activeFrom")
        or availability.get("active_from")
    )
    active_to = (
        settings.get("activeTo")
        or settings.get("active_to")
        or availability.get("activeTo")
        or availability.get("active_to")
    )

    return normalize_public_share_datetime(active_from), normalize_public_share_datetime(active_to)


def validate_public_share_access(
    share: Any,
    *,
    password: str | None,
    now: datetime | None = None,
    allow_active_window: bool = False,
    allow_expired: bool = False,
    active_attr: str = "is_active",
    deleted_attr: str = "deleted_at",
    expires_attrs: tuple[str, ...] = ("expires_at", "expire_time"),
    password_attrs: tuple[str, ...] = ("password_hash",),
    settings_attr: str = "settings",
) -> None:
    current_time = now or datetime.now(timezone.utc)

    if not bool(getattr(share, active_attr, False)) or getattr(share, deleted_attr, None) is not None:
        raise ForbiddenError(message="链接已停用")

    expires_at = normalize_public_share_datetime(extract_public_share_value(share, *expires_attrs))
    if expires_at and expires_at < current_time and not allow_expired:
        raise ForbiddenError(message="链接已过期")

    if allow_active_window:
        active_from, active_to = _resolve_active_window(getattr(share, settings_attr, None))
        if active_from and active_from > current_time:
            raise ForbiddenError(message="未到开放时间")
        if active_to and active_to < current_time and not allow_expired:
            raise ForbiddenError(message="链接已过期")

    password_hash = extract_public_share_value(share, *password_attrs)
    if password_hash:
        if not password:
            raise ForbiddenError(message="需要访问密码")
        if not verify_password_cached(password, str(password_hash)):
            raise ForbiddenError(message="访问密码错误")
