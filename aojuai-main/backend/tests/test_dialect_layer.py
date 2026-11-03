"""数据库方言注册表的选择、能力位与行为契约。"""

from __future__ import annotations

from sqlalchemy import Integer, column, table
from sqlalchemy.dialects.postgresql.dml import Insert as PostgreSQLInsert
from sqlalchemy.dialects.sqlite.dml import Insert as SQLiteInsert

from app.core.config import settings
from app.infrastructure.database.dialect import PostgreSQLDialect, SQLiteDialect, get_dialect


def _select_driver(monkeypatch, driver: str) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL_OVERRIDE", None)
    monkeypatch.setattr(settings, "DB_DRIVER", driver)


def test_get_dialect_selects_and_caches_postgresql(monkeypatch) -> None:
    _select_driver(monkeypatch, "postgresql")

    dialect = get_dialect()

    assert isinstance(dialect, PostgreSQLDialect)
    assert dialect is get_dialect()
    assert settings.DB_DIALECT == "postgresql"
    assert dialect.name == "postgresql"
    assert dialect.supports_partial_index is True
    assert dialect.supports_returning is True
    assert dialect.supports_advisory_lock is True
    assert dialect.supports_jsonb_ops is True
    assert dialect.single_writer is False
    assert dialect.begin_statement() is None


def test_get_dialect_selects_and_caches_sqlite(monkeypatch) -> None:
    _select_driver(monkeypatch, "sqlite")
    monkeypatch.setattr(settings, "SQLITE_BEGIN_MODE", "immediate")

    dialect = get_dialect()

    assert isinstance(dialect, SQLiteDialect)
    assert dialect is get_dialect()
    assert settings.DB_DIALECT == "sqlite"
    assert dialect.name == "sqlite"
    assert dialect.supports_partial_index is True
    assert dialect.supports_returning is True
    assert dialect.supports_advisory_lock is False
    assert dialect.supports_jsonb_ops is False
    assert dialect.single_writer is True
    assert dialect.begin_statement() == "BEGIN IMMEDIATE"

    monkeypatch.setattr(settings, "SQLITE_BEGIN_MODE", "deferred")
    assert dialect.begin_statement() == "BEGIN"


def test_portable_sql_is_identity_on_postgresql_and_rewrites_sqlite(monkeypatch) -> None:
    sql = "INSERT INTO items(payload, created_at) VALUES (cast(:payload as jsonb), now())"

    _select_driver(monkeypatch, "postgresql")
    assert get_dialect().portable_sql(sql) == sql

    _select_driver(monkeypatch, "sqlite")
    assert get_dialect().portable_sql(sql) == (
        "INSERT INTO items(payload, created_at) VALUES (:payload, CURRENT_TIMESTAMP)"
    )


def test_insert_returns_each_sqlalchemy_dialect_builder(monkeypatch) -> None:
    items = table("items", column("id", Integer))

    _select_driver(monkeypatch, "postgresql")
    assert isinstance(get_dialect().insert(items), PostgreSQLInsert)

    _select_driver(monkeypatch, "sqlite")
    assert isinstance(get_dialect().insert(items), SQLiteInsert)


async def test_sqlite_scheduler_job_lock_is_fail_open(monkeypatch) -> None:
    _select_driver(monkeypatch, "sqlite")

    async with get_dialect().scheduler_job_lock("dialect-layer-test") as acquired:
        assert acquired is True
