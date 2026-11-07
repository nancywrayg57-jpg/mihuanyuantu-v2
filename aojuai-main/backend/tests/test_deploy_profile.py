"""部署形态：lite（SQLite，无 Redis）与 standard（PostgreSQL + Redis）由 DB_DRIVER 一个开关派生，互不干扰。"""

from __future__ import annotations

from app.core.config import settings


def test_profile_follows_db_driver(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    assert settings.DEPLOY_PROFILE == "lite"
    monkeypatch.setattr(settings, "DB_DRIVER", "postgresql")
    assert settings.DEPLOY_PROFILE == "standard"


def test_redis_defaults_off_for_lite_and_on_for_standard(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REDIS_ENABLED", None)
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    assert settings.REDIS_ENABLED_EFFECTIVE is False
    monkeypatch.setattr(settings, "DB_DRIVER", "postgresql")
    assert settings.REDIS_ENABLED_EFFECTIVE is True
    monkeypatch.setattr(settings, "REDIS_ENABLED", True)
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    assert settings.REDIS_ENABLED_EFFECTIVE is True, "轻量档也允许显式开 Redis（多进程时需要）"


async def test_disabled_redis_cache_is_a_silent_miss(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REDIS_ENABLED", False)
    from app.infrastructure.cache import runtime_cache
    from app.infrastructure.cache import redis as redis_mod
    from app.infrastructure.cache.redis import RedisJsonCache

    redis_mod._LOCAL_INTS.clear()
    cache = RedisJsonCache()
    assert cache._client is None
    # JSON payloads stay silent-miss when Redis is off.
    assert await cache.get_json("k") is None
    # Version keys use process-local counters so menu bump works without Redis (IA_C6).
    assert await cache.incr("menu-ver") == 1
    assert await cache.get_int("menu-ver") == 1
    assert await cache.incr("menu-ver") == 2
    # Untouched keys still return the caller default (not a fake shared zero).
    assert await cache.get_ints(["a", "b"], default=7) == [7, 7]
    assert await runtime_cache._get_redis_client() is None
