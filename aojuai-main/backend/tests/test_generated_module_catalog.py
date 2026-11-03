from __future__ import annotations

import json

from scripts.export_module_catalog import OUTPUT_PATH, exportable_module_catalog


def test_generated_frontend_catalog_matches_backend_source() -> None:
    generated = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    # Any backend catalog edit must regenerate the checked-in frontend fallback;
    # otherwise this contract test fails before another hand-maintained drift ships.
    assert generated == exportable_module_catalog()
