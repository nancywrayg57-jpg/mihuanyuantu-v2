"""
AOJU Backend - Redis Cache Helpers

Best-effort cache wrapper:
- Redis failures must not break request handling.
- JSON payloads are stored as opaque bytes.
- Version keys use Redis INCR to avoid wildcard deletes.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import orjson
from redis.asyncio import Redis

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class RedisJsonCache:
    """Small async Redis helper focused on JSON + integer version keys."""

    def __init__(self) -> None:
        if not settings.REDIS_ENABLED_EFFECTIVE:
            # 轻量档：Redis 关闭，所有操作按"未命中"处理（get→None / incr→0），不发起连接
            self._client = None
            return
        self._client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            socket_timeout=1.5,
            socket_connect_timeout=1.5,
            health_check_interval=30,
        )

    @staticmethod
    def _ns(key: str) -> str:
        # 实例命名空间：同机多实例共享 Redis 时防跨实例键碰撞（版本键 INCR 互相干扰等）
        return f"ns:{settings.CACHE_NAMESPACE}:{key}"

    async def get_json(self, key: str) -> Any | None:
        if self._client is None:
            return
        key = self._ns(key)
        try:
            payload = await self._client.get(key)
        except Exception:
            logger.warning("redis_cache_get_failed", key=key, exc_info=True)
            return None

        if not payload:
            return None

        try:
            return orjson.loads(payload)
        except Exception:
            logger.warning("redis_cache_decode_failed", key=key, exc_info=True)
            return None

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        if self._client is None:
            return
        key = self._ns(key)
        try:
            payload = orjson.dumps(value)
            await self._client.set(key, payload, ex=max(1, int(ttl_seconds)))
        except Exception:
            logger.warning("redis_cache_set_failed", key=key, ttl_seconds=ttl_seconds, exc_info=True)

    async def get_int(self, key: str, *, default: int = 0) -> int:
        if self._client is None:
            return int(default)
        key = self._ns(key)
        try:
            value = await self._client.get(key)
        except Exception:
            logger.warning("redis_cache_get_int_failed", key=key, exc_info=True)
            return int(default)

        if value is None:
            return int(default)

        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning("redis_cache_invalid_int", key=key, value=value)
            return int(default)

    async def get_ints(self, keys: list[str], *, default: int = 0) -> list[int]:
        if self._client is None:
            return [int(default) for _ in keys]
        if not keys:
            return []

        keys = [self._ns(key) for key in keys]
        try:
            values = await self._client.mget(keys)
        except Exception:
            logger.warning("redis_cache_mget_failed", keys=keys, exc_info=True)
            return [int(default) for _ in keys]

        result: list[int] = []
        for key, value in zip(keys, values, strict=False):
            if value is None:
                result.append(int(default))
                continue
            try:
                result.append(int(value))
            except (TypeError, ValueError):
                logger.warning("redis_cache_invalid_int", key=key, value=value)
                result.append(int(default))
        return result

    async def incr(self, key: str) -> int:
        if self._client is None:
            return 0
        key = self._ns(key)
        try:
            value = await self._client.incr(key)
            return int(value)
        except Exception:
            logger.warning("redis_cache_incr_failed", key=key, exc_info=True)
            return 0

    async def incr_with_ttl_strict(self, key: str, *, ttl_seconds: int) -> int | None:
        """Atomically increment a window counter, failing explicitly when Redis is unavailable.

        Most cache callers deliberately treat Redis as best-effort. Security-sensitive public
        write flows cannot do that: ``None`` tells the caller to reject the request rather than
        silently removing its rate limit.
        """

        if self._client is None:
            return None
        namespaced_key = self._ns(key)
        script = (
            "local value = redis.call('INCR', KEYS[1]); "
            "if value == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
            "return value"
        )
        try:
            value = await self._client.eval(
                script,
                1,
                namespaced_key,
                max(1, int(ttl_seconds)),
            )
            return int(value)
        except Exception:
            logger.warning(
                "redis_cache_strict_incr_failed",
                key=namespaced_key,
                ttl_seconds=ttl_seconds,
                exc_info=True,
            )
            return None

    async def close(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.aclose()
        except Exception:
            logger.warning("redis_cache_close_failed", exc_info=True)


@lru_cache(maxsize=1)
def get_redis_cache() -> RedisJsonCache:
    return RedisJsonCache()


async def close_redis_cache() -> None:
    cache = get_redis_cache()
    await cache.close()
    get_redis_cache.cache_clear()
