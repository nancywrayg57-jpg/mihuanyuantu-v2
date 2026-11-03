from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.exceptions import BusinessError, ForbiddenError
from app.core.public_share import (
    apply_optional_password_hash,
    build_optional_password_hash,
    extract_public_share_value,
    generate_model_public_share_token,
    generate_public_share_token,
    get_public_share_by_token,
    materialize_public_share_aliases,
    materialize_public_share_field_aliases,
    normalize_public_share_datetime,
    pick_public_share_text,
    validate_public_share_access,
)
from app.core.security import verify_password


class _Base(DeclarativeBase):
    pass


class _TokenShare(_Base):
    __tablename__ = "test_public_share_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class _LegacyCodeShare(_Base):
    __tablename__ = "test_public_share_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    share_code: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def test_normalize_public_share_datetime_handles_iso_and_naive_datetime() -> None:
    naive = datetime(2026, 3, 21, 12, 0, 0)
    iso = "2026-03-21T12:00:00Z"

    normalized_naive = normalize_public_share_datetime(naive)
    normalized_iso = normalize_public_share_datetime(iso)

    assert normalized_naive is not None
    assert normalized_naive.tzinfo == timezone.utc
    assert normalized_iso == datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_generate_public_share_token_retries_until_unique() -> None:
    checker = AsyncMock(side_effect=[True, False])

    token = await generate_public_share_token(
        token_exists=checker,
        token_bytes=8,
        attempts=2,
    )

    assert isinstance(token, str)
    assert token
    assert checker.await_count == 2


@pytest.mark.asyncio
async def test_generate_public_share_token_raises_after_retry_budget() -> None:
    checker = AsyncMock(return_value=True)

    with pytest.raises(BusinessError, match="分享链接生成失败"):
        await generate_public_share_token(
            token_exists=checker,
            token_bytes=8,
            attempts=2,
        )


class _DummyResult:
    def __init__(self, *, scalar_value=None):  # noqa: ANN001
        self._scalar_value = scalar_value

    def scalar_one_or_none(self):  # noqa: ANN201
        return self._scalar_value


@pytest.mark.asyncio
async def test_get_public_share_by_token_returns_match_and_skips_blank_tokens() -> None:
    share = SimpleNamespace(id=1, token="share-1")
    db = SimpleNamespace(execute=AsyncMock(return_value=_DummyResult(scalar_value=share)))

    result = await get_public_share_by_token(
        db,
        model=_TokenShare,
        token=" share-1 ",
        active_attr="is_active",
    )

    assert result is share
    assert await get_public_share_by_token(db, model=_TokenShare, token="   ") is None


@pytest.mark.asyncio
async def test_generate_model_public_share_token_supports_legacy_token_field_name() -> None:
    db = SimpleNamespace(scalar=AsyncMock(side_effect=[1, None]))

    token = await generate_model_public_share_token(
        db,
        model=_LegacyCodeShare,
        token_attr="share_code",
        token_bytes=8,
        attempts=2,
        token_factory=lambda _bytes: "dup-code" if db.scalar.await_count == 0 else "fresh-code",
    )

    assert token == "fresh-code"
    assert db.scalar.await_count == 2


def test_apply_optional_password_hash_sets_and_clears_password_hash() -> None:
    target = SimpleNamespace(password_hash=None)

    apply_optional_password_hash(
        target,
        password_in_payload=True,
        password_value="secret",
    )
    assert target.password_hash
    assert verify_password("secret", target.password_hash)

    apply_optional_password_hash(
        target,
        password_in_payload=True,
        password_value="",
    )
    assert target.password_hash is None


def test_build_optional_password_hash_returns_none_for_blank_password() -> None:
    assert build_optional_password_hash(None) is None
    assert build_optional_password_hash("   ") is None


def test_public_share_alias_helpers_extract_and_materialize_values() -> None:
    source = {
        "publicToken": " public-123 ",
        "publicExpiry": "2026-03-21T12:00:00Z",
    }
    target: dict[str, str] = {}

    assert extract_public_share_value(source, "token", "publicToken") == " public-123 "
    assert pick_public_share_text(source, "token", "publicToken") == "public-123"

    materialize_public_share_field_aliases(
        target,
        field_names=("token", "public_token", "publicToken"),
        source=source,
        text_only=True,
    )
    materialize_public_share_aliases(
        target,
        alias_groups=(
            ("expires_at", "expiresAt", "public_expiry", "publicExpiry"),
        ),
        source=source,
        text_only=True,
    )

    assert target["token"] == "public-123"
    assert target["public_token"] == "public-123"
    assert target["publicToken"] == "public-123"
    assert target["expires_at"] == "2026-03-21T12:00:00Z"
    assert target["expiresAt"] == "2026-03-21T12:00:00Z"
    assert target["public_expiry"] == "2026-03-21T12:00:00Z"
    assert target["publicExpiry"] == "2026-03-21T12:00:00Z"


def test_validate_public_share_access_blocks_wrong_password() -> None:
    share = SimpleNamespace(
        is_active=True,
        deleted_at=None,
        expires_at=None,
        password_hash=build_optional_password_hash("secret"),
        settings={},
    )

    with pytest.raises(ForbiddenError, match="访问密码错误"):
        validate_public_share_access(share, password="bad")


def test_validate_public_share_access_blocks_before_active_window() -> None:
    active_from = datetime.now(timezone.utc) + timedelta(hours=2)
    share = SimpleNamespace(
        is_active=True,
        deleted_at=None,
        expires_at=None,
        password_hash=None,
        settings={"activeFrom": active_from.isoformat()},
    )

    with pytest.raises(ForbiddenError, match="未到开放时间"):
        validate_public_share_access(
            share,
            password=None,
            allow_active_window=True,
        )


def test_validate_public_share_access_can_allow_expired_end_times() -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    share = SimpleNamespace(
        is_active=True,
        deleted_at=None,
        expires_at=past,
        password_hash=build_optional_password_hash("secret"),
        settings={"activeTo": past.isoformat()},
    )

    validate_public_share_access(
        share,
        password="secret",
        allow_active_window=True,
        allow_expired=True,
    )


@pytest.mark.parametrize(
    ("share_overrides", "password", "error_message"),
    [
        ({"is_active": False}, "secret", "链接已停用"),
        ({"deleted_at": datetime.now(timezone.utc)}, "secret", "链接已停用"),
        ({"password_hash": build_optional_password_hash("secret")}, "bad", "访问密码错误"),
        (
            {"settings": {"activeFrom": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}},
            "secret",
            "未到开放时间",
        ),
    ],
)
def test_allow_expired_does_not_bypass_other_access_controls(
    share_overrides: dict[str, object],
    password: str,
    error_message: str,
) -> None:
    share_values: dict[str, object] = {
        "is_active": True,
        "deleted_at": None,
        "expires_at": datetime.now(timezone.utc) - timedelta(hours=2),
        "password_hash": build_optional_password_hash("secret"),
        "settings": {},
    }
    share_values.update(share_overrides)

    with pytest.raises(ForbiddenError, match=error_message):
        validate_public_share_access(
            SimpleNamespace(**share_values),
            password=password,
            allow_active_window=True,
            allow_expired=True,
        )


def test_validate_public_share_access_supports_legacy_expire_and_password_field_names() -> None:
    share = SimpleNamespace(
        is_active=True,
        deleted_at=None,
        expire_time=datetime.now(timezone.utc) + timedelta(hours=1),
        password=build_optional_password_hash("secret"),
        settings={},
    )

    validate_public_share_access(
        share,
        password="secret",
        expires_attrs=("expires_at", "expire_time"),
        password_attrs=("password_hash", "password"),
    )
