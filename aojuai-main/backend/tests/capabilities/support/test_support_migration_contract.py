"""迁移链合同：独立、单头、只建表、双方言。"""

from __future__ import annotations

import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.capabilities.support import CAPABILITY
from app.capabilities.support.models import SupportTicket, SupportTicketMessage

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "app"
    / "capabilities"
    / "support"
    / "migrations"
    / "versions"
    / "support_0001_initial.py"
)

#: 迁移必须在 SQLite 上也能重放（基座有轻量档），这些是 PG 专有写法。
PG_ONLY = (
    (re.compile(r"^(?![^\n]*with_variant)[^\n]*postgresql\.JSONB\(", re.M), "JSONB 要 with_variant"),
    (re.compile(r"::jsonb"), "去掉 ::jsonb"),
    (re.compile(r'sa\.text\(\s*"now\(\)"\s*\)'), "server_default 用 sa.func.now()"),
    (re.compile(r"information_schema|to_regclass|pg_indexes"), "用 sa.inspect(conn)"),
)


def _script() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(CAPABILITY.migration_path()))
    return ScriptDirectory.from_config(config)


def test_chain_is_independent_and_single_headed() -> None:
    script = _script()
    assert script.get_bases() == ["support_0001"]
    assert script.get_heads() == ["support_0001"]


def test_migration_creates_exactly_the_tables_the_models_declare() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    created = set(re.findall(r'op\.create_table\(\s*"([^"]+)"', source))
    assert created == {SupportTicket.__tablename__, SupportTicketMessage.__tablename__}


def test_migration_never_seeds_menus_or_switches() -> None:
    """菜单/权限/模块开关走 reconciler，不进迁移——迁移里写死一份就是第四套实现。"""
    source = MIGRATION.read_text(encoding="utf-8").lower()
    for forbidden in ("insert into menus", "role_menus", "feature_switches", "create_all"):
        assert forbidden not in source, forbidden


def test_migration_is_dual_dialect() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    problems = [
        f"{hint} @ line {source.count(chr(10), 0, match.start()) + 1}"
        for pattern, hint in PG_ONLY
        for match in pattern.finditer(source)
    ]
    assert not problems, problems


def test_soft_delete_unique_index_is_partial() -> None:
    """软删除表的业务唯一键必须带 `WHERE deleted_at IS NULL`，否则删掉的行还占着编号。"""
    source = MIGRATION.read_text(encoding="utf-8")
    assert "postgresql_where=sa.text(\"deleted_at IS NULL" in source
    assert "sqlite_where=sa.text(\"deleted_at IS NULL" in source


def test_updated_at_is_nullable() -> None:
    """GOV-08 的同一条规则：`updated_at` 必须可空（首次插入时它本来就没有值）。"""
    import ast

    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"), filename=str(MIGRATION))
    columns = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "Column"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "updated_at"
    ]
    assert columns, "迁移里没有 updated_at 列？"
    for column in columns:
        nullable = next(
            (keyword.value for keyword in column.keywords if keyword.arg == "nullable"), None
        )
        assert isinstance(nullable, ast.Constant) and nullable.value is True
