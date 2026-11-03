"""应用代码的双方言静态门禁：PG 专有写法只允许出现在 infrastructure 的可移植助手或明确按方言分支的文件里。

与 `test_sqlite_migration_portability.py` 成对：那边守迁移，这边守 ORM / raw SQL。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

#: 允许直接写 PG 专有语法的文件（它们内部按方言分支，或本身就是可移植助手）
ALLOWED = {
    "infrastructure/database/dialect.py",
    "infrastructure/database/types.py",
    "infrastructure/database/portable_sql.py",
    "infrastructure/database/session.py",
    "core/task_queue.py",
    "api/v1/endpoints/credits.py",  # 灰度对账：已用 require_postgresql 门控
}

# 方言选择本身只能留在收口层、配置计算字段与显式 PG-only 功能登记处。
DIALECT_JUDGMENT_ALLOWED = {
    "core/config.py",
    "core/dialect_features.py",
}

DIALECT_JUDGMENT_FORBIDDEN = (
    re.compile(r"\bIS_SQLITE\b"),
    re.compile(r"\bdialect\.name\b"),
    re.compile(r"\bDB_DRIVER\b"),
)

FORBIDDEN = (
    (re.compile(r"\.astext\b"), "用 col['k'].as_string() / as_integer()"),
    (re.compile(r"=\s*ANY\(:"), "= ANY(:x) → IN :x + bindparam(expanding=True)"),
    (re.compile(r"::jsonb|::json\b"), "去掉 ::jsonb；JSON 列用 PortableJSON"),
    (re.compile(r"func\.(greatest|least|date_trunc|array_agg|string_agg|jsonb_[a-z_]+|to_tsvector)\("), "用 types.greatest_of 等可移植助手，或按方言分支"),
    (re.compile(r"\.op\(['\"](@>|<@|\?|\|\||#>>|->>)['\"]\)"), "JSON 运算用 json_array_contains / json_merge_patch"),
    (re.compile(r"from sqlalchemy\.dialects\.postgresql import [^\n]*\b(insert|JSONB|ARRAY)\b"), "用 dialect_insert / PortableJSON"),
    (re.compile(r"pg_try_advisory|pg_advisory"), "用 task_queue.scheduler_job_lock"),
    (re.compile(r"information_schema|to_regclass"), "用 portable_sql.table_exists / column_exists"),
    (re.compile(r"\bDateTime\(timezone=True\)"), "模型列用 PortableDateTime()"),
)


def _app_files() -> list[Path]:
    return sorted(p for p in APP.rglob("*.py") if "/migrations/" not in str(p) and "__pycache__" not in str(p))


def _dialect_neutral_app_files() -> list[Path]:
    files = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP)
        rel_text = str(rel)
        if "__pycache__" in rel.parts or "migrations" in rel.parts:
            continue
        if rel.parts[:2] == ("infrastructure", "database"):
            continue
        if rel_text in DIALECT_JUDGMENT_ALLOWED:
            continue
        files.append(path)
    return sorted(files)


@pytest.mark.parametrize("path", _app_files(), ids=lambda p: str(p.relative_to(APP)))
def test_app_code_has_no_unguarded_pg_only_constructs(path: Path) -> None:
    rel = str(path.relative_to(APP))
    if rel in ALLOWED:
        pytest.skip("按方言分支的助手/门控文件")
    source = path.read_text(encoding="utf-8")
    problems = []
    for pattern, hint in FORBIDDEN:
        for m in pattern.finditer(source):
            line_no = source.count("\n", 0, m.start()) + 1
            line = source.splitlines()[line_no - 1]
            if line.lstrip().startswith("#") or "noqa: pg-only" in line:
                continue
            problems.append(f"{rel}:{line_no}: {hint} -> {line.strip()[:100]}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", _dialect_neutral_app_files(), ids=lambda p: str(p.relative_to(APP)))
def test_app_code_does_not_select_database_dialect_directly(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    problems = []
    for pattern in DIALECT_JUDGMENT_FORBIDDEN:
        for match in pattern.finditer(source):
            line_no = source.count("\n", 0, match.start()) + 1
            line = source.splitlines()[line_no - 1]
            problems.append(
                f"{path.relative_to(APP)}:{line_no}: 方言判断必须收口到 infrastructure/database -> "
                f"{line.strip()[:100]}"
            )
    assert not problems, "\n".join(problems)
