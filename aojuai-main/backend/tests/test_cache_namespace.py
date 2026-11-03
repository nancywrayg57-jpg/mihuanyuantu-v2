"""缓存键实例命名空间：同机多实例共享 Redis 时防跨实例投毒。

背景：menu_routes/tenant_feature_switches 等键形只含 tenant/user id，
各实例的 tenant 1/user 1 相同 → 共库 db0 时互读脏缓存（曾出现 dev 实例
读到 logistics 实例的 Shopify 菜单）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.infrastructure.cache import runtime_cache
from app.infrastructure.cache.redis import RedisJsonCache


def test_cache_namespace_defaults_to_db_name(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DB_DRIVER", "postgresql")  # SQLite 档缺省命名空间按库路径派生，见 test_dialect_features
    monkeypatch.setattr(settings, "AOJU_CACHE_NAMESPACE", "")
    expected_default = str(settings.DB_NAME)
    assert expected_default == settings.CACHE_NAMESPACE

    monkeypatch.setattr(settings, "AOJU_CACHE_NAMESPACE", "custom_ns")
    assert settings.CACHE_NAMESPACE == "custom_ns"


def test_runtime_cache_keys_are_namespaced() -> None:
    key = runtime_cache._namespaced("menu_routes:tenant:1:user:1")  # noqa: SLF001
    assert key == f"ns:{settings.CACHE_NAMESPACE}:menu_routes:tenant:1:user:1"


@pytest.mark.asyncio
async def test_redis_json_cache_calls_client_with_namespaced_keys() -> None:
    cache = RedisJsonCache.__new__(RedisJsonCache)
    client = AsyncMock()
    client.get.return_value = None
    client.mget.return_value = [None, b"3"]
    client.incr.return_value = 7
    cache._client = client  # noqa: SLF001

    ns = f"ns:{settings.CACHE_NAMESPACE}:"

    await cache.get_json("k1")
    client.get.assert_awaited_with(f"{ns}k1")

    await cache.set_json("k2", {"a": 1}, ttl_seconds=60)
    assert client.set.await_args.args[0] == f"{ns}k2"

    await cache.get_int("aoju:cache:ver:menu-structure")
    client.get.assert_awaited_with(f"{ns}aoju:cache:ver:menu-structure")

    values = await cache.get_ints(["v1", "v2"])
    assert client.mget.await_args.args[0] == [f"{ns}v1", f"{ns}v2"]
    assert values == [0, 3]

    assert await cache.incr("v3") == 7
    client.incr.assert_awaited_with(f"{ns}v3")


@pytest.mark.asyncio
async def test_incr_with_ttl_strict_returns_none_when_redis_unavailable() -> None:
    cache = RedisJsonCache.__new__(RedisJsonCache)
    cache._client = None  # noqa: SLF001
    assert await cache.incr_with_ttl_strict("rate:k", ttl_seconds=60) is None

    failing = AsyncMock()
    failing.eval.side_effect = ConnectionError("down")
    cache._client = failing  # noqa: SLF001
    assert await cache.incr_with_ttl_strict("rate:k", ttl_seconds=60) is None
    # best-effort incr keeps its 0 fallback; strict must not silently pass
    failing.incr.side_effect = ConnectionError("down")
    assert await cache.incr("rate:k") == 0


@pytest.mark.asyncio
async def test_incr_with_ttl_strict_uses_namespaced_key_and_ttl() -> None:
    cache = RedisJsonCache.__new__(RedisJsonCache)
    client = AsyncMock()
    client.eval.return_value = 3
    cache._client = client  # noqa: SLF001

    assert await cache.incr_with_ttl_strict("rate:k", ttl_seconds=0) == 3
    args = client.eval.await_args.args
    assert args[1] == 1
    assert args[2] == f"ns:{settings.CACHE_NAMESPACE}:rate:k"
    assert args[3] == 1  # ttl clamped to >= 1
