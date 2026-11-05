from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.tenant_time import (
    normalize_tenant_timezone,
    resolve_tenant_timezone_from_config,
    tenant_today,
    validate_tenant_timezone,
)


def test_normalize_tenant_timezone() -> None:
    assert normalize_tenant_timezone("Asia/Shanghai") == "Asia/Shanghai"
    assert normalize_tenant_timezone("invalid/tz") == "UTC"
    assert normalize_tenant_timezone("") == "UTC"


def test_validate_tenant_timezone() -> None:
    assert validate_tenant_timezone("America/Los_Angeles") == "America/Los_Angeles"
    with pytest.raises(ValueError):
        validate_tenant_timezone("bad-zone")


def test_resolve_tenant_timezone_from_config() -> None:
    assert resolve_tenant_timezone_from_config({"timezone": "Asia/Shanghai"}) == "Asia/Shanghai"
    assert resolve_tenant_timezone_from_config({"timeZone": "America/New_York"}) == "America/New_York"
    assert resolve_tenant_timezone_from_config({"tz": "Europe/London"}) == "Europe/London"
    assert resolve_tenant_timezone_from_config({"timezone": "invalid"}) == "UTC"


def test_tenant_today_respects_timezone_boundary() -> None:
    utc_now = datetime(2026, 2, 23, 1, 30, tzinfo=UTC)
    assert tenant_today("Asia/Shanghai", now_utc=utc_now).isoformat() == "2026-02-23"
    assert tenant_today("America/Los_Angeles", now_utc=utc_now).isoformat() == "2026-02-22"
