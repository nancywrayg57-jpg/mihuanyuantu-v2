"""SQLite 基线之后的 base 迁移必须双方言（存量 SQLite 库要靠它们升级，不能只靠新库 create_all+stamp）。

2026-08-28 实测：日报实例（SQLite）合并新 base 后 `/message-channels` 500——库停在旧 head，
而 5 条新迁移写了 `postgresql.JSONB(` / `::jsonb` / `now()` / `= ANY(` 等 PG 专有语法，`alembic upgrade` 在 SQLite 上直接炸。
这里做静态扫描把这类写法挡在提交前；真正跑通与否由 `docs/dev/issues/SQLITE_LIGHTWEIGHT_DEPLOY_PITFALLS.md §10` 的手工流程核对。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
#: SQLite 基线（d3882e12，2026-08-27）之前的迁移是 PG 专有历史，不重放；之后的都要双方言
BASELINE_REVISION = "base_20260809_system_menu_backfill"

FORBIDDEN = (
    (re.compile(r"^(?![^\n]*with_variant)[^\n]*postgresql\.JSONB\(", re.M), "postgresql.JSONB(...) 需写成 sa.JSON().with_variant(postgresql.JSONB(...), 'postgresql')"),
    (re.compile(r"::jsonb"), "'::jsonb' 只在 dialect == postgresql 分支里出现"),
    (re.compile(r"sa\.text\(\s*\"now\(\)\"\s*\)"), "server_default 用 sa.func.now()"),
    (re.compile(r"=\s*ANY\(:"), "= ANY(:x) 改 IN :x + bindparam(expanding=True)"),
    (re.compile(r"information_schema|to_regclass|pg_indexes"), "表/列存在性用 sa.inspect(conn).has_table / get_columns"),
)


def _post_baseline_migrations() -> list[Path]:
    files = sorted(VERSIONS.glob("base_*.py"))
    names = [f.stem for f in files]
    assert BASELINE_REVISION in names, "基线迁移不见了？"
    return files[names.index(BASELINE_REVISION) + 1 :]


def _dialect_branched(source: str) -> bool:
    return 'dialect.name == "sqlite"' in source or "dialect.name != \"postgresql\"" in source or "_sql(" in source


@pytest.mark.parametrize("path", _post_baseline_migrations(), ids=lambda p: p.stem)
def test_post_baseline_migration_is_dual_dialect(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    branched = _dialect_branched(source)
    problems = []
    for pattern, hint in FORBIDDEN:
        for m in pattern.finditer(source):
            line = source.count("\n", 0, m.start()) + 1
            # 已按方言分支的文件里，PG 专有写法允许出现在 PG 分支内
            if branched and pattern.pattern in (r"::jsonb", r"information_schema|to_regclass|pg_indexes"):
                continue
            problems.append(f"{path.name}:{line}: {hint}")
    assert not problems, "\n".join(problems)
