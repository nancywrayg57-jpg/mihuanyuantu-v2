"""In-process SQLite fixtures for the support pack's behavioural tests.

为什么不用真库：这批断言（租户隔离、归属越权、蜜罐/限流、留言桥）不依赖任何
PostgreSQL 专有语义，用一个进程内的内存库就能真跑 SQL——没配开发库的机器上
它们照样是**真实执行**的测试，而不是被 skip 掉的空门禁。
（真正需要 PG 语义的用例仍应打 `@pytest.mark.requires_database`。）
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    import app.capabilities.support.models  # noqa: F401
    import app.domain  # noqa: F401  # 注册内核模型（users / menus / roles / notifications …）
    from app.infrastructure.database.session import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def anonymous_request():
    """Minimal stand-in for ``fastapi.Request``: only headers + client are read."""

    class _Headers(dict):
        def get(self, key, default=""):  # noqa: D102 - dict.get with the header default
            return super().get(key, default)

    class _Client:
        host = "203.0.113.9"

    class _Request:
        headers = _Headers()
        client = _Client()

    return _Request()
