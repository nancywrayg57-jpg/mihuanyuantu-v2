"""GOV-13 and GOV-08 checks over the real Alembic graph and migration files."""

from __future__ import annotations

import ast
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from .common import ScanResult, Violation, require_discovered


def _script_directory(backend_root: Path) -> ScriptDirectory:
    ini_path = backend_root / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return ScriptDirectory.from_config(config)


def scan_single_alembic_head(backend_root: Path) -> ScanResult:
    script = _script_directory(backend_root.resolve())
    revisions = tuple(sorted(revision.revision for revision in script.walk_revisions()))
    require_discovered("GOV-13", revisions, "Alembic revisions")
    heads = tuple(script.get_heads())
    violations: tuple[Violation, ...] = ()
    if len(heads) != 1:
        violations = (
            Violation(
                "GOV-13",
                "alembic/versions",
                0,
                f"expected exactly one Alembic head, found {len(heads)}: {', '.join(heads) or '<none>'}",
            ),
        )
    return ScanResult("GOV-13", revisions, violations)


def discover_migration_files(backend_root: Path) -> tuple[Path, ...]:
    versions = backend_root / "alembic" / "versions"
    return tuple(sorted(path for path in versions.glob("*.py") if path.is_file()))


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _updated_at_column(node: ast.Call) -> bool:
    if _call_name(node.func) != "Column":
        return False
    name_node = (
        node.args[0]
        if node.args
        else next(
            (keyword.value for keyword in node.keywords if keyword.arg == "name"),
            None,
        )
    )
    if not isinstance(name_node, ast.Constant) or name_node.value != "updated_at":
        return False
    nullable = next((keyword.value for keyword in node.keywords if keyword.arg == "nullable"), None)
    return nullable is not None and _is_false(nullable)


def scan_updated_at_nullability(backend_root: Path) -> ScanResult:
    backend_root = backend_root.resolve()
    targets = discover_migration_files(backend_root)
    discovered = tuple(path.relative_to(backend_root).as_posix() for path in targets)
    require_discovered("GOV-08", discovered, "migration files")
    violations: list[Violation] = []

    for path, relative in zip(targets, discovered, strict=True):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            violations.append(Violation("GOV-08", relative, 0, f"cannot parse migration: {exc}"))
            continue
        upgrades = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "upgrade"
        ]
        for upgrade in upgrades:
            for node in ast.walk(upgrade):
                if isinstance(node, ast.Call) and _updated_at_column(node):
                    violations.append(
                        Violation(
                            "GOV-08",
                            relative,
                            node.lineno,
                            'upgrade() creates "updated_at" with nullable=False',
                        )
                    )
    return ScanResult("GOV-08", discovered, tuple(violations))
