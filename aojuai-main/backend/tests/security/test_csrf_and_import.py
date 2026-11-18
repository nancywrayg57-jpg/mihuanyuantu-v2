"""SEC-E01 CSRF Origin 强制；SEC-F03 导入 Base URL。"""

from __future__ import annotations

import pytest
from fastapi import Request
from starlette.datastructures import Headers

from app.capabilities.realphotos.services import import_fetch
from app.core.csrf_protection import enforce_cookie_csrf
from app.core.exceptions import BusinessError, ForbiddenError


def _request(*, method: str = "POST", headers: dict[str, str] | None = None, cookies: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": "/api/v1/realphotos/x",
        "raw_path": b"/api/v1/realphotos/x",
        "query_string": b"",
        "headers": Headers({**(headers or {}), "host": "localhost"}).raw,
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 80),
    }
    req = Request(scope)
    if cookies:
        req._cookies = cookies  # noqa: SLF001 — test helper
    return req


def test_cookie_csrf_rejects_missing_origin(monkeypatch) -> None:
    from app.core import csrf_protection

    monkeypatch.setattr(csrf_protection, "get_access_cookie", lambda _r: "tok")
    monkeypatch.setattr(csrf_protection, "get_refresh_cookie", lambda _r: None)
    with pytest.raises(ForbiddenError):
        enforce_cookie_csrf(_request(headers={}))


def test_cookie_csrf_allows_same_origin(monkeypatch) -> None:
    from app.core import csrf_protection
    from app.core.config import settings

    monkeypatch.setattr(csrf_protection, "get_access_cookie", lambda _r: "tok")
    monkeypatch.setattr(csrf_protection, "get_refresh_cookie", lambda _r: None)
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost"])
    enforce_cookie_csrf(_request(headers={"origin": "http://localhost"}))


def test_import_base_url_requires_config(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "REALPHOTOS_IMPORT_BASE_URL", "")
    with pytest.raises(BusinessError) as err:
        import_fetch.default_import_base_url()
    assert err.value.code == "SERVICE_NOT_CONFIGURED"
