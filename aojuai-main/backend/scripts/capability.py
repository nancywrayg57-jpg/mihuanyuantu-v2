#!/usr/bin/env python3
"""Install-time orchestration for independently migrated capability packages."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.capability_registry import (  # noqa: E402
    CapabilityDefinition,
    capability_by_code,
    discover_capabilities,
)
from app.core.capability_runtime import (  # noqa: E402
    installed_capabilities,
    sync_installed_capabilities,
)
from app.core.config import settings  # noqa: E402
from app.core.feature_switches import MODULE_CATALOG, is_module_installed  # noqa: E402
from app.infrastructure.database import get_db_context  # noqa: E402
from app.infrastructure.database.dialect import get_dialect  # noqa: E402

ADVISORY_LOCK_ID = 4_704_558_201
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _alembic_config(script_location: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(script_location.resolve()))
    config.set_main_option("prepend_sys_path", str(BACKEND_DIR))
    return config


def _core_config() -> Config:
    return _alembic_config(BACKEND_DIR / "alembic")


def _capability_config(definition: CapabilityDefinition) -> Config:
    return _alembic_config(definition.migration_path())


def _static_head(config: Config, label: str) -> str:
    heads = tuple(ScriptDirectory.from_config(config).get_heads())
    if len(heads) != 1:
        rendered = ", ".join(heads) or "<none>"
        raise RuntimeError(
            f"{label}: expected exactly one migration head, found {len(heads)}: {rendered}"
        )
    return heads[0]


def _database_heads(connection: Any, version_table: str) -> tuple[str, ...]:
    if not IDENTIFIER_RE.fullmatch(version_table):
        raise RuntimeError(f"unsafe Alembic version table: {version_table!r}")
    # 用 inspector 而不是 PostgreSQL 的 to_regclass：轻量部署下同一份代码要能跑 SQLite。
    if not sa_inspect(connection).has_table(version_table):
        return ()
    rows = connection.execute(
        text(f'SELECT version_num FROM "{version_table}" ORDER BY version_num')
    ).scalars()
    return tuple(str(value) for value in rows)


def _verify_upgraded_chain(
    connection: Any,
    *,
    config: Config,
    label: str,
    version_table: str,
) -> str:
    expected = _static_head(config, label)
    current = _database_heads(connection, version_table)
    if current != (expected,):
        rendered = ", ".join(current) or "<none>"
        raise RuntimeError(
            f"{label}: database must be at its single head {expected!r}, found {rendered}"
        )
    return expected


def _validate_installed_dependencies(
    definitions: tuple[CapabilityDefinition, ...],
) -> None:
    installed = {definition.code for definition in definitions}
    base_dependencies = {"core", "assistant", "speech", "public_site"}
    for definition in definitions:
        missing = set(definition.dependencies) - installed - base_dependencies
        if missing:
            raise RuntimeError(
                f"{definition.code}: missing installed dependencies: {', '.join(sorted(missing))}"
            )


def list_modules() -> int:
    print("code\tlayer\tinstalled\tversion")
    declarations = {
        definition.code: definition
        for definition in discover_capabilities()
    }
    for item in MODULE_CATALOG:
        declaration = declarations.get(item.code)
        installed = is_module_installed(item.code)
        version = declaration.version if declaration else "core"
        print(f"{item.code}\t{item.layer}\t{str(installed).lower()}\t{version}")
    return 0


def show_heads() -> int:
    had_error = False
    chains: list[tuple[str, Config]] = [("core", _core_config())]
    chains.extend(
        (definition.code, _capability_config(definition))
        for definition in installed_capabilities()
    )
    for label, config in chains:
        heads = tuple(ScriptDirectory.from_config(config).get_heads())
        print(f"{label}: {', '.join(heads) or '<none>'}")
        had_error = had_error or len(heads) != 1
    return 1 if had_error else 0


@contextmanager
def _migration_lock(connection: Any) -> Iterator[None]:
    """跨进程的迁移互斥锁，按方言选实现。

    - PostgreSQL：会话级 advisory lock，和原来行为一致。
    - SQLite：advisory lock 不存在，改用数据库文件旁的 flock。内存库没有文件、
      也不可能被别的进程共享，直接放行。
    - 其它方言：不假装有锁，直接放行并由调用方自行串行化。
    """
    dialect = get_dialect()
    if dialect.supports_advisory_lock:
        connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID})
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID})
            connection.commit()
        return

    if dialect.single_writer:
        db_path = connection.engine.url.database
        if not db_path or db_path == ":memory:":
            yield
            return
        import fcntl

        lock_file = Path(f"{db_path}.migrate.lock")
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        with lock_file.open("w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
        connection.commit()
        return

    yield
    connection.commit()


def _bootstrap_core_on_sqlite(connection: Any, config: Config) -> str | None:
    """SQLite 新库的核心 schema 引导。

    核心链里有一批 PostgreSQL 专有的历史迁移（JSONB / ::jsonb / information_schema），
    在 SQLite 上不可重放。轻量部署的约定是：新库用 ORM metadata 建全表，直接 stamp 到
    core head，之后只由"双方言"的新迁移接管——与 `init_db()` 的 SQLite 分支同一套语义。

    返回 stamp 上去的 head；库已经被 Alembic 管理过则返回 None（交回正常 upgrade 流程）。
    """
    if sa_inspect(connection).has_table("alembic_version"):
        stamped = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        if stamped:
            return None

    import app.domain  # noqa: F401  # 注册全部核心模型
    from app.infrastructure.database.session import Base

    Base.metadata.create_all(bind=connection)

    head = ScriptDirectory.from_config(config).get_current_head()
    if not head:
        return None
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(255) NOT NULL PRIMARY KEY)"
    )
    connection.exec_driver_sql("DELETE FROM alembic_version")
    connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES (?)", (head,))
    connection.commit()
    return head


def upgrade_database() -> int:
    definitions = installed_capabilities()
    _validate_installed_dependencies(definitions)
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    try:
        with engine.connect() as lock_connection, _migration_lock(lock_connection):
            core_config = _core_config()
            _static_head(core_config, "core")
            bootstrapped = None
            if get_dialect().single_writer:
                bootstrapped = _bootstrap_core_on_sqlite(lock_connection, core_config)
            if bootstrapped:
                print(f"core bootstrapped (sqlite create_all + stamp): {bootstrapped}")
            else:
                command.upgrade(core_config, "head")
            core_head = _verify_upgraded_chain(
                lock_connection,
                config=core_config,
                label="core",
                version_table="alembic_version",
            )
            if not bootstrapped:
                print(f"core upgraded: {core_head}")

            for definition in definitions:
                config = _capability_config(definition)
                _static_head(config, definition.code)
                command.upgrade(config, "head")
                head = _verify_upgraded_chain(
                    lock_connection,
                    config=config,
                    label=definition.code,
                    version_table=definition.version_table,
                )
                print(f"{definition.code} upgraded: {head}")
    finally:
        engine.dispose()
    return 0


def purge_database(code: str, *, purge: bool) -> int:
    """Explicitly destroy one uninstalled capability schema and its data."""

    if not purge:
        raise RuntimeError("refusing destructive downgrade without explicit --purge")
    definition = capability_by_code(code)
    if definition is None:
        raise RuntimeError(f"unknown capability: {code}")
    if is_module_installed(definition.code):
        raise RuntimeError(f"{definition.code} is still installed; remove it from AOJ_ENABLED_MODULES first")

    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    try:
        with engine.connect() as lock_connection, _migration_lock(lock_connection):
            config = _capability_config(definition)
            _static_head(config, definition.code)
            command.downgrade(config, "base")
            current = _database_heads(lock_connection, definition.version_table)
            if current:
                raise RuntimeError(f"{definition.code}: purge left migration revisions: {current!r}")
            print(f"{definition.code} purged; capability tables and data were deleted")
    finally:
        engine.dispose()
    return 0


async def _sync() -> int:
    _validate_installed_dependencies(installed_capabilities())
    async with get_db_context() as db:
        outcomes = await sync_installed_capabilities(db)
    if not outcomes:
        print("no installed capability seeds")
        return 0
    for code, tenant_outcomes in outcomes.items():
        changed = sum(int(outcome.changed) for _, outcome in tenant_outcomes)
        print(f"{code}: tenants={len(tenant_outcomes)}, changed={changed}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list catalog modules and installation state")
    subparsers.add_parser("sync", help="idempotently reconcile installed capability data")
    subparsers.add_parser("heads", help="print the head of core and each installed chain")
    db_parser = subparsers.add_parser("db", help="database schema operations")
    db_subparsers = db_parser.add_subparsers(dest="db_command", required=True)
    db_subparsers.add_parser("upgrade", help="upgrade core then every installed capability")
    purge_parser = db_subparsers.add_parser(
        "purge",
        help="destructively downgrade one uninstalled capability to base",
    )
    purge_parser.add_argument("code")
    purge_parser.add_argument(
        "--purge",
        action="store_true",
        help="required acknowledgement that capability tables and data will be deleted",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list":
            return list_modules()
        if args.command == "heads":
            return show_heads()
        if args.command == "sync":
            return asyncio.run(_sync())
        if args.command == "db" and args.db_command == "upgrade":
            return upgrade_database()
        if args.command == "db" and args.db_command == "purge":
            return purge_database(args.code, purge=args.purge)
    except Exception as exc:
        print(f"capability error: {exc}", file=sys.stderr)
        return 1
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
