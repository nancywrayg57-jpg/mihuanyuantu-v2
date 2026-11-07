"""Browse-only legacy device-preset import catalog (FR-007 / 405 ops).

Reads desensitized JSON under 输入材料/. Does NOT mark MakerNote brands as
successfully imported into runtime presets.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# services/ → realphotos → capabilities → app → backend → aojuai-main → repo root
_REPO_ROOT = Path(__file__).resolve().parents[6]
_LEGACY_DIR = _REPO_ROOT / "输入材料" / "旧版可复用模块" / "02_设备参数" / "按旧分类"
_CATEGORIES = ("phone.json", "dslr.json", "mirrorless.json", "action.json")


@lru_cache(maxsize=1)
def _load_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    if not _LEGACY_DIR.is_dir():
        return ()
    for name in _CATEGORIES:
        path = _LEGACY_DIR / name
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for template in payload.get("templates") or []:
            if not isinstance(template, dict):
                continue
            provenance = template.get("provenance") or {}
            if not isinstance(provenance, dict):
                provenance = {}
            source_id = provenance.get("source_id")
            rows.append(
                {
                    "sourceId": source_id,
                    "templateRef": template.get("template_ref"),
                    "deviceDisplay": template.get("device_display"),
                    "legacyCategory": provenance.get("legacy_category")
                    or template.get("family_hint")
                    or payload.get("legacy_category"),
                    "visibility": provenance.get("legacy_visibility") or "UNKNOWN",
                    "activationStatus": template.get("activation_status") or "NOT_ACTIVATED",
                    "reviewBucket": template.get("review_bucket") or "UNKNOWN",
                    "reviewFlags": list(template.get("review_flags") or []),
                    "makerNoteImported": False,
                    "runtimeActivated": False,
                }
            )
    return tuple(rows)


def browse_legacy_imports(*, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """Paginated browse. importedBrands stays empty — no MakerNote activation claim."""
    size = max(1, min(int(page_size or 20), 100))
    current = max(1, int(page or 1))
    rows = list(_load_rows())
    total = len(rows)
    start = (current - 1) * size
    slice_rows = rows[start : start + size]
    return {
        "items": slice_rows,
        "total": total,
        "page": current,
        "pageSize": size,
        # Honest: legacy catalog is browse-only; no brand claimed as MakerNote-imported.
        "importedBrands": [],
        "emptyReason": None if total else "legacy_catalog_missing_or_empty",
        "note": "浏览旧版导入记录；未把未授权品牌 MakerNote 写成已导入成功",
    }
