"""GOV-09: soft-deleted rows must not block reuse of business keys."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

from sqlalchemy import Index, UniqueConstraint

from .common import ScanResult, Violation, require_discovered, validate_allowlist

# Keys are ``<table>.<constraint-or-index>``. Add only genuinely permanent identities,
# with a durable business reason. The base repository currently needs no exception.
PERMANENT_UNIQUENESS_ALLOWLIST: dict[str, str] = {}


def discover_model_modules(backend_root: Path) -> tuple[str, ...]:
    modules: list[str] = []
    app_root = backend_root / "app"
    for path in sorted(app_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        declares_table = any(
            (
                isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "__tablename__" for target in node.targets)
            )
            or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "__tablename__"
            )
            for node in ast.walk(tree)
        )
        if declares_table:
            modules.append(".".join(path.relative_to(backend_root).with_suffix("").parts))
    return tuple(modules)


def _has_deleted_at_filter(index: Index) -> bool:
    where = index.dialect_options["postgresql"].get("where")
    if where is None:
        return False
    normalized = " ".join(str(where).lower().replace('"', "").split())
    return "deleted_at is null" in normalized


def scan_soft_delete_uniqueness(
    backend_root: Path | None = None,
    *,
    registry: Any | None = None,
    allowlist: dict[str, str] | None = None,
) -> ScanResult:
    allowed = PERMANENT_UNIQUENESS_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-09", allowed)

    if registry is None:
        if backend_root is None:
            raise ValueError("backend_root is required when registry is not supplied")
        backend_root = backend_root.resolve()
        modules = discover_model_modules(backend_root)
        require_discovered("GOV-09", modules, "SQLAlchemy model modules")
        for module in modules:
            importlib.import_module(module)
        from app.infrastructure.database.session import Base

        registry = Base.registry

    soft_delete_mappers = tuple(
        sorted(
            (mapper for mapper in registry.mappers if "deleted_at" in mapper.local_table.c),
            key=lambda mapper: mapper.local_table.name,
        )
    )
    discovered = tuple(mapper.local_table.name for mapper in soft_delete_mappers)
    require_discovered("GOV-09", discovered, "mapped models containing deleted_at")

    violations: list[Violation] = []
    for mapper in soft_delete_mappers:
        table = mapper.local_table
        candidates = list(table.constraints) + list(table.indexes)
        for item in candidates:
            is_unique = isinstance(item, UniqueConstraint) or isinstance(item, Index) and item.unique
            if not is_unique:
                continue
            columns = ",".join(column.name for column in item.columns)
            item_name = item.name or f"unnamed({columns})"
            key = f"{table.name}.{item_name}"
            if key in allowed:
                continue
            if isinstance(item, Index) and _has_deleted_at_filter(item):
                continue
            violations.append(
                Violation(
                    "GOV-09",
                    mapper.class_.__module__.replace(".", "/") + ".py",
                    0,
                    f"{key} is unique without postgresql_where=(deleted_at IS NULL)",
                )
            )
    return ScanResult("GOV-09", discovered, tuple(violations))
