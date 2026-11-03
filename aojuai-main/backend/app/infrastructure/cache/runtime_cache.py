"""Optional runtime cache with Redis and in-process fallback."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_LOCAL_CACHE_MAX_ITEMS = 2048
_REDIS_RETRY_BACKOFF_SECONDS = 5.0
_REDIS_SOCKET_TIMEOUT_SECONDS = 1.0
_local_cache: dict[str, tuple[float, Any]] = {}
_local_cache_lock = asyncio.Lock()
_remember_locks: dict[str, asyncio.Lock] = {}
_redis_client: Any | None = None
_redis_initialized = False
_redis_init_lock = asyncio.Lock()
_redis_failure_logged = False
_redis_retry_after = 0.0


def _now() -> float:
    return time.monotonic()


async def _local_get(key: str) -> Any | None:
    async with _local_cache_lock:
        entry = _local_cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= _now():
            _local_cache.pop(key, None)
            return None
        return deepcopy(value)


async def _local_set(key: str, value: Any, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    async with _local_cache_lock:
        if len(_local_cache) >= _LOCAL_CACHE_MAX_ITEMS:
            expired_keys = [item_key for item_key, (expires_at, _) in _local_cache.items() if expires_at <= _now()]
            for item_key in expired_keys:
                _local_cache.pop(item_key, None)
        if len(_local_cache) >= _LOCAL_CACHE_MAX_ITEMS:
            oldest_key = next(iter(_local_cache.keys()), None)
            if oldest_key is not None:
                _local_cache.pop(oldest_key, None)
        _local_cache[key] = (_now() + float(ttl_seconds), deepcopy(value))


async def _local_delete(key: str) -> None:
    async with _local_cache_lock:
        _local_cache.pop(key, None)


async def _local_delete_prefix(prefix: str) -> None:
    async with _local_cache_lock:
        keys = [item_key for item_key in _local_cache if item_key.startswith(prefix)]
        for item_key in keys:
            _local_cache.pop(item_key, None)


async def _close_redis_client() -> None:
    global _redis_client

    client = _redis_client
    _redis_client = None
    if client is None:
        return

    try:
        await client.aclose()
    except Exception:
        logger.debug("runtime_cache_redis_close_failed", exc_info=True)


async def _mark_redis_unavailable(*, error: Exception | str | None = None) -> None:
    global _redis_failure_logged, _redis_retry_after

    await _close_redis_client()
    _redis_retry_after = _now() + _REDIS_RETRY_BACKOFF_SECONDS
    if not _redis_failure_logged:
        logger.info("runtime_cache_redis_disabled", error=str(error or "unknown"))
        _redis_failure_logged = True


async def _get_redis_client() -> Any | None:
    global _redis_client, _redis_failure_logged, _redis_retry_after

    if not settings.REDIS_ENABLED_EFFECTIVE:
        # 轻量档：显式关闭，不连、不重试、不打降级日志——本地缓存就是最终形态
        return None
    if _redis_client is not None:
        return _redis_client
    if _redis_initialized:
        return None
    if _now() < _redis_retry_after:
        return None

    async with _redis_init_lock:
        if _redis_client is not None:
            return _redis_client
        if _redis_initialized:
            return None
        if _now() < _redis_retry_after:
            return None

        try:
            import redis.asyncio as redis  # type: ignore

            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=_REDIS_SOCKET_TIMEOUT_SECONDS,
                socket_timeout=_REDIS_SOCKET_TIMEOUT_SECONDS,
                health_check_interval=30,
            )
            await client.ping()
            _redis_client = client
            _redis_retry_after = 0.0
            if _redis_failure_logged:
                logger.info("runtime_cache_redis_recovered")
                _redis_failure_logged = False
        except Exception as exc:
            await _mark_redis_unavailable(error=exc)

    return _redis_client


def _namespaced(key: str) -> str:
    """所有键统一加实例命名空间，防同机多实例共享 Redis 时跨实例读到脏缓存。"""
    return f"ns:{settings.CACHE_NAMESPACE}:{key}"


async def get_json(key: str) -> Any | None:
    key = _namespaced(key)
    local_value = await _local_get(key)
    if local_value is not None:
        return local_value

    client = await _get_redis_client()
    if client is None:
        return None

    try:
        raw = await client.get(key)
    except Exception as exc:
        logger.debug("runtime_cache_redis_get_failed", key=key, error=str(exc))
        await _mark_redis_unavailable(error=exc)
        return None

    if not raw:
        return None

    try:
        value = json.loads(raw)
    except Exception:
        return None

    try:
        ttl = await client.ttl(key)
    except Exception:
        ttl = None
    if isinstance(ttl, int) and ttl > 0:
        await _local_set(key, value, ttl)

    return deepcopy(value)


async def set_json(key: str, value: Any, *, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return

    key = _namespaced(key)
    await _local_set(key, value, ttl_seconds)

    client = await _get_redis_client()
    if client is None:
        return

    try:
        await client.set(key, json.dumps(value, ensure_ascii=False, separators=(",", ":")), ex=max(int(ttl_seconds), 1))
    except Exception as exc:
        logger.debug("runtime_cache_redis_set_failed", key=key, error=str(exc))
        await _mark_redis_unavailable(error=exc)


async def delete(key: str) -> None:
    key = _namespaced(key)
    await _local_delete(key)

    client = await _get_redis_client()
    if client is None:
        return

    try:
        await client.delete(key)
    except Exception as exc:
        logger.debug("runtime_cache_redis_delete_failed", key=key, error=str(exc))
        await _mark_redis_unavailable(error=exc)


async def delete_prefix(prefix: str) -> None:
    prefix = _namespaced(prefix)
    await _local_delete_prefix(prefix)

    client = await _get_redis_client()
    if client is None:
        return

    cursor = 0
    pattern = f"{prefix}*"
    try:
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await client.delete(*keys)
            if int(cursor) == 0:
                break
    except Exception as exc:
        logger.debug("runtime_cache_redis_delete_prefix_failed", prefix=prefix, error=str(exc))
        await _mark_redis_unavailable(error=exc)


async def remember_json(
    key: str,
    *,
    ttl_seconds: int,
    loader: Callable[[], Awaitable[Any]],
) -> Any:
    cached = await get_json(key)
    if cached is not None:
        return cached

    lock = _remember_locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = await get_json(key)
        if cached is not None:
            return cached
        value = await loader()
        await set_json(key, value, ttl_seconds=ttl_seconds)
        return deepcopy(value)
