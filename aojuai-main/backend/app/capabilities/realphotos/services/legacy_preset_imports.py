"""Legacy device-preset catalog browse + activation (FR-007 / ND-014).

PRODUCT-GAP A7: single activate + MakerNote (admin 2026-11-07 allow).
PRESET-BULK-IMPORT: clear placeholders, full 405 activate, 55-key snapshot integrity.
Source directory is fixed to 输入材料/旧版可复用模块/02_设备参数/.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.constants import DEVICE_TYPES
from app.capabilities.realphotos.models import RealphotosDevicePreset
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s6_ops import GPS_MODES, RealphotosOpsService
from app.core.exceptions import BusinessError

_REPO_ROOT = Path(__file__).resolve().parents[6]
_LEGACY_DIR = _REPO_ROOT / "输入材料" / "旧版可复用模块" / "02_设备参数" / "按旧分类"
_CATEGORIES = ("phone.json", "dslr.json", "mirrorless.json", "action.json")

# Appendix A — 55 keys; must all land in snapshot.legacyParameters (except documented excluded).
LEGACY_PARAMETER_KEYS: tuple[str, ...] = (
    "ai_img2img_strength",
    "ai_negative_prompt",
    "ai_positive_prompt",
    "ai_strength",
    "ambient_light",
    "aperture",
    "burst_sequence",
    "camera_make",
    "camera_model",
    "category",
    "color_depth",
    "color_mode",
    "color_space",
    "color_temperature",
    "compression_ratio",
    "description",
    "ev_value",
    "exposure_compensation",
    "exposure_mode",
    "file_number",
    "flash_mode",
    "focal_length",
    "focal_length_equiv",
    "focal_plane_res_unit",
    "focal_plane_x_res",
    "focal_plane_y_res",
    "focus_distance",
    "gps_mode",
    "image_description",
    "image_format",
    "image_height",
    "image_orientation",
    "image_width",
    "iso",
    "iso_range",
    "keywords",
    "lens_make",
    "lens_max_aperture",
    "lens_model",
    "maker_note_template",
    "metering_mode",
    "name",
    "noise_reduction",
    "pixel_density",
    "raw_version",
    "scene_mode",
    "scene_type",
    "sensor_size",
    "sensor_type",
    "sharpening",
    "shutter_speed",
    "shutter_type",
    "software",
    "stabilization",
    "white_balance",
)

PLACEHOLDER_BRANDS = {"Honeybadger", "honeybadger"}
PLACEHOLDER_CODE_PREFIXES = ("s1-", "pa-gps-", "bf-", "pa-", "blocking-")


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
                    "legacyParameters": dict(params),
                    "runtimeOverrides": dict(template.get("v2_runtime_overrides") or {}),
                    "raw": template,
                }
            )
    return tuple(rows)


def expected_template_count() -> int:
    return len(_load_rows())


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


def _copy_legacy_parameters(source: dict[str, Any]) -> dict[str, Any]:
    """Preserve every source key; also materialize known 55-key slots when absent."""
    out: dict[str, Any] = {key: source.get(key, "") for key in LEGACY_PARAMETER_KEYS}
    for key, value in source.items():
        if key not in out:
            out[key] = value
    return out


def _resolve_gps(
    *, gps_raw: str, legacy_parameters: dict[str, Any], overrides: dict[str, Any]
) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    """Keep source gps_mode; never invent coords when overrides forbid inheritance."""
    mode = str(gps_raw or "none").strip() or "none"
    if mode not in GPS_MODES:
        # Keep source string in meta; column falls back to none for schema safety.
        column_mode = "none"
        source_mode = mode
    else:
        column_mode = mode
        source_mode = mode
    meta = {
        "gpsSourceMode": source_mode,
        "gpsColumnMode": column_mode,
        "gpsOverridePolicy": overrides.get("gps"),
        "gpsCoordsInherited": False,
        "gpsWriteNote": None,
    }
    gps_config: dict[str, Any] | None = None
    # Only attach coords if present in legacy payload (rare); do not invent.
    lat = legacy_parameters.get("gps_latitude") or legacy_parameters.get("latitude")
    lng = legacy_parameters.get("gps_longitude") or legacy_parameters.get("longitude")
    scene = legacy_parameters.get("gps_scene_rule") or legacy_parameters.get("scene_rule")
    forbid = "DO_NOT_INHERIT" in str(overrides.get("gps") or "").upper()
    if column_mode == "fixed" and lat not in (None, "") and lng not in (None, "") and not forbid:
        gps_config = {"latitude": lat, "longitude": lng}
        alt = legacy_parameters.get("gps_altitude") or legacy_parameters.get("altitude")
        if alt not in (None, ""):
            gps_config["altitude"] = alt
        meta["gpsCoordsInherited"] = True
    elif column_mode == "random_by_scene" and scene not in (None, "") and not forbid:
        gps_config = {"sceneRule": scene}
        meta["gpsCoordsInherited"] = True
    elif column_mode in {"fixed", "random_by_scene"}:
        meta["gpsWriteNote"] = (
            "源模式已保留；无可用坐标/场景或旧版声明不继承固定坐标，EXIF 写入须诚实失败而非伪装成功"
        )
    return column_mode, gps_config, meta


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
    activated_count = 0
    for row in rows:
        ref = str(row.get("templateRef") or "")
        runtime = activated.get(ref)
        active = runtime is not None and bool(runtime.enabled)
        brand = str((runtime.brand if runtime else row.get("cameraMake")) or "")
        status = "ACTIVATED" if runtime is not None else str(row.get("activationStatus") or "NOT_ACTIVATED")
        if runtime is not None:
            activated_count += 1
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
        "activatedCount": activated_count,
        "importedBrands": sorted(imported_brands),
        "emptyReason": None if total else "legacy_catalog_missing_or_empty",
        "note": "旧版导入记录；importedBrands 仅含真实激活成功品牌；total 应为 405",
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
    legacy_parameters = _copy_legacy_parameters(dict(match.get("legacyParameters") or {}))
    overrides = dict(match.get("runtimeOverrides") or {})
    gps_mode, gps_config, gps_meta = _resolve_gps(
        gps_raw=str(match.get("gpsModeRaw") or legacy_parameters.get("gps_mode") or "none"),
        legacy_parameters=legacy_parameters,
        overrides=overrides,
    )
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
        iso=str(match.get("iso") or legacy_parameters.get("iso") or "100"),
        shutter=str(match.get("shutter") or legacy_parameters.get("shutter_speed") or "1/125"),
        aperture=_format_aperture(match.get("aperture") or legacy_parameters.get("aperture")),
        focal_length=_format_focal(match.get("focalLength") or legacy_parameters.get("focal_length")),
        ai_positive_prompt=str(match.get("aiPositivePrompt") or legacy_parameters.get("ai_positive_prompt") or ""),
        ai_negative_prompt=str(match.get("aiNegativePrompt") or legacy_parameters.get("ai_negative_prompt") or ""),
        source="legacy_import",
        legacy_source_id=str(match.get("sourceId") or ""),
        legacy_template_ref=ref,
        legacy_visibility=str(match.get("visibility") or ""),
        legacy_review_bucket=str(match.get("reviewBucket") or ""),
        gps_config=gps_config,
        snapshot_extra={
            "legacyParameters": legacy_parameters,
            "legacyRuntimeOverrides": overrides,
            "legacyGpsMeta": gps_meta,
            "legacyParameterKeyCount": len(legacy_parameters),
        },
    )
    payload["activationStatus"] = "ACTIVATED"
    payload["makerNoteRequested"] = maker
    payload["legacyParameterKeyCount"] = len(legacy_parameters)
    payload["legacyGpsMeta"] = gps_meta
    return payload


def _is_placeholder_row(row: RealphotosDevicePreset) -> bool:
    code = str(row.code or "")
    brand = str(row.brand or "")
    source = str(row.source or "")
    if source == "legacy_import":
        return False
    if any(code.startswith(prefix) for prefix in PLACEHOLDER_CODE_PREFIXES):
        return True
    if brand in PLACEHOLDER_BRANDS and source in {"catalog", "admin", ""}:
        return True
    return code in {item["code"] for item in S1_ENABLED_PRESETS}


async def clear_placeholder_presets(
    db: AsyncSession, *, actor_role_codes: set[str]
) -> dict[str, Any]:
    from app.capabilities.realphotos.permissions import ROLE_ADMIN
    from app.core.exceptions import ForbiddenError

    if ROLE_ADMIN not in actor_role_codes and "admin" not in actor_role_codes:
        raise ForbiddenError(message="只有平台管理员可以清除占位预设")

    rows = (
        await db.execute(select(RealphotosDevicePreset).where(RealphotosDevicePreset.deleted_at.is_(None)))
    ).scalars().all()
    disabled: list[str] = []
    soft_deleted: list[str] = []
    now = datetime.now(timezone.utc)
    catalog_codes = {item["code"] for item in S1_ENABLED_PRESETS}
    for row in rows:
        if not _is_placeholder_row(row):
            continue
        # Prefer disable for audit; soft-delete pure catalog placeholders.
        row.enabled = False
        if str(row.source or "") == "catalog" or row.code in catalog_codes:
            row.deleted_at = now
            soft_deleted.append(row.code)
        else:
            disabled.append(row.code)
    await db.flush()
    return {
        "placeholder_presets_removed": True,
        "disabledCodes": disabled,
        "softDeletedCodes": soft_deleted,
        "catalogInjection": False,
        "s1CatalogCodes": sorted(catalog_codes),
    }


async def activate_all_legacy_templates(
    db: AsyncSession,
    *,
    actor_role_codes: set[str],
    enabled: bool = True,
) -> dict[str, Any]:
    rows = list(_load_rows())
    total = len(rows)
    failures: list[dict[str, Any]] = []
    activated = 0
    brands: set[str] = set()
    for index, row in enumerate(rows, start=1):
        ref = str(row.get("templateRef") or "")
        try:
            payload = await activate_legacy_template(
                db,
                actor_role_codes=actor_role_codes,
                template_ref=ref,
                enabled=bool(enabled),
            )
            activated += 1
            brand = str(payload.get("brand") or "")
            if brand:
                brands.add(brand)
        except Exception as exc:  # noqa: BLE001 — batch must continue; failures audited
            failures.append(
                {
                    "templateRef": ref,
                    "index": index,
                    "error": str(exc)[:300],
                }
            )
    return {
        "total": total,
        "legacy_activated_count": activated,
        "failedCount": len(failures),
        "failures": failures,
        "importedBrands": sorted(brands),
        "progress": f"{activated}/{total}",
        "activationStatus": "ACTIVATED" if activated == total and not failures else "PARTIAL",
    }
