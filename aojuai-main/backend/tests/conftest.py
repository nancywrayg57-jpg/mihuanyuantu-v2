"""测试级的全局状态隔离。

模块安装开关（`AOJ_ENABLED_MODULES`）与它的 lru_cache 是**进程级**的：
某个测试把它设成 "none" 之后如果忘了还原，后面所有依赖模块目录的测试都会看到
一个被裁剪过的 catalog，症状是"单独跑全过、全量跑就红"，而且报错位置离肇事者很远。

以前这件事靠每个测试文件各自写 fixture 记得清理，于是删掉某个文件时会连带
让别的测试变红（本轮就发生过一次）。统一收口到这里，测试文件不再各自记忆清理步骤。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest

from app.core import feature_switches


@pytest.fixture(autouse=True)
def isolate_module_installation_state() -> Iterator[None]:
    """把每个测试的起点固定为"未裁剪"，并在结束后还原。

    起点必须是固定值而不是"当前值"：这个设置会从 backend/.env 读进来，
    本地放一个 `AOJ_ENABLED_MODULES=none` 的 .env（部署环境的常见值）就会让
    整批模块目录相关的测试变红，而代码本身没有任何问题。
    测试结果不该取决于开发者本地的 .env。
    """
    original = feature_switches.settings.AOJ_ENABLED_MODULES
    feature_switches.settings.AOJ_ENABLED_MODULES = ""
    feature_switches.clear_module_install_caches()
    try:
        yield
    finally:
        feature_switches.settings.AOJ_ENABLED_MODULES = original
        feature_switches.clear_module_install_caches()


@pytest.fixture(scope="session", autouse=True)
def bootstrap_sqlite_schema() -> None:
    """SQLite 轻量档跑集成测试时建一次表。

    PG 档的集成测试依赖一个已迁移的开发库；SQLite 档（`DB_DRIVER=sqlite`）通常指向
    一个临时文件，没有人替它建表，所以在会话开始时走一次 `init_db()`
    （create_all + stamp head，已迁移过的库是 no-op）。PG 档不做任何事，保持迁移是唯一真源。
    """
    import asyncio

    from app.core.config import settings

    if not settings.IS_SQLITE:
        return
    from app.infrastructure.database.session import close_db, init_db

    async def _bootstrap() -> None:
        await init_db()
        # PG 档的集成测试默认有一个已 seed 的开发库（租户 1 / admin / 系统菜单）；SQLite 临时库同样补齐，
        # 否则依赖租户 1 或权限按钮的测试会因"租户不存在"假红。seed 幂等。
        from scripts.seed_data import seed_initial_data

        await seed_initial_data()
        if settings.SQLITE_PATH.strip() != ":memory:":
            await close_db()  # 内存库的 StaticPool 一 dispose 就没了，只对文件库释放连接

    asyncio.run(_bootstrap())


@pytest.fixture(autouse=True)
async def release_engine_connections_between_loops() -> AsyncIterator[None]:
    """pytest-asyncio 每个测试一个事件循环，而进程级 engine 的连接池是跨测试共享的。

    真实库测试跑完后，池里留着绑定在**上一个循环**上的 asyncpg 连接；下一个真实库测试
    在新循环里取到它就会报 "Task attached to a different loop"（并发扣费测试在全量跑时
    稳定失败、单跑全绿）。每个测试结束后清空连接池即可。

    SQLite `:memory:` 不能 dispose：StaticPool 一 dispose 内存库就空了，而
    session 级 bootstrap 只 seed 一次。aiosqlite StaticPool 跨 loop 复用可接受；
    本守卫的目标故障是 asyncpg 连接绑旧 loop。
    """
    yield
    from app.core.config import settings
    from app.infrastructure.database.session import engine

    if settings.IS_SQLITE and settings.SQLITE_PATH.strip() == ":memory:":
        return
    try:
        await engine.dispose()
    except Exception:  # noqa: BLE001 - 上一个循环的连接关闭失败不该让测试变红
        pass


# ---------------------------------------------------------------------------
# PostgreSQL 集成测试的统一跳过闸门
# ---------------------------------------------------------------------------
# 一批 credits / ai_redaction 用例是**真库**集成测试：它们直接连
# `settings.DATABASE_URL`，断言的东西（丢失更新、迁移契约里的索引、
# information_schema、权限按钮的种子数据）离开真实 PostgreSQL 就没有意义，
# 换成 SQLite 只会把断言稀释成"另一套语义下也成立"，等于把门禁拆了。
#
# 但它们此前没有任何守卫：没配开发库的机器上 `pytest` 一跑就是
# 12 failed + 4 errors，全都是 `role "aoju" does not exist`——一个**环境**问题
# 伪装成 16 个代码故障，三份分支合并报告都被它绊过一次。
#
# 所以给它们一个显式标记 `@pytest.mark.requires_database`：
# 库连得上照常跑（一行断言不改），连不上就 skip，并把真实原因写进 skip reason，
# 免得下一个人再去猜是代码坏了还是环境没配。
#
# 判据是"连得上", 不是"环境变量像不像"：只有真去连一次才分得清
# 「库没起」「角色不存在」「密码错」「网络不通」，而这几种都得跳过。
# 探测每个进程只做一次（结果缓存），并且**懒执行**——没选中带标记的用例时不会去连库。

_DATABASE_PROBE: list[str | None] = []  # 空 = 还没探过；[None] = 可用；[reason] = 不可用


def _safe_database_url() -> str:
    """脱敏后的连接串，用来写进 skip reason（原串带密码，不能进日志）。"""
    from sqlalchemy.engine import make_url

    from app.core.config import settings

    try:
        return make_url(settings.DATABASE_URL).render_as_string(hide_password=True)
    except Exception:  # noqa: BLE001 - 连串都解析不了时不值得把测试拖红
        return "<unparseable DATABASE_URL>"


def _probe_database() -> str | None:
    """真去连一次测试库。返回 None 表示可用，否则返回不可用的原因。"""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings

    url = settings.DATABASE_URL
    # 只对 asyncpg 下发连接超时；连不上的机器上默认会干等到 TCP 超时。
    connect_args = {"timeout": 5} if "asyncpg" in url else {}

    async def _connect() -> None:
        # 用一次性 engine，别碰进程级 engine 的连接池（那个池是跨测试共享的，
        # 见上面 release_engine_connections_between_loops 的说明）。
        engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("select 1"))
        finally:
            await engine.dispose()

    try:
        asyncio.run(_connect())
    except Exception as exc:  # noqa: BLE001 - 任何连不上的原因都一样要跳过
        return f"{type(exc).__name__}: {exc}"
    return None


def database_unavailable_reason() -> str | None:
    """测试库不可用的原因；可用时返回 None。进程级只探一次。"""
    if not _DATABASE_PROBE:
        from app.core.config import settings

        # SQLite 档不需要外部服务，建表由 bootstrap_sqlite_schema 负责。
        _DATABASE_PROBE.append(None if settings.IS_SQLITE else _probe_database())
    return _DATABASE_PROBE[0]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_database: 需要一个可连接的（已迁移并 seed 过的）数据库；连不上时跳过而不是变红",
    )


@pytest.fixture(autouse=True)
def skip_when_database_is_unreachable(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("requires_database") is None:
        return
    reason = database_unavailable_reason()
    if reason is None:
        return
    pytest.skip(
        f"需要可连接的测试数据库（{_safe_database_url()}），当前连不上：{reason}。"
        "配好 backend/.env 或 DB_* 环境变量（或 DB_DRIVER=sqlite 走轻量档）后本用例会照常执行。"
    )
