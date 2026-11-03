from pathlib import Path

import pytest

from governance_tools.common import assert_clean
from governance_tools.menu_routes import discover_next_pages, scan_menu_routes


def _write_page(repo: Path, relative: str) -> None:
    page = repo / "frontend" / "src" / "app" / "(app)" / relative / "page.tsx"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("export default function Page() { return null }\n", encoding="utf-8")


def _write_menu_source(repo: Path, paths: list[str]) -> None:
    source = repo / "backend" / "scripts" / "seed_probe.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    entries = ", ".join(repr({"path": path}) for path in paths)
    source.write_text(
        f'SQL = "INSERT INTO menus (path) VALUES (:path)"\nMENUS = [{entries}]\n',
        encoding="utf-8",
    )


def test_gov_06_repository_menu_paths_match_next_pages(repo_root: Path) -> None:
    result = scan_menu_routes(repo_root)
    assert result.discovered
    assert_clean(result)


def test_gov_06_route_discovery_handles_groups_dynamic_and_catch_all(tmp_path: Path) -> None:
    _write_page(tmp_path, "(admin)/users/[id]")
    _write_page(tmp_path, "docs/[...slug]")
    _write_page(tmp_path, "optional/[[...slug]]")

    patterns = {page.pattern for page in discover_next_pages(tmp_path)}

    assert patterns == {"/users/[id]", "/docs/[...slug]", "/optional/[[...slug]]"}


def test_gov_06_mutation_unknown_menu_path_makes_target_assertion_red(tmp_path: Path) -> None:
    _write_page(tmp_path, "known")
    _write_menu_source(tmp_path, ["/known", "/missing"])

    result = scan_menu_routes(tmp_path, menu_allowlist={}, hidden_page_allowlist={})

    with pytest.raises(AssertionError, match="menu path '/missing' resolves to no"):
        assert_clean(result)


def test_gov_06_mutation_unlisted_page_makes_target_assertion_red(tmp_path: Path) -> None:
    _write_page(tmp_path, "known")
    _write_page(tmp_path, "internal-new-page")
    _write_menu_source(tmp_path, ["/known"])

    result = scan_menu_routes(tmp_path, menu_allowlist={}, hidden_page_allowlist={})

    with pytest.raises(AssertionError, match="internal-new-page.*neither a menu"):
        assert_clean(result)
