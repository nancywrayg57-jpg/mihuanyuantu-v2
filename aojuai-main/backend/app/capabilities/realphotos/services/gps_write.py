"""Resolve GPS coordinates from device-preset snapshots (FR-008)."""

from __future__ import annotations

import random
from typing import Any

# Compact scene bounding boxes adapted from legacy GPS_REGIONS intent.
# Values are (lat_min, lat_max, lon_min, lon_max, alt_min, alt_max).
_SCENE_BOXES: dict[str, tuple[float, float, float, float, float, float]] = {
    "landscape": (35.0, 45.0, -120.0, -110.0, 200.0, 1800.0),
    "urban": (31.1, 31.3, 121.4, 121.6, 2.0, 40.0),
    "portrait": (30.2, 30.4, 120.1, 120.3, 5.0, 60.0),
    "food": (39.8, 40.0, 116.3, 116.5, 30.0, 80.0),
    "sports": (34.0, 34.2, -118.3, -118.1, 20.0, 100.0),
    "macro": (22.2, 22.4, 114.1, 114.3, 5.0, 50.0),
    "beach": (21.2, 21.4, -157.9, -157.7, 0.0, 15.0),
    "mountain": (27.8, 28.2, 86.8, 87.0, 3000.0, 4500.0),
    "street": (31.2, 31.3, 121.4, 121.5, 2.0, 30.0),
}

_SKIP_SCENES = {"indoor", "studio"}


def gps_writability(*, gps_mode: str, gps_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ops-facing GPS writability without mutating mode (ALIGN-GAP G6).

    Never rewrites gpsMode=fixed → none. Returns gpsWritable + Chinese reason.
    gpsWillSkip=true when runtime will skip GPS (incomplete fixed/random, or mode none).
    """
    mode = str(gps_mode or "none").strip() or "none"
    plan = resolve_gps(preset={"gpsMode": mode, "gpsConfig": dict(gps_config or {})}, seed=0)
    action = str(plan.get("action") or "")
    plan_reason = str(plan.get("reason") or "")
    if action == "write":
        return {
            "gpsWritable": True,
            "gpsWillSkip": False,
            "gpsWritableReason": "",
            "gpsMode": mode,
        }
    if action == "skip":
        # Skip is processable (legacy-aligned). Surface soft hint for incomplete coords/scene
        # so merchants see pre-submit warning; keep gpsWritableReason empty for none mode.
        incomplete = mode in {"fixed", "random_by_scene"} and bool(plan_reason)
        return {
            "gpsWritable": True,
            "gpsWillSkip": True,
            "gpsWritableReason": plan_reason if incomplete else "",
            "gpsMode": mode,
        }
    return {
        "gpsWritable": False,
        "gpsWillSkip": True,
        "gpsWritableReason": plan_reason or "GPS 不可写入",
        "gpsMode": mode,
    }


def assert_preset_gps_ready(preset: dict[str, Any]) -> None:
    """Reject submit only when EXIF GPS would hard-fail (unknown mode / bad range).

    Skip paths match legacy exifWriter: none、fixed 无坐标、random 缺场景时不写 GPS，
    任务仍可成功；不把 gpsMode 静默改成 none。
    """
    from app.core.exceptions import BusinessError

    plan = resolve_gps(preset=preset, seed=0)
    if plan.get("action") == "fail":
        raise BusinessError(
            message=str(plan.get("reason") or "预设 GPS 配置不可用，无法提交处理"),
            code="PRESET_GPS_UNUSABLE",
        )


def _scene_rule_from_preset(preset: dict[str, Any], config: dict[str, Any]) -> str:
    """Legacy used scene_type for random_by_scene; accept that plus gpsConfig keys."""
    legacy = preset.get("legacyParameters") if isinstance(preset.get("legacyParameters"), dict) else {}
    # Prefer English scene_type keys (urban/landscape/…); ignore Chinese scene_mode labels.
    raw = (
        config.get("sceneRule")
        or config.get("scene")
        or config.get("sceneType")
        or preset.get("scene_type")
        or preset.get("sceneType")
        or (legacy or {}).get("scene_type")
        or ""
    )
    return str(raw).strip().lower()


def resolve_gps(*, preset: dict[str, Any], seed: int) -> dict[str, Any]:
    """Return write plan for EXIF GPS.

    Legacy-aligned behavior (exifWriter.ts):
      none → skip
      fixed + coords → write; fixed without coords → skip (do not invent, do not fail)
      random_by_scene → write from scene box (sceneRule / scene_type); missing → skip

    Keys:
      action: write | skip | fail
      reason: human-readable Chinese reason when skip/fail context
      latitude/longitude/altitude: floats when action=write
      mode: none | fixed | random_by_scene
    """
    mode = str(preset.get("gpsMode") or "none").strip()
    config = dict(preset.get("gpsConfig") or {})
    if mode == "none":
        return {"action": "skip", "mode": mode, "reason": "gpsMode=none 不写入 GPS"}
    if mode == "fixed":
        try:
            lat = float(config.get("latitude"))
            lon = float(config.get("longitude"))
            alt = float(config.get("altitude") if config.get("altitude") not in (None, "") else 0.0)
        except (TypeError, ValueError):
            # Old runtime: fixed 无坐标则不生成 GPS，任务仍成功；模式保持 fixed。
            # Wording must not equal the former hard-fail string (inbox/UI confusion).
            return {
                "action": "skip",
                "mode": mode,
                "reason": "fixed 无坐标：已按旧版跳过 GPS 写入（不伪造、不失败）",
            }
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return {"action": "fail", "mode": mode, "reason": "fixed 坐标超出合法范围"}
        return {
            "action": "write",
            "mode": mode,
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "reason": "",
        }
    if mode == "random_by_scene":
        rule = _scene_rule_from_preset(preset, config)
        if not rule:
            return {
                "action": "skip",
                "mode": mode,
                "reason": "random_by_scene 缺少 sceneRule/scene_type，跳过 GPS 写入（不伪造坐标）",
            }
        rng = random.Random(int(seed) ^ (hash(rule) & 0xFFFFFFFF))
        if rule in _SKIP_SCENES:
            if rng.random() < 0.5:
                return {
                    "action": "skip",
                    "mode": mode,
                    "reason": f"场景 {rule} 按规则跳过 GPS 写入",
                }
            box = _SCENE_BOXES.get("urban")
        else:
            box = _SCENE_BOXES.get(rule)
        if box is None:
            return {
                "action": "fail",
                "mode": mode,
                "reason": f"未知场景规则 {rule}",
            }
        lat = rng.uniform(box[0], box[1])
        lon = rng.uniform(box[2], box[3])
        alt = rng.uniform(box[4], box[5])
        return {
            "action": "write",
            "mode": mode,
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "sceneRule": rule,
            "reason": "",
        }
    return {"action": "fail", "mode": mode, "reason": f"未知 gpsMode={mode}"}
