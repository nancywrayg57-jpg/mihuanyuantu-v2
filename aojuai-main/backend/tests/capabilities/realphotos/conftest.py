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
    from app.core.config import settings

    root = tmp_path / "realphotos-disk"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "REALPHOTOS_STORAGE_ROOT", str(root))
    monkeypatch.setattr(settings, "REALPHOTOS_ALLOW_DEV_CAPTCHA", "true")
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
        # PRESET-BULK-IMPORT B1 stops catalog injection; seed RuntimeCam rows so S1/S2/S3/S4/S6
        # unit tests that still reference S1_ENABLED_PRESETS codes keep a real enabled preset.
        from app.capabilities.realphotos.permissions import ROLE_ADMIN
        from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
        from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService

        ops = RealphotosOpsService(session)
        for item in S1_ENABLED_PRESETS:
            await ops.save_preset(
                actor_role_codes={ROLE_ADMIN, "admin"},
                code=str(item["code"]),
                device_type=str(item["deviceType"]),
                brand="RuntimeCam",
                model_name=str(item["model"]),
                gps_mode=str(item.get("gpsMode") or "none"),
                enabled=True,
                iso=str(item.get("iso") or "100"),
                shutter=str(item.get("shutter") or "1/125"),
                aperture=str(item.get("aperture") or "f/1.8"),
                focal_length=str(item.get("focalLength") or "26mm"),
                source="admin",
            )
        await session.commit()
        yield session
    await engine.dispose()
    feature_switches.settings.AOJ_ENABLED_MODULES = ""
    feature_switches.clear_module_install_caches()
