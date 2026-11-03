"""数据库方言注册表：集中承载 PostgreSQL 标准档与 SQLite 轻量档的差异。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, Protocol

from sqlalchemy import cast, exists, func, literal, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import settings
from app.core.logger import get_logger

DialectName = Literal["postgresql", "sqlite"]

_JSONB_CAST = re.compile(r"cast\(\s*(:\w+|'[^']*')\s+as\s+jsonb\s*\)", re.IGNORECASE)
_NOW = re.compile(r"\bnow\(\)", re.IGNORECASE)

# 保持迁移前 task_queue 的 logger 名称，避免结构重构改变日志归属。
_task_queue_logger = get_logger("app.core.task_queue")


class DialectSupport(Protocol):
    """业务代码可依赖的完整方言能力面。"""

    name: DialectName
    supports_partial_index: bool
    supports_returning: bool
    supports_advisory_lock: bool
    supports_jsonb_ops: bool
    single_writer: bool

    def begin_statement(self) -> str | None: ...

    def json_array_contains(self, column: Any, value: Any) -> ColumnElement[bool]: ...

    def json_merge_patch(self, column: Any, patch: dict[str, Any]) -> ColumnElement[Any]: ...

    def greatest(self, *exprs: Any) -> ColumnElement[Any]: ...

    def insert(self, table: object) -> Any: ...

    async def table_exists(self, db: object, name: str) -> bool: ...

    async def column_exists(self, db: object, table: str, col: str) -> bool: ...

    async def index_exists(self, db: object, table: str, index: str) -> bool: ...

    async def escalate_to_write_lock(self, db: object) -> None: ...

    def scheduler_job_lock(self, job_name: str) -> AbstractAsyncContextManager[bool]: ...

    def portable_sql(self, sql: str) -> str: ...


def _advisory_lock_key(value: str) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


@dataclass(frozen=True, slots=True)
class PostgreSQLDialect:
    name: Literal["postgresql"] = "postgresql"
    supports_partial_index: bool = True
    supports_returning: bool = True
    supports_advisory_lock: bool = True
    supports_jsonb_ops: bool = True
    single_writer: bool = False

    def begin_statement(self) -> None:
        return None

    def json_array_contains(self, column: Any, value: Any) -> ColumnElement[bool]:
        return column.contains([value])

    def json_merge_patch(self, column: Any, patch: dict[str, Any]) -> ColumnElement[Any]:
        return column.op("||")(cast(patch, JSONB))

    def greatest(self, *exprs: Any) -> ColumnElement[Any]:
        return func.greatest(*exprs)

    def insert(self, table: object) -> Any:
        from sqlalchemy.dialects.postgresql import insert

        return insert(table)

    async def table_exists(self, db: object, name: str) -> bool:
        sql = text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :name LIMIT 1"
        )
        return bool((await db.execute(sql, {"name": name})).scalar())  # type: ignore[attr-defined]

    async def column_exists(self, db: object, table: str, col: str) -> bool:
        sql = text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t AND column_name = :c LIMIT 1"
        )
        return bool((await db.execute(sql, {"t": table, "c": col})).scalar())  # type: ignore[attr-defined]

    async def index_exists(self, db: object, table: str, index: str) -> bool:
        quoted_table = table.replace("'", "''")
        quoted_index = index.replace("'", "''")
        return bool(
            (
                await db.execute(  # type: ignore[attr-defined]
                    text(
                        f"""
                        SELECT 1
                        FROM pg_indexes
                        WHERE schemaname = current_schema()
                          AND tablename = '{quoted_table}'
                          AND indexname = '{quoted_index}'
                        LIMIT 1
                        """
                    )
                )
            ).scalar()
        )

    async def escalate_to_write_lock(self, db: object) -> None:
        return None

    @asynccontextmanager
    async def scheduler_job_lock(self, job_name: str) -> AsyncIterator[bool]:
        key = _advisory_lock_key(f"scheduler_job:{job_name}")
        from app.infrastructure.database.session import engine

        try:
            conn = await engine.connect()
        except Exception:  # noqa: BLE001
            _task_queue_logger.warning("scheduler_job_lock_unavailable", job=job_name, exc_info=True)
            yield True
            return
        acquired = False
        try:
            try:
                got = await conn.execute(
                    text("SELECT pg_try_advisory_lock(:key)").bindparams(key=key)
                )
                acquired = bool(got.scalar())
                await conn.commit()
            except Exception:  # noqa: BLE001 - 锁不可用时按既有契约放行
                acquired = True
            if not acquired:
                _task_queue_logger.info("scheduler_job_lock_busy", job=job_name)
            try:
                yield acquired
            finally:
                if acquired:
                    try:
                        await conn.execute(
                            text("SELECT pg_advisory_unlock(:key)").bindparams(key=key)
                        )
                        await conn.commit()
                    except Exception:  # noqa: BLE001
                        _task_queue_logger.warning(
                            "scheduler_job_unlock_failed", job=job_name, exc_info=True
                        )
                        try:  # noqa: SIM105 - 保持迁移前的 fail-open 控制流
                            await conn.invalidate()
                        except Exception:  # noqa: BLE001
                            pass
        finally:
            await conn.close()

    def portable_sql(self, sql: str) -> str:
        return sql


@dataclass(frozen=True, slots=True)
class SQLiteDialect:
    name: Literal["sqlite"] = "sqlite"
    supports_partial_index: bool = True
    supports_returning: bool = True
    supports_advisory_lock: bool = False
    supports_jsonb_ops: bool = False
    single_writer: bool = True

    def begin_statement(self) -> str:
        return "BEGIN IMMEDIATE" if settings.SQLITE_BEGIN_MODE == "immediate" else "BEGIN"

    def json_array_contains(self, column: Any, value: Any) -> ColumnElement[bool]:
        each = func.json_each(column).table_valued("value")
        return exists(select(literal(1)).select_from(each).where(each.c.value == value))

    def json_merge_patch(self, column: Any, patch: dict[str, Any]) -> ColumnElement[Any]:
        return func.json_patch(column, json.dumps(patch, ensure_ascii=False))

    def greatest(self, *exprs: Any) -> ColumnElement[Any]:
        return func.max(*exprs)

    def insert(self, table: object) -> Any:
        from sqlalchemy.dialects.sqlite import insert

        return insert(table)

    async def table_exists(self, db: object, name: str) -> bool:
        sql = text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :name LIMIT 1")
        return bool((await db.execute(sql, {"name": name})).scalar())  # type: ignore[attr-defined]

    async def column_exists(self, db: object, table: str, col: str) -> bool:
        rows = (await db.execute(text(f'PRAGMA table_info("{table}")'))).all()  # type: ignore[attr-defined]
        return any(str(row[1]) == col for row in rows)

    async def index_exists(self, db: object, table: str, index: str) -> bool:
        rows = (await db.execute(text(f'PRAGMA index_list("{table}")'))).all()  # type: ignore[attr-defined]
        return any(str(row[1]) == index for row in rows)

    async def escalate_to_write_lock(self, db: object) -> None:
        await db.execute(  # type: ignore[attr-defined]
            text("UPDATE alembic_version SET version_num = version_num")
        )

    @asynccontextmanager
    async def scheduler_job_lock(self, job_name: str) -> AsyncIterator[bool]:
        # SQLite 轻量档没有 advisory lock，且按设计只跑单进程：直接放行。
        yield True

    def portable_sql(self, sql: str) -> str:
        # SQLite 的 JSON 列就是 TEXT，JSON 字符串直接写入；CURRENT_TIMESTAMP 与 PG now() 等价（UTC）。
        sql = _JSONB_CAST.sub(r"\1", sql)
        return _NOW.sub("CURRENT_TIMESTAMP", sql)


@lru_cache(maxsize=2)
def _dialect_by_name(name: DialectName) -> DialectSupport:
    if name == "sqlite":
        return SQLiteDialect()
    return PostgreSQLDialect()


def get_dialect() -> DialectSupport:
    """返回当前配置对应的缓存方言实现。"""
    return _dialect_by_name(settings.DB_DIALECT)
