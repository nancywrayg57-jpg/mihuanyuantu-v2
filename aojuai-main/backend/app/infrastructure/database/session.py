"""
AOJU Backend - Database Connection
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

def _build_engine():
    """方言感知的引擎工厂：PostgreSQL 走连接池参数；SQLite 走单文件/内存配置。

    SQLite 要点（轻量部署）：
    - 外键约束默认关闭，必须每连接 PRAGMA foreign_keys=ON；
    - 文件库开 WAL 提高读写并发；busy_timeout 避免"database is locked"直接抛错；
    - SQLite 方言会忽略 `FOR UPDATE`。事务起始由 `SQLITE_BEGIN_MODE` 决定：缺省 immediate（SQLAlchemy 官方
      pysqlite 配方：所有事务串行化，"先读后写"既不丢更新也不报 BUSY，busy_timeout 内排队；轻量档以正确性优先），
      deferred 则读事务不占写锁、吞吐更好，但"先读后写"遇并发写会以 `database is locked` 失败——
      关键写路径已用 `escalate_to_write_lock()` 在首条读之前进入写事务，其余路径需自行承担该语义。
    """
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        from pathlib import Path

        from sqlalchemy import event
        from sqlalchemy.pool import NullPool, StaticPool

        is_memory = ":memory:" in url or url.endswith("sqlite+aiosqlite://")
        if not is_memory:
            # 缺省 ./data/aoju.db 的父目录不存在时 sqlite3 直接报 "unable to open database file"
            Path(url.split("sqlite+aiosqlite:///", 1)[1]).expanduser().parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"echo": settings.DB_ECHO, "connect_args": {"timeout": 30}}
        # aiosqlite ≥0.22 的 Connection 不再是 daemon Thread，而 SQLAlchemy 的 aiosqlite 适配器从不
        # await close()（sqlalchemy#13039 / aiosqlite#369）：池里留着的连接会让进程退出时卡在
        # threading._shutdown。文件库用 NullPool（用完即关，线程随之结束，WAL 下每连接开销可忽略），
        # 内存库必须 StaticPool（否则每个连接都是一个新的空库）；应用关闭统一 close_db() → dispose()。
        kwargs["poolclass"] = StaticPool if is_memory else NullPool
        sqlite_engine = create_async_engine(url, **kwargs)

        @event.listens_for(sqlite_engine.sync_engine, "connect")
        def _sqlite_on_connect(dbapi_connection, _record) -> None:  # pragma: no cover - 由集成测试覆盖
            dbapi_connection.isolation_level = None  # 交给 begin 事件显式开事务
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            if not is_memory:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        begin_sql = "BEGIN IMMEDIATE" if settings.SQLITE_BEGIN_MODE == "immediate" else "BEGIN"

        @event.listens_for(sqlite_engine.sync_engine, "begin")
        def _sqlite_begin(conn) -> None:  # pragma: no cover
            conn.exec_driver_sql(begin_sql)

        return sqlite_engine
    # PG：连接带进程标识（pg_stat_activity 可按 web/worker 归属）、空闲会话回收、LIFO 复用热连接
    server_settings = {"application_name": settings.DB_APPLICATION_NAME_EFFECTIVE}
    if settings.DB_IDLE_SESSION_TIMEOUT_EFFECTIVE > 0:
        server_settings["idle_session_timeout"] = f"{settings.DB_IDLE_SESSION_TIMEOUT_EFFECTIVE}s"
    return create_async_engine(
        url,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        pool_use_lifo=True,
        connect_args={"server_settings": server_settings},
        pool_size=settings.DB_POOL_SIZE_EFFECTIVE,
        max_overflow=settings.DB_MAX_OVERFLOW_EFFECTIVE,
        pool_timeout=settings.DB_POOL_TIMEOUT_EFFECTIVE,
        pool_recycle=settings.DB_POOL_RECYCLE_EFFECTIVE,
    )


# Create async engine
engine = _build_engine()

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base"""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.
    Use in FastAPI endpoints: db: AsyncSession = Depends(get_db)
    
    Transaction is automatically managed:
    - Commits on successful completion
    - Rolls back on exception
    
    Note: 不使用 session.begin() 以支持在特殊情况下手动提交部分事务
    （例如：登录失败时需要记录失败次数后再抛出异常）
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database session.
    Use in background tasks or services.
    
    Transaction is automatically managed:
    - Commits on successful completion
    - Rolls back on exception

    Note:
    - Do NOT wrap the whole context in `session.begin()` here.
      Some services/scripts may call `commit()` internally.
      A surrounding transaction context would then be closed too early.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database (create tables).

    只服务开发态冷启动。库一旦被 Alembic 管理过（alembic_version 有记录），
    就必须由迁移作为 schema 的唯一真源——此时 create_all 会凭 ORM 现状
    补出迁移链里没有的表/列，让"迁移是唯一真源"的约束失效，因此直接返回。
    """
    async with engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            probe = text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'")
        else:
            probe = text("SELECT to_regclass('alembic_version')")
        if (await conn.execute(probe)).scalar_one_or_none() is not None:
            stamped = await conn.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
            if stamped.scalar_one_or_none() is not None:
                return

        # Import all models before creating tables
        # NOTE: AUTO_INIT_DB is intended for dev bootstrap; production should use Alembic migrations.
        import app.domain  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "sqlite":
            # 轻量部署：SQLite 新库由 create_all 建全表后直接 stamp 到 head，
            # 后续 schema 变更由"双方言迁移"接管（历史 PG 专有迁移不在 SQLite 上重放）。
            await conn.run_sync(_stamp_alembic_head)


def _stamp_alembic_head(sync_conn) -> None:
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    ini = Path(__file__).resolve().parents[3] / "alembic.ini"
    if not ini.is_file():
        return
    cfg = Config(str(ini))
    # alembic.ini 里 script_location=alembic 是相对 cwd 的；非 backend/ 目录启动时要锚定到 ini 所在目录
    cfg.set_main_option("script_location", str(ini.parent / cfg.get_main_option("script_location", "alembic")))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    if not head:
        return
    sync_conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(255) NOT NULL PRIMARY KEY)")
    sync_conn.exec_driver_sql("DELETE FROM alembic_version")
    sync_conn.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES (?)", (head,))


async def close_db() -> None:
    """Close database connections"""
    await engine.dispose()
