"""Legacy device-preset catalog browse + activation (FR-007 / ND-014 / PRODUCT-GAP A7).

Source directory is fixed to 输入材料/旧版可复用模块/02_设备参数/.
MakerNote activation is authorized for this round (admin 2026-11-07).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.constants import DEVICE_TYPES
from app.capabilities.realphotos.models import RealphotosDevicePreset
from app.capabilities.realphotos.services.s6_ops import GPS_MODES, RealphotosOpsService
from app.core.exceptions import BusinessError

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
            params = template.get("legacy_parameters") or {}
            if not isinstance(params, dict):
                params = {}
            family = str(
                provenance.get("legacy_category")
                or template.get("family_hint")
                or payload.get("legacy_category")
                or "phone"
            ).strip()
            if family not in DEVICE_TYPES:
                family = "phone"
            rows.append(
                {
                    "sourceId": provenance.get("source_id"),
                    "templateRef": template.get("template_ref"),
                    "deviceDisplay": template.get("device_display"),
                    "legacyCategory": family,
                    "visibility": provenance.get("legacy_visibility") or "UNKNOWN",
                    "activationStatus": template.get("activation_status") or "NOT_ACTIVATED",
                    "reviewBucket": template.get("review_bucket") or "UNKNOWN",
                    "reviewFlags": list(template.get("review_flags") or []),
                    "makerNoteTemplate": str(params.get("maker_note_template") or ""),
                    "cameraMake": str(params.get("camera_make") or ""),
                    "cameraModel": str(params.get("camera_model") or ""),
                    "aiPositivePrompt": str(params.get("ai_positive_prompt") or ""),
                    "aiNegativePrompt": str(params.get("ai_negative_prompt") or ""),
                    "iso": str(params.get("iso") or ""),
                    "shutter": str(params.get("shutter_speed") or ""),
                    "aperture": str(params.get("aperture") or ""),
                    "focalLength": str(params.get("focal_length") or ""),
                    "gpsModeRaw": str(params.get("gps_mode") or "none"),
                    "raw": template,
                }
            )
    return tuple(rows)


def _code_for(template_ref: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(template_ref or "").strip()).strip("-").lower()
    return f"legacy-{slug}"[:64]


def _format_aperture(raw: object) -> str:
    if raw in (None, ""):
        return "f/1.8"
    text = str(raw).strip()
    if text.lower().startswith("f"):
        return text
    return f"f/{text}"


def _format_focal(raw: object) -> str:
    if raw in (None, ""):
        return "26mm"
    text = str(raw).strip()
    if text.lower().endswith("mm"):
        return text
    return f"{text}mm"


async def browse_legacy_imports(
    db: AsyncSession | None = None, *, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    size = max(1, min(int(page_size or 20), 100))
    current = max(1, int(page or 1))
    rows = list(_load_rows())
    activated: dict[str, RealphotosDevicePreset] = {}
    if db is not None:
        found = (
            await db.execute(
                select(RealphotosDevicePreset).where(
                    RealphotosDevicePreset.deleted_at.is_(None),
                    RealphotosDevicePreset.source == "legacy_import",
                )
            )
        ).scalars().all()
        for row in found:
            key = str(row.legacy_template_ref or row.code)
            activated[key] = row
            if row.legacy_template_ref:
                activated[str(row.legacy_template_ref)] = row

    items: list[dict[str, Any]] = []
    imported_brands: set[str] = set()
    for row in rows:
        ref = str(row.get("templateRef") or "")
        runtime = activated.get(ref)
        active = runtime is not None and bool(runtime.enabled)
        brand = str((runtime.brand if runtime else row.get("cameraMake")) or "")
        status = "ACTIVATED" if runtime is not None else str(row.get("activationStatus") or "NOT_ACTIVATED")
        items.append(
            {
                "sourceId": row.get("sourceId"),
                "templateRef": ref,
                "deviceDisplay": row.get("deviceDisplay"),
                "legacyCategory": row.get("legacyCategory"),
                "visibility": row.get("visibility"),
                "activationStatus": status,
                "reviewBucket": row.get("reviewBucket"),
                "reviewFlags": list(row.get("reviewFlags") or []),
                "makerNoteImported": bool(runtime is not None and str(runtime.maker_note or "").strip()),
                "runtimeActivated": active,
                "runtimeCode": runtime.code if runtime else None,
                "brand": brand,
            }
        )
        if runtime is not None and brand:
            imported_brands.add(brand)

    total = len(items)
    start = (current - 1) * size
    slice_rows = items[start : start + size]
    return {
        "items": slice_rows,
        "total": total,
        "page": current,
        "pageSize": size,
        "importedBrands": sorted(imported_brands),
        "emptyReason": None if total else "legacy_catalog_missing_or_empty",
        "note": "旧版导入记录；importedBrands 仅含真实激活成功品牌",
    }


async def activate_legacy_template(
    db: AsyncSession,
    *,
    actor_role_codes: set[str],
    template_ref: str,
    enabled: bool = True,
) -> dict[str, Any]:
    ref = str(template_ref or "").strip()
    if not ref:
        raise BusinessError(message="templateRef 必填", code="INPUT_INVALID")
    match = next((row for row in _load_rows() if str(row.get("templateRef")) == ref), None)
    if match is None:
        raise BusinessError(message="旧版模板不存在于授权目录", code="NOT_FOUND")
    brand = str(match.get("cameraMake") or "Legacy").strip() or "Legacy"
    model = str(match.get("cameraModel") or match.get("deviceDisplay") or ref).strip()
    maker = str(match.get("makerNoteTemplate") or "").strip()
    gps_raw = str(match.get("gpsModeRaw") or "none").strip()
    # Do not invent fixed coords from legacy; inherit only none when unsupported.
    gps_mode = gps_raw if gps_raw in GPS_MODES and gps_raw == "none" else "none"
    code = _code_for(ref)
    ops = RealphotosOpsService(db)
    payload = await ops.save_preset(
        actor_role_codes=actor_role_codes,
        code=code,
        device_type=str(match.get("legacyCategory") or "phone"),
        brand=brand,
        model_name=model,
        gps_mode=gps_mode,
        enabled=bool(enabled),
        maker_note=maker,
        iso=str(match.get("iso") or "100"),
        shutter=str(match.get("shutter") or "1/125"),
        aperture=_format_aperture(match.get("aperture")),
        focal_length=_format_focal(match.get("focalLength")),
        ai_positive_prompt=str(match.get("aiPositivePrompt") or ""),
        ai_negative_prompt=str(match.get("aiNegativePrompt") or ""),
        source="legacy_import",
        legacy_source_id=str(match.get("sourceId") or ""),
        legacy_template_ref=ref,
        legacy_visibility=str(match.get("visibility") or ""),
        legacy_review_bucket=str(match.get("reviewBucket") or ""),
    )
    payload["activationStatus"] = "ACTIVATED"
    payload["makerNoteRequested"] = maker
    return payload
