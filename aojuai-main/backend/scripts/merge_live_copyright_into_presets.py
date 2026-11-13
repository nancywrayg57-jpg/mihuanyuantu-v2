#!/usr/bin/env python3
"""Merge live-site author/copyright/software/GPS coords into legacy_import presets.

Source JSON: repo .tmp/legacy-live-copyright.json (id -> fields).
Matches cap_realphotos_device_presets.legacy_source_id.

Also backfills empty legacy 55-key cells from local desensitized catalog when present,
strips prototype-only keys, never writes ip_geo.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json

from app.core.config import settings

REPO = Path(__file__).resolve().parents[3]
LIVE_PATH = REPO / ".tmp" / "legacy-live-copyright.json"
LEGACY_DIR = REPO / "输入材料" / "旧版可复用模块" / "02_设备参数" / "按旧分类"
PROTO_ONLY = {"lighting", "background", "post_processing"}
IP_GEO = {"ip_geo", "ipgeo"}


def _load_live() -> dict[str, dict[str, Any]]:
    rows = json.loads(LIVE_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("id") or "").strip()
        if sid:
            out[sid] = row
    return out


def _load_local_params() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not LEGACY_DIR.is_dir():
        return out
    for path in LEGACY_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for template in payload.get("templates") or []:
            if not isinstance(template, dict):
                continue
            prov = template.get("provenance") or {}
            sid = str(prov.get("source_id") or "").strip()
            params = template.get("legacy_parameters") or {}
            if sid and isinstance(params, dict):
                out[sid] = dict(params)
    return out


def _clean_lp(lp: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in dict(lp).items():
        lk = str(key).lower()
        if lk in IP_GEO or lk in PROTO_ONLY:
            continue
        cleaned[str(key)] = value
    return cleaned


def _merge_one(
    *,
    lp: dict[str, Any],
    live: dict[str, Any] | None,
    local: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None, list[str]]:
    notes: list[str] = []
    merged = _clean_lp(lp)
    # Fill empty from local catalog first (55-key honesty).
    if local:
        for key, value in local.items():
            lk = str(key).lower()
            if lk in IP_GEO or lk in PROTO_ONLY:
                continue
            cur = merged.get(key)
            if (cur is None or cur == "") and value not in (None, ""):
                merged[key] = value
                notes.append(f"local:{key}")
    gps_mode = None
    gps_config = None
    if live:
        for key in ("author", "copyright", "software", "scene_type"):
            val = live.get(key)
            if val not in (None, ""):
                if merged.get(key) != val:
                    notes.append(f"live:{key}")
                merged[key] = val
        mode = str(live.get("gps_mode") or "").strip()
        if mode in {"none", "fixed", "random_by_scene"}:
            gps_mode = mode
            merged["gps_mode"] = mode
        if mode == "fixed":
            lat, lng, alt = live.get("gps_latitude"), live.get("gps_longitude"), live.get("gps_altitude")
            if lat not in (None, "") and lng not in (None, ""):
                gps_config = {
                    "latitude": str(lat),
                    "longitude": str(lng),
                    "altitude": alt if alt is not None else None,
                }
                notes.append("live:gpsConfig")
        elif mode == "random_by_scene":
            scene = live.get("scene_type")
            if scene not in (None, ""):
                gps_config = {"sceneRule": str(scene)}
                merged["scene_type"] = str(scene)
                notes.append("live:sceneRule")
        elif mode == "none":
            gps_config = None
    return merged, gps_config, gps_mode, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not LIVE_PATH.is_file():
        print(f"missing {LIVE_PATH}", file=sys.stderr)
        return 2

    sync_url = str(settings.DATABASE_URL_SYNC)
    # psycopg2 wants postgresql:// without SQLAlchemy driver suffixes.
    for prefix, repl in (
        ("postgresql+psycopg2://", "postgresql://"),
        ("postgresql+psycopg://", "postgresql://"),
        ("postgresql+asyncpg://", "postgresql://"),
    ):
        if sync_url.startswith(prefix):
            sync_url = sync_url.replace(prefix, repl, 1)
            break

    live_map = _load_live()
    local_map = _load_local_params()
    print(f"live={len(live_map)} local={len(local_map)} dry_run={args.dry_run}")

    updated = 0
    skipped = 0
    missing_live = 0
    conn = psycopg2.connect(sync_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.id, p.code, p.legacy_source_id, p.gps_mode, p.version_no, p.tenant_id,
                       v.snapshot
                from cap_realphotos_device_presets p
                join lateral (
                  select snapshot
                  from cap_realphotos_preset_versions v
                  where v.preset_code = p.code
                  order by v.version_no desc
                  limit 1
                ) v on true
                where p.source = 'legacy_import'
                  and p.deleted_at is null
                order by p.id
                """
            )
            rows = cur.fetchall()
            print(f"legacy_import_rows={len(rows)}")
            for preset_id, code, lsid, gps_mode, version_no, tenant_id, snapshot in rows:
                snap = snapshot if isinstance(snapshot, dict) else json.loads(snapshot)
                lp = dict(snap.get("legacyParameters") or {})
                live = live_map.get(str(lsid or "").strip())
                local = local_map.get(str(lsid or "").strip())
                if live is None:
                    missing_live += 1
                merged, gps_config, new_mode, notes = _merge_one(lp=lp, live=live, local=local)
                prev_cfg = snap.get("gpsConfig")
                mode_same = new_mode is None or new_mode == gps_mode
                cfg_same = gps_config is None or gps_config == prev_cfg
                if not notes and merged == _clean_lp(lp) and mode_same and cfg_same:
                    skipped += 1
                    continue
                new_version = int(version_no) + 1
                new_snap = dict(snap)
                new_snap["legacyParameters"] = merged
                new_snap["legacyParameterKeyCount"] = len(merged)
                if new_mode:
                    new_snap["gpsMode"] = new_mode
                if gps_config is not None:
                    new_snap["gpsConfig"] = gps_config
                elif new_mode == "none":
                    new_snap["gpsConfig"] = None
                new_snap["copyrightPolicy"] = "admin_ledger_author_copyright_allowed_ip_geo_excluded"
                new_snap["liveCopyrightMergedAt"] = datetime.now(UTC).isoformat()
                print(f"update {code} lsid={lsid} notes={notes[:8]}{'...' if len(notes)>8 else ''}")
                if args.dry_run:
                    updated += 1
                    continue
                cur.execute(
                    """
                    update cap_realphotos_device_presets
                    set version_no = %s,
                        gps_mode = coalesce(%s, gps_mode),
                        updated_at = now()
                    where id = %s
                    """,
                    (new_version, new_mode, preset_id),
                )
                cur.execute(
                    """
                    insert into cap_realphotos_preset_versions
                      (tenant_id, preset_code, version_no, snapshot, created_at)
                    values (%s, %s, %s, %s, now())
                    """,
                    (int(tenant_id or 0), code, new_version, Json(new_snap)),
                )
                updated += 1
        if not args.dry_run:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()
    print(f"done updated={updated} skipped={skipped} missing_live={missing_live}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
