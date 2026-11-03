from __future__ import annotations

from fastapi import Request, Response

from app.core.config import settings


def _normalize_forwarded_proto(value: str | None) -> str:
    return str(value or "").split(",", 1)[0].strip().lower()


def should_use_secure_auth_cookie(request: Request) -> bool:
    if settings.AUTH_COOKIE_SECURE is not None:
        secure = bool(settings.AUTH_COOKIE_SECURE)
    else:
        forwarded_proto = _normalize_forwarded_proto(request.headers.get("x-forwarded-proto"))
        secure = forwarded_proto == "https" if forwarded_proto else request.url.scheme == "https"

    if settings.AUTH_COOKIE_SAMESITE == "none":
        return True
    return secure


def get_access_cookie(request: Request) -> str | None:
    value = str(request.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME) or "").strip()
    return value or None


def get_refresh_cookie(request: Request) -> str | None:
    value = str(request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME) or "").strip()
    return value or None


def _cookie_domain() -> str | None:
    domain = str(settings.AUTH_COOKIE_DOMAIN or "").strip()
    return domain or None


def set_auth_cookies(
    response: Response,
    *,
    request: Request,
    access_token: str,
    refresh_token: str,
) -> None:
    secure = should_use_secure_auth_cookie(request)
    cookie_domain = _cookie_domain()
    access_max_age = max(int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES or 0), 1) * 60
    refresh_max_age = max(int(settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS or 0), 1) * 24 * 60 * 60

    response.set_cookie(
        key=settings.AUTH_ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=access_max_age,
        expires=access_max_age,
        path="/",
        domain=cookie_domain,
        secure=secure,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=refresh_max_age,
        expires=refresh_max_age,
        path="/api/v1/auth",
        domain=cookie_domain,
        secure=secure,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


def clear_auth_cookies(response: Response, *, request: Request) -> None:
    secure = should_use_secure_auth_cookie(request)
    cookie_domain = _cookie_domain()

    response.delete_cookie(
        key=settings.AUTH_ACCESS_COOKIE_NAME,
        path="/",
        domain=cookie_domain,
        secure=secure,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        domain=cookie_domain,
        secure=secure,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
