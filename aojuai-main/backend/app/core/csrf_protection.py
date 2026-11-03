from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from fastapi import Request

from app.core.auth_cookies import get_access_cookie, get_refresh_cookie
from app.core.config import settings
from app.core.exceptions import ForbiddenError

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _normalize_origin(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.lower() == "null":
        return "null"

    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    hostname = str(parsed.hostname or "").strip().lower()
    if not hostname:
        return ""

    scheme = str(parsed.scheme or "").strip().lower()
    port = parsed.port
    if not scheme:
        scheme = "https" if port == 443 else "http"

    default_port = 443 if scheme == "https" else 80 if scheme == "http" else None
    if port and port != default_port:
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{hostname}"


def _resolve_request_origin(request: Request) -> str:
    forwarded_host = str(request.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip()
    host = forwarded_host or str(request.headers.get("host") or "").strip()
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    scheme = forwarded_proto or str(request.url.scheme or "").strip().lower() or "http"
    if host:
        return _normalize_origin(f"{scheme}://{host}")
    return _normalize_origin(str(request.base_url).rstrip("/"))


def _normalize_allowed_origins(origins: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for origin in origins:
        value = _normalize_origin(origin)
        if value and value != "null":
            normalized.add(value)
    return normalized


def get_allowed_csrf_origins(request: Request) -> set[str]:
    allowed = _normalize_allowed_origins(settings.CORS_ORIGINS)
    request_origin = _resolve_request_origin(request)
    if request_origin:
        allowed.add(request_origin)
    return allowed


def _extract_source_origin(request: Request) -> str:
    origin = _normalize_origin(request.headers.get("origin"))
    if origin:
        return origin
    return _normalize_origin(request.headers.get("referer"))


def has_bearer_authorization(request: Request) -> bool:
    authorization = str(request.headers.get("authorization") or "").strip().lower()
    return authorization.startswith("bearer ")


def uses_auth_cookies(request: Request) -> bool:
    return bool(get_access_cookie(request) or get_refresh_cookie(request))


def should_enforce_cookie_csrf(request: Request) -> bool:
    if str(request.method or "").upper() in SAFE_METHODS:
        return False
    if has_bearer_authorization(request):
        return False
    return uses_auth_cookies(request)


def enforce_cookie_csrf(request: Request) -> None:
    if not should_enforce_cookie_csrf(request):
        return

    fetch_site = str(request.headers.get("sec-fetch-site") or "").strip().lower()
    if fetch_site == "cross-site":
        raise ForbiddenError(message="跨站请求已被拒绝，请从当前站点重新发起操作")

    source_origin = _extract_source_origin(request)
    if not source_origin:
        return
    if source_origin == "null":
        raise ForbiddenError(message="请求来源无效，请刷新页面后重试")
    if source_origin not in get_allowed_csrf_origins(request):
        raise ForbiddenError(message="请求来源无效，请刷新页面后重试")
