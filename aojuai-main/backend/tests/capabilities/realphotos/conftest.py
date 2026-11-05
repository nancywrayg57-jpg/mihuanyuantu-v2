"""In-memory SQLite fixtures for realphotos S0 behavioural tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def storage_tmpdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "realphotos-disk"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("REALPHOTOS_STORAGE_ROOT", str(root))
    monkeypatch.setenv("REALPHOTOS_ALLOW_DEV_CAPTCHA", "true")
    return root


@pytest_asyncio.fixture
async def db(storage_tmpdir: Path) -> AsyncIterator[AsyncSession]:
    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.core import feature_switches
    from app.infrastructure.database.session import Base

    feature_switches.settings.AOJ_ENABLED_MODULES = "realphotos"
    feature_switches.clear_module_install_caches()

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
    feature_switches.settings.AOJ_ENABLED_MODULES = ""
    feature_switches.clear_module_install_caches()
