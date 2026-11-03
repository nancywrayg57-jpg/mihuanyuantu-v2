"""Cache-Control helpers for public / shared responses.

内核只提供工具与两个通用常量；具体业务路径的缓存策略由调用方决定，
不要在这里堆积业务专用常量。
"""

from __future__ import annotations

from collections.abc import Mapping

from starlette.responses import Response

PUBLIC_SITE_CONFIG_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=600"
PUBLIC_SHARE_INFO_CACHE_CONTROL = "public, max-age=30, stale-while-revalidate=60"


def apply_cache_control(
    response: Response,
    cache_control: str,
    *,
    vary: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> Response:
    response.headers["Cache-Control"] = cache_control
    if vary:
        response.headers["Vary"] = vary
    if extra_headers:
        for key, value in extra_headers.items():
            response.headers[key] = value
    return response
