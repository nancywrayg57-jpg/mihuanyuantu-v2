from __future__ import annotations

import pytest

from app.core.exceptions import ForbiddenError
from app.core.trusted_proxy import enforce_trusted_proxy, resolve_requested_host, should_bypass_trusted_proxy


def test_should_bypass_trusted_proxy_for_local_loopback_request() -> None:
    assert should_bypass_trusted_proxy(
        client_host="127.0.0.1",
        requested_host="127.0.0.1:8000",
    )


def test_should_not_bypass_trusted_proxy_for_public_host_via_local_proxy() -> None:
    assert not should_bypass_trusted_proxy(
        client_host="127.0.0.1",
        requested_host="nextjs-base.example.test",
    )


def test_should_bypass_trusted_proxy_in_pytest_for_testclient_host() -> None:
    assert should_bypass_trusted_proxy(
        client_host="testclient",
        requested_host="testserver",
        is_pytest=True,
    )


def test_resolve_requested_host_prefers_forwarded_host_and_strips_port() -> None:
    assert (
        resolve_requested_host(
            headers={"x-forwarded-host": "nextjs-base.example.test:443", "host": "127.0.0.1:8000"},
            fallback_host="127.0.0.1",
        )
        == "nextjs-base.example.test"
    )


def test_enforce_trusted_proxy_accepts_valid_proxy_secret() -> None:
    enforce_trusted_proxy(
        headers={"x-aoju-proxy-key": "secret-value"},
        client_host="127.0.0.1",
        requested_host="nextjs-base.example.test",
        shared_secret="secret-value",
    )


def test_enforce_trusted_proxy_rejects_public_request_without_proxy_secret() -> None:
    with pytest.raises(ForbiddenError, match="受信代理"):
        enforce_trusted_proxy(
            headers={},
            client_host="127.0.0.1",
            requested_host="nextjs-base.example.test",
            shared_secret="secret-value",
        )
