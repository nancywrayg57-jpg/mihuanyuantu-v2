from __future__ import annotations

import hmac
import ipaddress
from collections.abc import Mapping

from app.core.exceptions import ForbiddenError

PROXY_SECRET_HEADER = "x-aoju-proxy-key"
_LOCAL_TEST_HOSTS = {"testclient", "testserver"}
_LOCAL_HOST_ALIASES = {"localhost", *_LOCAL_TEST_HOSTS}


def _normalize_host(value: str | None) -> str:
    host = str(value or "").strip().lower()
    if not host:
        return ""

    if "," in host:
        host = host.split(",", 1)[0].strip()

    if host.startswith("[") and "]" in host:
        return host[1 : host.index("]")]

    if host.count(":") == 1:
        candidate, port = host.rsplit(":", 1)
        if port.isdigit():
            return candidate.strip()

    return host


def _is_loopback_host(value: str | None) -> bool:
    host = _normalize_host(value)
    if not host:
        return False
    if host in _LOCAL_HOST_ALIASES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def normalize_host(value: str | None) -> str:
    """Return the normalized hostname used by proxy and public-site checks."""
    return _normalize_host(value)


def is_loopback_host(value: str | None) -> bool:
    return _is_loopback_host(value)


def is_forwarded_host_trusted(
    *,
    headers: Mapping[str, str],
    client_host: str | None,
    shared_secret: str | None,
    is_pytest: bool = False,
) -> bool:
    """Whether this request may use ``x-forwarded-host`` as its authority.

    A forwarded host is authority-bearing data, so the header is ignored when
    the existing trusted-proxy proof is absent.  Local-to-local requests keep
    the same bypass semantics as ``enforce_trusted_proxy``.
    """
    forwarded_host = _normalize_host(headers.get("x-forwarded-host"))
    if not forwarded_host:
        return False

    if should_bypass_trusted_proxy(
        client_host=client_host,
        requested_host=forwarded_host,
        is_pytest=is_pytest,
    ):
        return True

    secret = str(shared_secret or "").strip()
    provided = str(headers.get(PROXY_SECRET_HEADER) or "").strip()
    return bool(secret and provided and hmac.compare_digest(provided, secret))


def resolve_requested_host(*, headers: Mapping[str, str], fallback_host: str | None = None) -> str:
    forwarded_host = str(headers.get("x-forwarded-host") or "").strip()
    host = forwarded_host or str(headers.get("host") or "").strip() or str(fallback_host or "").strip()
    return _normalize_host(host)


def should_bypass_trusted_proxy(
    *,
    client_host: str | None,
    requested_host: str | None,
    is_pytest: bool = False,
) -> bool:
    normalized_requested = _normalize_host(requested_host)
    if is_pytest and normalized_requested in {"", *_LOCAL_TEST_HOSTS}:
        return True
    return _is_loopback_host(client_host) and _is_loopback_host(normalized_requested)


def enforce_trusted_proxy(
    *,
    headers: Mapping[str, str],
    client_host: str | None,
    requested_host: str | None,
    shared_secret: str | None,
    is_pytest: bool = False,
) -> None:
    secret = str(shared_secret or "").strip()
    if not secret:
        return

    if should_bypass_trusted_proxy(
        client_host=client_host,
        requested_host=requested_host,
        is_pytest=is_pytest,
    ):
        return

    provided = str(headers.get(PROXY_SECRET_HEADER) or "").strip()
    if provided and hmac.compare_digest(provided, secret):
        return

    raise ForbiddenError(message="请求来源未通过受信代理校验")
