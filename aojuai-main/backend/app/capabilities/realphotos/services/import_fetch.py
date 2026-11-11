"""SSRF-safe fetch for staging image-host URL imports only."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.capabilities.realphotos.constants import MAX_UPLOAD_BYTES
from app.core.exceptions import BusinessError

DEFAULT_STAGING_HOST = "47.85.47.252"
IMPORT_FETCH_TIMEOUT_SECONDS = 30.0
MAX_REDIRECTS = 3


def host_allowlist_from_base_url(base_url: str) -> set[str]:
    hosts = {DEFAULT_STAGING_HOST}
    parsed = urlparse(str(base_url or "").strip())
    if parsed.hostname:
        hosts.add(parsed.hostname.lower())
    return hosts


def assert_import_url_allowed(url: str, *, allowed_hosts: set[str]) -> str:
    text = str(url or "").strip()
    if not text:
        raise BusinessError(message="缺少 url", code="INPUT_INVALID")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise BusinessError(message="仅允许 http/https", code="IMPORT_URL_REJECTED")
    host = (parsed.hostname or "").lower()
    if host not in {h.lower() for h in allowed_hosts}:
        raise BusinessError(message="URL 主机不在联调 allowlist", code="IMPORT_URL_REJECTED")
    path = parsed.path or ""
    if "/images/" not in path:
        raise BusinessError(message="联调图床仅允许 /images/ 路径", code="IMPORT_URL_REJECTED")
    if parsed.username or parsed.password:
        raise BusinessError(message="禁止带凭据的 URL", code="IMPORT_URL_REJECTED")
    return text


async def fetch_import_bytes(url: str, *, allowed_hosts: set[str]) -> bytes:
    current = assert_import_url_allowed(url, allowed_hosts=allowed_hosts)
    timeout = httpx.Timeout(IMPORT_FETCH_TIMEOUT_SECONDS, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            response = await client.get(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location") or ""
                if not location:
                    raise BusinessError(message="重定向缺少 Location", code="IMPORT_FETCH_FAILED")
                # Relative redirect → resolve against current.
                nxt = str(httpx.URL(current).join(location))
                current = assert_import_url_allowed(nxt, allowed_hosts=allowed_hosts)
                continue
            if response.status_code >= 400:
                raise BusinessError(
                    message=f"图床返回 HTTP {response.status_code}",
                    code="IMPORT_FETCH_FAILED",
                )
            raw = response.content
            if len(raw) > MAX_UPLOAD_BYTES:
                raise BusinessError(message="超过 20 MiB", code="UPLOAD_TOO_LARGE")
            if not raw:
                raise BusinessError(message="空文件", code="INPUT_INVALID")
            return raw
    raise BusinessError(message="重定向次数过多", code="IMPORT_FETCH_FAILED")
