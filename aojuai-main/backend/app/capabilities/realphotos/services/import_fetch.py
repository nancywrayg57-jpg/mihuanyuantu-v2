"""SSRF-safe fetch for API-type URL import suppliers.

Merchant may paste ``/images/<file>`` or ``/api/images/<file>`` URLs; the runtime
always downloads via ``GET {base}/api/images/<file>``.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

from app.capabilities.realphotos.constants import MAX_UPLOAD_BYTES
from app.core.config import settings
from app.core.exceptions import BusinessError

IMPORT_FETCH_TIMEOUT_SECONDS = 30.0
MAX_REDIRECTS = 3

_FILENAME_RE = re.compile(
    r"^(?:/api)?/images/(?P<name>[A-Za-z0-9._-]+)$",
)


def default_import_base_url() -> str:
    """SEC-F03：未配置 REALPHOTOS_IMPORT_BASE_URL 时拒绝隐式出站。"""
    raw = str(getattr(settings, "REALPHOTOS_IMPORT_BASE_URL", "") or "").strip()
    if raw:
        return raw.rstrip("/")
    raise BusinessError(
        message="未配置导入供应商 Base URL（REALPHOTOS_IMPORT_BASE_URL）",
        code="SERVICE_NOT_CONFIGURED",
    )


def normalize_import_base_url(base_url: str | None) -> str:
    text = str(base_url or "").strip()
    if not text:
        text = default_import_base_url()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise BusinessError(message="导入供应商 Base URL 无效", code="SERVICE_NOT_CONFIGURED")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def host_allowlist_from_base_url(base_url: str) -> set[str]:
    """Allow only the configured supplier host (env default when base empty)."""
    normalized = normalize_import_base_url(base_url)
    host = (urlparse(normalized).hostname or "").lower()
    if not host:
        raise BusinessError(message="导入供应商 Base URL 无效", code="SERVICE_NOT_CONFIGURED")
    return {host}


def extract_import_filename(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        raise BusinessError(message="缺少 url", code="INPUT_INVALID")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise BusinessError(message="仅允许 http/https", code="IMPORT_URL_REJECTED")
    if parsed.username or parsed.password:
        raise BusinessError(message="禁止带凭据的 URL", code="IMPORT_URL_REJECTED")
    path = parsed.path or ""
    match = _FILENAME_RE.match(path)
    if match is None:
        raise BusinessError(
            message="仅允许 /images/<文件名> 或 /api/images/<文件名>",
            code="IMPORT_URL_REJECTED",
        )
    name = str(match.group("name") or "").strip()
    if not name or "/" in name or ".." in name:
        raise BusinessError(message="文件名无效", code="IMPORT_URL_REJECTED")
    return name


def assert_import_url_allowed(url: str, *, allowed_hosts: set[str]) -> str:
    """Validate pasted URL host + path; return original text (not the rewrite)."""
    text = str(url or "").strip()
    extract_import_filename(text)
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if host not in {h.lower() for h in allowed_hosts}:
        raise BusinessError(message="URL 主机不在导入供应商 allowlist", code="IMPORT_URL_REJECTED")
    return text


def api_download_url(*, base_url: str, filename: str) -> str:
    base = normalize_import_base_url(base_url)
    return urljoin(f"{base}/", f"api/images/{filename}")


def _assert_host_allowed(url: str, *, allowed_hosts: set[str]) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in {h.lower() for h in allowed_hosts}:
        raise BusinessError(message="URL 主机不在导入供应商 allowlist", code="IMPORT_URL_REJECTED")


async def fetch_import_bytes(
    url: str,
    *,
    allowed_hosts: set[str],
    base_url: str | None = None,
) -> bytes:
    """Fetch image bytes via the supplier API path, not the pasted URL verbatim."""
    assert_import_url_allowed(url, allowed_hosts=allowed_hosts)
    filename = extract_import_filename(url)
    current = api_download_url(base_url=base_url or default_import_base_url(), filename=filename)
    _assert_host_allowed(current, allowed_hosts=allowed_hosts)

    timeout = httpx.Timeout(IMPORT_FETCH_TIMEOUT_SECONDS, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            response = await client.get(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location") or ""
                if not location:
                    raise BusinessError(message="重定向缺少 Location", code="IMPORT_FETCH_FAILED")
                nxt = str(httpx.URL(current).join(location))
                _assert_host_allowed(nxt, allowed_hosts=allowed_hosts)
                # Keep API rewrite after redirect (static → api).
                current = api_download_url(
                    base_url=f"{urlparse(nxt).scheme}://{urlparse(nxt).netloc}",
                    filename=extract_import_filename(nxt),
                )
                continue
            if response.status_code >= 400:
                raise BusinessError(
                    message=f"导入供应商返回 HTTP {response.status_code}",
                    code="IMPORT_FETCH_FAILED",
                )
            raw = response.content
            if len(raw) > MAX_UPLOAD_BYTES:
                raise BusinessError(message="超过 20 MiB", code="UPLOAD_TOO_LARGE")
            if not raw:
                raise BusinessError(message="空文件", code="INPUT_INVALID")
            return raw
    raise BusinessError(message="重定向次数过多", code="IMPORT_FETCH_FAILED")
