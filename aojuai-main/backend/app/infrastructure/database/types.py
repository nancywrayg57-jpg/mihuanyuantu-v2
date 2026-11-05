"""跨方言列类型（PostgreSQL 主档 / SQLite 轻量档）。

- PortableJSON：以 JSONB 为基座（PG 语义、比较器、autogenerate 完全不变），SQLite 落 JSON(TEXT)。
  ORM 取值用 `col["key"].as_string()` / `.as_integer()`；PG 专有运算（`@>`、`?`、`.astext`）不要直接用，
  数组成员判断用 `json_array_contains()`。
- PortablePK：PG BIGINT，SQLite INTEGER（否则拿不到自增 rowid）。
- PortableDateTime：PG `timestamptz` 原样；SQLite 存 UTC naive、读回补 UTC tzinfo，保证 Python 侧比较不混用 naive/aware。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import JSON, TypeDecorator

from app.infrastructure.database.dialect import get_dialect

PortableJSON = JSONB().with_variant(JSON(), "sqlite")
PortablePK = BigInteger().with_variant(Integer(), "sqlite")


class PortableDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None or dialect.name != "sqlite":
            return value
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None or dialect.name != "sqlite":
            return value
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


def is_sqlite_dialect(bind: Any) -> bool:
    dialect = getattr(bind, "dialect", None) or getattr(getattr(bind, "engine", None), "dialect", None)
    return bool(dialect is not None and dialect.name == "sqlite")


def json_array_contains(column: Any, value: Any) -> ColumnElement[bool]:
    """`column`（JSON 数组）是否包含标量 `value`：PG `@>`，SQLite `json_each`。按当前配置的方言分派。"""
    return get_dialect().json_array_contains(column, value)


def json_merge_patch(column: Any, patch: dict[str, Any]) -> ColumnElement[Any]:
    """在数据库里把 `patch` 合并进 JSON 对象列（读到的永远是当前值，不用先读后写）。

    PG：`col || patch::jsonb`（浅合并）；SQLite：`json_patch(col, patch)`（RFC 7396：
    顶层键覆盖，与浅合并一致；差异只在 patch 里的 null 会删除键、嵌套对象会递归合并）。
    """
    return get_dialect().json_merge_patch(column, patch)


def greatest_of(*exprs: Any) -> ColumnElement[Any]:
    """PG `greatest(a, b, …)`；SQLite 没有 greatest，多参数标量 `max(a, b, …)` 等价。"""
    return get_dialect().greatest(*exprs)
