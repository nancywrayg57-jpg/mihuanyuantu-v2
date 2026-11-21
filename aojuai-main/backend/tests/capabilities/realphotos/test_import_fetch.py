"""API-type URL import fetch rewrite + allowlist."""

from __future__ import annotations

import httpx
import pytest

from app.capabilities.realphotos.services.import_fetch import (
    api_download_url,
    assert_import_url_allowed,
    extract_import_filename,
    fetch_import_bytes,
    host_allowlist_from_base_url,
)
from app.core.exceptions import BusinessError


def test_extract_accepts_static_and_api_paths():
    assert extract_import_filename("http://47.85.47.252/images/abc.png") == "abc.png"
    assert extract_import_filename("http://47.85.47.252/api/images/abc.png") == "abc.png"


def test_extract_rejects_bad_paths():
    with pytest.raises(BusinessError) as err:
        extract_import_filename("http://47.85.47.252/other/abc.png")
    assert err.value.code == "IMPORT_URL_REJECTED"


def test_api_download_url_rewrites():
    assert (
        api_download_url(base_url="http://47.85.47.252", filename="a.png")
        == "http://47.85.47.252/api/images/a.png"
    )


def test_allowlist_only_contract_host():
    hosts = host_allowlist_from_base_url("http://47.85.47.252")
    assert hosts == {"47.85.47.252"}
    with pytest.raises(BusinessError) as err:
        assert_import_url_allowed("https://evil.example/images/a.png", allowed_hosts=hosts)
    assert err.value.code == "IMPORT_URL_REJECTED"


@pytest.mark.asyncio
async def test_fetch_rewrites_static_to_api(monkeypatch):
    hosts = {"47.85.47.252"}
    seen: list[str] = []
    client_headers: dict[str, str] = {}

    class FakeResponse:
        status_code = 200
        content = b"fakepng-bytes-here!!"
        headers: dict[str, str] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            client_headers.clear()
            client_headers.update(kwargs.get("headers") or {})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            seen.append(str(url))
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    raw = await fetch_import_bytes(
        "http://47.85.47.252/images/f4.png",
        allowed_hosts=hosts,
        base_url="http://47.85.47.252",
    )
    assert raw.startswith(b"fakepng")
    assert seen == ["http://47.85.47.252/api/images/f4.png"]
    assert "X-API-Key" not in client_headers


@pytest.mark.asyncio
async def test_fetch_sends_x_api_key_when_provided(monkeypatch):
    hosts = {"47.85.47.252"}
    client_headers: dict[str, str] = {}

    class FakeResponse:
        status_code = 200
        content = b"fakepng-bytes-here!!"
        headers: dict[str, str] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            client_headers.clear()
            client_headers.update(kwargs.get("headers") or {})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    raw = await fetch_import_bytes(
        "http://47.85.47.252/api/images/f4.png",
        allowed_hosts=hosts,
        base_url="http://47.85.47.252",
        api_key="demo-import-key",
    )
    assert raw.startswith(b"fakepng")
    assert client_headers.get("X-API-Key") == "demo-import-key"

def test_missing_import_base_url_is_not_configured(monkeypatch):
    """SEC-F03：未配置时不得回落到硬编码公网地址。"""
    from app.capabilities.realphotos.services import import_fetch
    from app.core.config import settings

    monkeypatch.setattr(settings, "REALPHOTOS_IMPORT_BASE_URL", "")
    with pytest.raises(BusinessError) as err:
        import_fetch.default_import_base_url()
    assert err.value.code == "SERVICE_NOT_CONFIGURED"
