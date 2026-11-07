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


def resolve_gps(*, preset: dict[str, Any], seed: int) -> dict[str, Any]:
    """Return write plan for EXIF GPS.

    Keys:
      action: write | skip
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
            return {
                "action": "fail",
                "mode": mode,
                "reason": "fixed 模式缺少可用的纬度/经度",
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
        rule = str(config.get("sceneRule") or config.get("scene") or "").strip().lower()
        if not rule:
            return {"action": "fail", "mode": mode, "reason": "random_by_scene 缺少 sceneRule"}
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
