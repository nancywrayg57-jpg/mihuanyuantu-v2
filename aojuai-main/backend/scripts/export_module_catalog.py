#!/usr/bin/env python3
"""Export the backend feature catalog as the frontend's offline fallback."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = BACKEND_DIR.parent
OUTPUT_PATH = REPOSITORY_DIR / "frontend" / "src" / "generated" / "module-catalog.json"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core import feature_switches  # noqa: E402


def _exportable_module_catalog_raw() -> dict[str, Any]:
    """Return the complete source catalog, independent of deployment filtering."""
    original = feature_switches.settings.AOJ_ENABLED_MODULES
    try:
        feature_switches.settings.AOJ_ENABLED_MODULES = ""
        feature_switches.clear_module_install_caches()
        return feature_switches.build_feature_catalog_definition(include_uninstalled=True)
    finally:
        feature_switches.settings.AOJ_ENABLED_MODULES = original
        feature_switches.clear_module_install_caches()


def render_module_catalog_json() -> str:
    return json.dumps(
        exportable_module_catalog(),
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render_module_catalog_json(), encoding="utf-8")


_RUNTIME_ONLY_KEYS = ("databaseDialect", "unavailableFeatures")


def exportable_module_catalog() -> dict:
    """静态兜底目录：剥掉运行时才确定的方言字段（databaseDialect / unavailableFeatures），
    它们不进 catalogDigest，前端在拿到 /tenants/current 之前按"全部可用"处理。"""
    catalog = dict(_exportable_module_catalog_raw())
    for key in _RUNTIME_ONLY_KEYS:
        catalog.pop(key, None)
    return catalog

if __name__ == "__main__":
    main()
