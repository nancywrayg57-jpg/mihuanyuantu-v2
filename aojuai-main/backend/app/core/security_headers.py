from __future__ import annotations

from collections.abc import Mapping

from starlette.responses import Response

RELAXED_EMBED_PATH_PREFIXES = (
    "/share",
    "/share-groups",
    "/conversation-share",
    "/forms/share",
    "/reports/share",
    "/s",
    "/stage",
    "/appearance",
    "/assets",
    "/emojis",
    "/plugins",
    "/snippets",
    "/widgets",
    "/export",
    "/history",
    "/files",
)

BACKEND_HTML_CSP = "frame-ancestors 'self'; base-uri 'self'; object-src 'none'"
PERMISSIONS_POLICY = ", ".join(
    [
        "accelerometer=()",
        "browsing-topics=()",
        "geolocation=()",
        "gyroscope=()",
        "magnetometer=()",
        "payment=()",
        "usb=()",
    ]
)


def _normalize_path(path: str | None) -> str:
    value = str(path or "").strip()
    if not value:
        return "/"
    if value == "/":
        return value
    return value[:-1] if value.endswith("/") else value


def _matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def should_relax_embed_protection(path: str | None) -> bool:
    normalized = _normalize_path(path)
    return any(_matches_prefix(normalized, prefix) for prefix in RELAXED_EMBED_PATH_PREFIXES)


def _is_html_content_type(content_type: str | None) -> bool:
    return "text/html" in str(content_type or "").lower()


def _is_secure_request(*, headers: Mapping[str, str], scheme: str | None = None) -> bool:
    forwarded_proto = str(headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto == "https"
    return str(scheme or "").strip().lower() == "https"


def apply_security_headers(
    response: Response,
    *,
    request_path: str | None,
    request_headers: Mapping[str, str],
    request_scheme: str | None = None,
) -> Response:
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-DNS-Prefetch-Control", "off")
    response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)

    if _is_secure_request(headers=request_headers, scheme=request_scheme):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    if should_relax_embed_protection(request_path):
        if "X-Frame-Options" in response.headers:
            del response.headers["X-Frame-Options"]
        if "Content-Security-Policy" in response.headers:
            del response.headers["Content-Security-Policy"]
        return response

    if _is_html_content_type(response.headers.get("content-type")):
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Content-Security-Policy", BACKEND_HTML_CSP)

    return response
