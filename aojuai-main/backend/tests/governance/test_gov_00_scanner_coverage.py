from pathlib import Path

from governance_tools.alembic_checks import discover_migration_files
from governance_tools.menu_routes import discover_menu_source_files, discover_next_pages, extract_menu_paths
from governance_tools.runtime_env import scan_runtime_env_access
from governance_tools.soft_delete_uniqueness import discover_model_modules


def test_gov_00_runtime_scanner_discovers_new_deep_repository_module(backend_root: Path) -> None:
    probe_dir = backend_root / "app" / "domain" / "_mutation_probe"
    probe = probe_dir / "service.py"
    relative = probe.relative_to(backend_root).as_posix()
    assert not probe.exists(), f"stale governance probe exists: {probe}"

    try:
        probe_dir.mkdir(parents=True)
        probe.write_text("MUTATION_PROBE = True\n", encoding="utf-8")
        result = scan_runtime_env_access(backend_root)
        assert relative in result.discovered
    finally:
        if probe.exists():
            probe.unlink()
        if probe_dir.exists():
            probe_dir.rmdir()

    assert not probe.exists()


def test_gov_00_other_filesystem_scanners_discover_new_repository_probes(
    backend_root: Path,
    repo_root: Path,
) -> None:
    migration = backend_root / "alembic" / "versions" / "_mutation_probe.py"
    model_dir = backend_root / "app" / "domain" / "_mutation_probe"
    model = model_dir / "models.py"
    menu_source = backend_root / "scripts" / "_mutation_probe_seed.py"
    page_dir = repo_root / "frontend" / "src" / "app" / "(app)" / "_mutation_probe"
    page = page_dir / "page.tsx"

    probes = (migration, model, menu_source, page)
    assert not any(probe.exists() for probe in probes), f"stale governance probe exists: {probes}"
    try:
        migration.write_text("def upgrade():\n    pass\n", encoding="utf-8")
        model_dir.mkdir(parents=True)
        model.write_text('class Probe:\n    __tablename__: str = "gov_probe"\n', encoding="utf-8")
        menu_source.write_text(
            'SQL = "INSERT INTO menus (path) VALUES (:path)"\nMENU = {"path": "/_mutation_probe"}\n',
            encoding="utf-8",
        )
        page_dir.mkdir(parents=True)
        page.write_text("export default function Probe() { return null }\n", encoding="utf-8")

        assert migration in discover_migration_files(backend_root)
        assert "app.domain._mutation_probe.models" in discover_model_modules(backend_root)
        assert any(item.source.endswith("/_mutation_probe/page.tsx") for item in discover_next_pages(repo_root))
        assert menu_source in discover_menu_source_files(backend_root)
        assert any(item.path == "/_mutation_probe" for item in extract_menu_paths(menu_source, backend_root))
    finally:
        for probe in probes:
            if probe.exists():
                probe.unlink()
        for directory in (model_dir, page_dir):
            if directory.exists():
                directory.rmdir()
