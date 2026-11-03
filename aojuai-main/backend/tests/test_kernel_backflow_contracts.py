"""内核卫生回流的契约测试。

这些能力都是从下游分支回流的纯内核件，
每一条都对应一个曾经在下游踩过的坑，测试用来防止它在基座上重新长出来。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import TooManyRequestsError
from app.core.http_cache import (
    PUBLIC_SHARE_INFO_CACHE_CONTROL,
    PUBLIC_SITE_CONFIG_CACHE_CONTROL,
    apply_cache_control,
)
from app.core.module_guards import (
    ensure_module_enabled_for_tenant,
    is_module_enabled_for_tenant,
)


def test_too_many_requests_error_shape() -> None:
    err = TooManyRequestsError(message="提交过于频繁")

    assert err.status_code == 429
    assert err.code == "TOO_MANY_REQUESTS"
    assert err.message == "提交过于频繁"


def _db_with_modules(**switches: bool) -> AsyncMock:
    db = AsyncMock()
    db.scalar.return_value = {"feature_switches": {"modules": dict(switches)}}
    return db


@pytest.mark.asyncio
async def test_is_module_enabled_for_tenant_does_not_raise_when_disabled() -> None:
    """可选模块联动的关键：对方关了要能"跳过"，而不是把调用方打成 403。"""
    db = _db_with_modules(public_site=False)

    assert (
        await is_module_enabled_for_tenant(db=db, tenant_id=1, module_code="public_site")
        is False
    )


@pytest.mark.asyncio
async def test_is_module_enabled_for_tenant_true_when_enabled() -> None:
    db = _db_with_modules(public_site=True)

    assert (
        await is_module_enabled_for_tenant(db=db, tenant_id=1, module_code="public_site")
        is True
    )


@pytest.mark.asyncio
async def test_ensure_module_enabled_still_enforces() -> None:
    """非强制查询新增后，强制版本的行为不能被削弱。"""
    from app.core.exceptions import ForbiddenError

    db = _db_with_modules(public_site=False)

    with pytest.raises(ForbiddenError):
        await ensure_module_enabled_for_tenant(
            db=db, tenant_id=1, module_code="public_site"
        )


def test_apply_cache_control_sets_headers() -> None:
    from starlette.responses import JSONResponse

    response = apply_cache_control(
        JSONResponse({"ok": True}),
        PUBLIC_SITE_CONFIG_CACHE_CONTROL,
        vary="Host",
        extra_headers={"X-Test": "1"},
    )

    assert response.headers["Cache-Control"] == PUBLIC_SITE_CONFIG_CACHE_CONTROL
    assert response.headers["Vary"] == "Host"
    assert response.headers["X-Test"] == "1"
    assert "max-age" in PUBLIC_SHARE_INFO_CACHE_CONTROL


def test_db_pool_settings_are_bounded() -> None:
    """连接池参数必须走 Settings 且有上下限，避免一个笔误把池设成 0 或 10 万。"""
    from app.core.config import Settings

    tiny = Settings(DB_POOL_SIZE=0, DB_MAX_OVERFLOW=-5, DB_POOL_TIMEOUT=0, DB_POOL_RECYCLE=5)
    assert tiny.DB_POOL_SIZE_EFFECTIVE == 1
    assert tiny.DB_MAX_OVERFLOW_EFFECTIVE == 0
    assert tiny.DB_POOL_TIMEOUT_EFFECTIVE == 1
    assert tiny.DB_POOL_RECYCLE_EFFECTIVE == 60

    huge = Settings(DB_POOL_SIZE=10_000, DB_MAX_OVERFLOW=10_000, DB_POOL_TIMEOUT=10_000)
    assert huge.DB_POOL_SIZE_EFFECTIVE == 200
    assert huge.DB_MAX_OVERFLOW_EFFECTIVE == 500
    assert huge.DB_POOL_TIMEOUT_EFFECTIVE == 300

    never_recycle = Settings(DB_POOL_RECYCLE=-1)
    assert never_recycle.DB_POOL_RECYCLE_EFFECTIVE == -1


class _FakeResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeConn:
    """按执行顺序回放 information_schema / alembic_version 两次查询的结果。"""

    def __init__(self, results: list[object | None]) -> None:
        self._results = list(results)
        self.run_sync_calls: list[object] = []

    async def execute(self, *_args: object, **_kwargs: object) -> _FakeResult:
        return _FakeResult(self._results.pop(0) if self._results else None)

    async def run_sync(self, fn: object) -> None:
        self.run_sync_calls.append(fn)

    @property
    def dialect(self):  # init_db 会按方言决定是否 stamp（SQLite 专用）
        from types import SimpleNamespace

        return SimpleNamespace(name="postgresql")


class _FakeEngine:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def begin(self):  # noqa: ANN201 - async context manager
        conn = self._conn

        class _Ctx:
            async def __aenter__(self):  # noqa: ANN204
                return conn

            async def __aexit__(self, *_exc: object) -> bool:
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_init_db_skips_create_all_on_migrated_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUTO_INIT_DB 不得在已被 Alembic 管理的库上跑 create_all。

    踩过的坑：迁移失败后部署脚本回落 AUTO_INIT_DB=true，create_all 按 ORM 现状
    补出迁移链里不存在的表，之后迁移与真实 schema 永久对不上。
    """
    from app.infrastructure.database import session as session_module

    # alembic_version 表存在，且有一行版本记录
    conn = _FakeConn([1, 1])
    monkeypatch.setattr(session_module, "engine", _FakeEngine(conn))

    await session_module.init_db()

    assert conn.run_sync_calls == [], "已迁移的库上不允许执行 create_all"


@pytest.mark.asyncio
async def test_init_db_creates_tables_on_fresh_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """反向用例：全新库仍要能被 AUTO_INIT_DB 拉起来，否则开发态冷启动就断了。"""
    from app.infrastructure.database import session as session_module

    conn = _FakeConn([None])  # 没有 alembic_version 表
    monkeypatch.setattr(session_module, "engine", _FakeEngine(conn))

    await session_module.init_db()

    assert len(conn.run_sync_calls) == 1, "全新库必须执行一次 create_all"


@pytest.mark.asyncio
async def test_send_notification_can_skip_channel_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dispatcher 要先做跨作用域去重，因此必须能只落站内、不投外部通道。"""
    from app.domain.notifications import send as notification_module

    class _FakeNotification:
        id = 42

    created = _FakeNotification()

    class _FakeService:
        def __init__(self, _db: object) -> None:
            pass

        async def create(self, _data: dict[str, object]) -> object:
            return created

    deliver = AsyncMock()
    monkeypatch.setattr(notification_module, "NotificationService", _FakeService)
    monkeypatch.setattr(
        notification_module, "deliver_notification_to_user_channels", deliver
    )

    result = await notification_module.send_notification(
        AsyncMock(),
        tenant_id=1,
        user_id=2,
        category="message",
        title="t",
        deliver_to_channels=False,
    )

    assert result is created
    deliver.assert_not_awaited()

    await notification_module.send_notification(
        AsyncMock(),
        tenant_id=1,
        user_id=2,
        category="message",
        title="t",
    )
    deliver.assert_awaited_once()
