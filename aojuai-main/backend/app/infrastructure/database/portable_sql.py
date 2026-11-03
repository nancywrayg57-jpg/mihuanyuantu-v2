"""把 seed / 运维脚本里的 PostgreSQL 习惯写法按方言改写，让同一段 SQL 在 SQLite 轻量档也能跑。

只覆盖仓库内实际出现的三种写法；业务代码请直接用 ORM/`PortableJSON`，不要依赖这里。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from app.infrastructure.database.dialect import get_dialect


def portable_sql(sql: str) -> str:
    return get_dialect().portable_sql(sql)


def ptext(sql: str) -> TextClause:
    """`text()` 的方言安全版。"""
    return text(portable_sql(sql))


def json_column_value(value: object, default: object | None = None) -> object:
    """raw SQL 读出的 JSON 列：PG(JSONB) 已是 dict/list，SQLite(JSON=TEXT) 是字符串，这里统一。"""
    import json

    if value is None:
        return {} if default is None else default
    if isinstance(value, (str, bytes, bytearray)):
        parsed = json.loads(value)
        return ({} if default is None else default) if parsed is None else parsed
    return value


async def escalate_to_write_lock(db: object) -> None:
    """`SELECT … FOR UPDATE` 的 SQLite 等价物：在读取前先拿写锁（RESERVED），让并发写者串行化并读到最新值。

    SQLite 方言会忽略 FOR UPDATE；缺省 deferred 事务下"先读快照再写"会以 `database is locked`
    （SQLITE_BUSY_SNAPSHOT）失败。先执行一条无副作用的写语句即可提前进入写事务（busy_timeout 内排队）。
    必须在该事务的第一条读语句之前调用；PG 下是 no-op。
    """
    await get_dialect().escalate_to_write_lock(db)


def dialect_insert(table: object):
    """带 `on_conflict_do_nothing / on_conflict_do_update` 的 INSERT：PG 与 SQLite 各自的方言构造器，接口一致。"""
    return get_dialect().insert(table)


async def table_exists(db: object, table_name: str) -> bool:
    """当前库里是否有这张表：PG 查 information_schema（current_schema），SQLite 查 sqlite_master。"""
    return await get_dialect().table_exists(db, table_name)


async def column_exists(db: object, table_name: str, column_name: str) -> bool:
    return await get_dialect().column_exists(db, table_name, column_name)


async def index_exists(db: object, table_name: str, index_name: str) -> bool:
    """当前库里是否有指定索引。"""
    return await get_dialect().index_exists(db, table_name, index_name)
