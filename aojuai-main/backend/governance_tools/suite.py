"""Run every database-independent governance scanner."""

from __future__ import annotations

from pathlib import Path

from .alembic_checks import scan_single_alembic_head, scan_updated_at_nullability
from .common import ScanResult
from .doc_references import scan_doc_references
from .frontend_conventions import scan_frontend_conventions
from .locale_index import scan_locale_index
from .kernel_purity import scan_kernel_purity
from .menu_routes import scan_menu_routes
from .menu_title_i18n import scan_menu_title_i18n
from .page_guard_coverage import scan_page_guard_coverage
from .module_manifest_check import scan_module_manifests
from .runtime_env import scan_runtime_env_access
from .soft_delete_uniqueness import scan_soft_delete_uniqueness


def run_all_checks(backend_root: Path) -> tuple[ScanResult, ...]:
    backend_root = backend_root.resolve()
    return (
        scan_single_alembic_head(backend_root),
        scan_runtime_env_access(backend_root),
        scan_updated_at_nullability(backend_root),
        scan_soft_delete_uniqueness(backend_root),
        scan_menu_routes(backend_root.parent),
        scan_kernel_purity(backend_root),
        scan_doc_references(backend_root.parent),
        scan_frontend_conventions(backend_root.parent),
        scan_locale_index(backend_root.parent),
        scan_module_manifests(backend_root),
        scan_menu_title_i18n(backend_root.parent),
        scan_page_guard_coverage(backend_root.parent),
    )
