"""Guards for the anonymous ticket entry point.

匿名写入路径的三条防护，缺一条都在真实站点上被利用过：

1. **蜜罐**：隐藏字段被填 => 静默接受、不建单。返回错误等于告诉对方这里有防护。
2. **按 IP 限流**：10 分钟 5 次。计数器用 `incr_with_ttl_strict`——它在 Redis 不可用时
   显式返回 `None`，调用方据此**拒绝**请求（fail closed）。best-effort 计数器
   （`incr()` 失败返回 0）在这里是错的：Redis 一挂，限流就等于没有。
3. **租户闸门**：主机解析不到租户、或该租户没开 support，一律 404（在 api 层）。
"""

from __future__ import annotations

from fastapi import Request

from app.core.exceptions import TooManyRequestsError
from app.infrastructure.cache.redis import get_redis_cache

from .constants import PUBLIC_SUBMIT_MAX_PER_WINDOW, PUBLIC_SUBMIT_WINDOW_SECONDS


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for", "") or "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def is_honeypot_hit(value: str | None) -> bool:
    return bool((value or "").strip())


async def enforce_public_submit_rate_limit(
    *,
    tenant_id: int,
    request: Request,
    limit: int = PUBLIC_SUBMIT_MAX_PER_WINDOW,
    window_seconds: int = PUBLIC_SUBMIT_WINDOW_SECONDS,
) -> int:
    """Raise ``TooManyRequestsError`` when the window is exhausted **or unknowable**."""
    key = f"support:public_submit:{tenant_id}:{client_ip(request)}"
    count = await get_redis_cache().incr_with_ttl_strict(key, ttl_seconds=window_seconds)
    if count is None:
        # 计数器不可用 = 没有限流。匿名写入路径宁可拒绝，也不能无防护放行。
        raise TooManyRequestsError(message="提交通道暂时不可用，请稍后再试")
    if count > limit:
        raise TooManyRequestsError(message="提交过于频繁，请稍后再试")
    return int(count)


__all__ = [
    "client_ip",
    "enforce_public_submit_rate_limit",
    "is_honeypot_hit",
]
