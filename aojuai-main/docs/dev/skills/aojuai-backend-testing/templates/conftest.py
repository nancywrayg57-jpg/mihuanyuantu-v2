from __future__ import annotations

import os

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.infrastructure.database.session import Base
from app.infrastructure.database.session import get_db as get_db_dep


def _require_test_db_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Missing TEST_DATABASE_URL. Example:\n"
            "  export TEST_DATABASE_URL='postgresql+asyncpg://aidevbase:***@127.0.0.1:5432/aidevbase_test'"
        )
    return url


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(_require_test_db_url(), echo=False, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db_dep] = _override_get_db
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

