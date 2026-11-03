"""GOV-18 的变异测试：三种"漏声明"都必须被抓住。

用 tmp_path 搭一个只有两个文件的假 backend root——扫描器是纯静态解析，
不需要真的应用代码。这样变异测试不会碰到仓库本体。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from governance_tools.module_manifest_check import scan_module_manifests

_CATALOG_TEMPLATE = '''
_BUILTIN_MODULE_CATALOG: tuple[ModuleCatalogItem, ...] = (
{entries}
)
'''

_MANIFEST_TEMPLATE = '''
BUILTIN_MODULE_MANIFESTS: tuple[BuiltinModuleManifest, ...] = (
{entries}
)
'''


def _catalog_entry(code: str) -> str:
    return f'    ModuleCatalogItem(code="{code}", label="x", description="x"),'


def _manifest_entry(
    code: str,
    *,
    code_paths: str = '("app/domain/x",)',
    model_modules: str = '("app.domain.x.models",)',
    table_prefixes: str = '("x_",)',
) -> str:
    return (
        f"    BuiltinModuleManifest(\n"
        f'        code="{code}",\n'
        f"        code_paths={code_paths},\n"
        f"        model_modules={model_modules},\n"
        f"        table_prefixes={table_prefixes},\n"
        f"    ),"
    )


def _write_fake_backend(root: Path, *, catalog: list[str], manifests: list[str]) -> Path:
    core = root / "app" / "core"
    core.mkdir(parents=True, exist_ok=True)
    (core / "feature_switches.py").write_text(
        _CATALOG_TEMPLATE.format(entries="\n".join(catalog)), encoding="utf-8"
    )
    (core / "module_manifest.py").write_text(
        _MANIFEST_TEMPLATE.format(entries="\n".join(manifests)), encoding="utf-8"
    )
    return root


def test_gov_18_passes_when_every_builtin_declares_its_boundary(tmp_path: Path) -> None:
    root = _write_fake_backend(
        tmp_path,
        catalog=[_catalog_entry("speech"), _catalog_entry("public_site")],
        manifests=[_manifest_entry("speech"), _manifest_entry("public_site")],
    )
    result = scan_module_manifests(root)
    assert result.discovered == ("speech", "public_site")
    assert result.violations == ()


def test_gov_18_catches_missing_manifest(tmp_path: Path) -> None:
    root = _write_fake_backend(
        tmp_path,
        catalog=[_catalog_entry("speech"), _catalog_entry("public_site")],
        manifests=[_manifest_entry("speech")],
    )
    violations = scan_module_manifests(root).violations
    assert len(violations) == 1
    assert "public_site" in violations[0].message
    assert "no BuiltinModuleManifest" in violations[0].message


@pytest.mark.parametrize("field", ["code_paths", "model_modules", "table_prefixes"])
def test_gov_18_catches_empty_required_field(tmp_path: Path, field: str) -> None:
    root = _write_fake_backend(
        tmp_path,
        catalog=[_catalog_entry("speech")],
        manifests=[_manifest_entry("speech", **{field: "()"})],
    )
    violations = scan_module_manifests(root).violations
    assert len(violations) == 1
    assert f"declares no {field}" in violations[0].message


def test_gov_18_catches_manifest_for_unknown_module(tmp_path: Path) -> None:
    """清单里留着已删模块的条目也算漂移——它会让 absent_table_prefixes 永久多一条。"""
    root = _write_fake_backend(
        tmp_path,
        catalog=[_catalog_entry("speech")],
        manifests=[_manifest_entry("speech"), _manifest_entry("ghost")],
    )
    violations = scan_module_manifests(root).violations
    assert len(violations) == 1
    assert "'ghost'" in violations[0].message
