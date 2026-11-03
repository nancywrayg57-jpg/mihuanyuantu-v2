from __future__ import annotations

from pathlib import Path

import pytest

from scripts import new_module


def options(**overrides) -> new_module.ModuleOptions:  # noqa: ANN003
    values = {
        "code": "order_items",
        "layer": "sample",
        "route": "/order-items",
        "entity": "item",
        "permissions": ("read", "create", "update", "delete"),
    }
    values.update(overrides)
    return new_module.ModuleOptions(**values)


@pytest.mark.parametrize(
    "mutation",
    [
        {"code": "OrderItems"},
        {"code": "order-items"},
        {"route": "/order_items"},
        {"route": "order-items"},
        {"entity": "LineItem"},
        {"permissions": ("read", "sample-items:create")},
        {"code": "this_module_code_is_far_too_long_for_an_alembic_revision"},
    ],
)
def test_scaffold_validation_rejects_mutations_and_accepts_restored_input(
    mutation: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        new_module.validate_options(options(**mutation))
    new_module.validate_options(options())
    assert options().table_name == "cap_order_items"


def test_permission_parser_rejects_bad_format_and_restores_green() -> None:
    with pytest.raises(ValueError):
        new_module.parse_permissions("read,create-item")
    with pytest.raises(ValueError):
        new_module.parse_permissions("create,update")
    assert new_module.parse_permissions("read,create,update,delete") == (
        "read",
        "create",
        "update",
        "delete",
    )


def test_scaffold_generates_full_stack_without_touching_central_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = tmp_path / "backend"
    repository = tmp_path
    router = backend / "app" / "api" / "v1" / "__init__.py"
    catalog = backend / "app" / "core" / "feature_switches.py"
    router.parent.mkdir(parents=True)
    catalog.parent.mkdir(parents=True)
    router.write_text("ROUTER_SENTINEL\n", encoding="utf-8")
    catalog.write_text("CATALOG_SENTINEL\n", encoding="utf-8")

    monkeypatch.setattr(new_module, "BACKEND_DIR", backend)
    monkeypatch.setattr(new_module, "REPOSITORY_DIR", repository)
    created = new_module.generate(options())

    module = backend / "app" / "capabilities" / "order_items"
    # 断言"必须生成哪些文件"，不断言总数——加一个文件就红是脆断言，
    # 会让"补齐脚手架"这件事本身变成破坏性改动。
    required = [
        module / "__init__.py",
        module / "models.py",
        module / "service.py",
        module / "api.py",
        module / "access.py",
        module / "seed.py",
        module / "PRODUCTION_BLOCKED",
        module / "migrations" / "env.py",
        module / "migrations" / "versions" / "order_items_0001_initial.py",
        repository / "frontend" / "src" / "app" / "(app)" / "order-items" / "page.tsx",
        repository / "frontend" / "src" / "lib" / "order-items-api.ts",
        # 语言包：新模块开箱就该是 i18n-ready，否则每个模块都从硬编码中文起步
        repository / "frontend" / "src" / "lib" / "i18n" / "locales" / "order-items.ts",
    ]
    for path in required:
        assert path.is_file(), f"脚手架漏生成：{path.relative_to(repository)}"
    assert set(required) <= set(created)
    assert len(list((backend / "tests" / "capabilities" / "order_items").glob("test_*.py"))) == 4

    for path in created:
        if path.suffix == ".py":
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

    declaration = (module / "__init__.py").read_text(encoding="utf-8")
    migration = (module / "migrations" / "versions" / "order_items_0001_initial.py").read_text(encoding="utf-8")
    page = (repository / "frontend" / "src" / "app" / "(app)" / "order-items" / "page.tsx").read_text(encoding="utf-8")
    assert 'layer="sample"' in declaration
    assert "production_blocked=True" in declaration
    assert 'version_table="alembic_version_cap_order_items"' in declaration
    assert '"cap_order_items"' in migration
    assert "down_revision = None" in migration
    assert "postgresql_where" in migration
    assert "hasAnyPermission" in page
    assert router.read_text(encoding="utf-8") == "ROUTER_SENTINEL\n"
    assert catalog.read_text(encoding="utf-8") == "CATALOG_SENTINEL\n"

    with pytest.raises(FileExistsError):
        new_module.generate(options())
