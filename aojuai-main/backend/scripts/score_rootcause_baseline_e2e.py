"""SCORE-ROOTCAUSE baseline: 10 merchant assets × 2 rounds, live Gemini.

Writes /tmp/score-lift-rootcause-e2e.log
Does not change PASS_SCORE. production_billing=false.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

LOG = Path("/tmp/score-lift-rootcause-e2e.log")
API = "http://127.0.0.1:38000"
# Locked sample set from rp_merchant_a1 library (mix upload + AI gen).
SAMPLES = [
    {"assetId": 159, "originKind": "local_upload", "note": "likely_real_jpeg"},
    {"assetId": 160, "originKind": "local_upload", "note": "likely_real_jpeg"},
    {"assetId": 119, "originKind": "local_upload", "note": "upload_png"},
    {"assetId": 27, "originKind": "local_upload", "note": "large_jpeg_upload"},
    {"assetId": 140, "originKind": "text_to_image", "note": "ai_t2i"},
    {"assetId": 139, "originKind": "text_to_image", "note": "ai_t2i"},
    {"assetId": 112, "originKind": "text_to_image", "note": "ai_t2i"},
    {"assetId": 109, "originKind": "image_to_image", "note": "ai_i2i"},
    {"assetId": 108, "originKind": "text_to_image", "note": "ai_t2i"},
    {"assetId": 83, "originKind": "text_to_image", "note": "ai_t2i"},
]
PRESET = "legacy-legacy-online-1001"  # Nikon D850 gpsMode=none complete EXIF
ROUNDS = 2


def note(msg: str) -> None:
    line = msg.rstrip()
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


async def login(client: httpx.AsyncClient, username: str, password: str) -> dict[str, str]:
    ch = await client.post("/api/v1/realphotos/auth/challenges")
    ch.raise_for_status()
    data = ch.json()["data"]
    lg = await client.post(
        "/api/v1/realphotos/auth/login",
        json={
            "username": username,
            "password": password,
            "challengeId": data["challengeId"],
            "challengeCode": data["devCode"],
        },
    )
    lg.raise_for_status()
    return {"Authorization": "Bearer " + lg.json()["data"]["accessToken"]}


async def poll(client: httpx.AsyncClient, headers: dict, task_id: int, timeout_s: int = 300) -> dict:
    terminal = {"DELIVERED", "FAILED", "REJECTED", "EXPIRED", "CANCELLED"}
    started = time.time()
    last: dict = {}
    while time.time() - started < timeout_s:
        r = await client.get(f"/api/v1/realphotos/processing-tasks/{task_id}", headers=headers)
        if r.status_code != 200:
            await asyncio.sleep(3)
            continue
        last = r.json()["data"]
        if str(last.get("status") or "") in terminal:
            return last
        await asyncio.sleep(3)
    return last


async def run_round(client: httpx.AsyncClient, headers: dict, round_no: int, stamp: str) -> list[dict]:
    rows: list[dict] = []
    for sample in SAMPLES:
        asset_id = int(sample["assetId"])
        body = {
            "assetId": asset_id,
            "presetCode": PRESET,
            "idempotencyKey": f"score-rc-r{round_no}-a{asset_id}-{stamp}",
            # omit detectionMode → default gemini; explicit for evidence
            "detectionMode": "gemini",
        }
        t0 = time.time()
        sub = await client.post("/api/v1/realphotos/processing-tasks", headers=headers, json=body)
        note(f"round={round_no} submit asset={asset_id} http={sub.status_code}")
        if sub.status_code != 200:
            row = {
                "round": round_no,
                "assetId": asset_id,
                "originKind": sample["originKind"],
                "note": sample["note"],
                "submitHttp": sub.status_code,
                "submitError": sub.text[:500],
                "classification_hint": "SUBMIT_FAILED",
            }
            rows.append(row)
            note("row " + json.dumps(row, ensure_ascii=False))
            continue
        task = sub.json()["data"]
        task_id = int(task["id"])
        note(
            f"round={round_no} task={task_id} asset={asset_id} submitted "
            f"detectionMode={task.get('detectionMode')} preReview={task.get('preReviewMode')}"
        )
        final = await poll(client, headers, task_id)
        det = final.get("detection") or {}
        elapsed = round(time.time() - t0, 1)
        row = {
            "round": round_no,
            "assetId": asset_id,
            "originKind": sample["originKind"],
            "note": sample["note"],
            "taskId": task_id,
            "status": final.get("status"),
            "failureClass": final.get("failureClass"),
            "failureMessage": (final.get("failureMessage") or "")[:240],
            "creditDisposition": final.get("creditDisposition"),
            "detectionMode": final.get("detectionMode"),
            "preReviewMode": final.get("preReviewMode"),
            "outputObjectKey": final.get("outputObjectKey"),
            "pipelineVersion": final.get("pipelineVersion"),
            "detector": det.get("detector"),
            "totalScore": det.get("total_score"),
            "passed": det.get("passed"),
            "accepted": det.get("accepted"),
            "passScoreThreshold": det.get("passScoreThreshold"),
            "dims": {
                "noise": det.get("noise"),
                "depthOfField": det.get("depthOfField"),
                "lighting": det.get("lighting"),
                "colorRealism": det.get("colorRealism"),
                "overallRealism": det.get("overallRealism"),
            },
            "reason": (det.get("reason") or "")[:300],
            "elapsedSec": elapsed,
        }
        rows.append(row)
        note("row " + json.dumps(row, ensure_ascii=False))
    return rows


async def main() -> int:
    LOG.write_text("", encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD
    from app.core.config import settings

    stamp = str(int(time.time()))
    note("SCORE_ROOTCAUSE_BASELINE start")
    note(f"started_at={datetime.now(UTC).isoformat()}")
    note(f"api_base={API}")
    note(f"db_dialect={settings.DB_DIALECT}")
    note(f"preset={PRESET} gpsMode=none")
    note(f"samples={json.dumps(SAMPLES, ensure_ascii=False)}")
    note("detectionMode=gemini live")
    note("PASS_SCORE=75 unchanged")
    note("production_billing=false")
    note("sample_is_not_public_pass=true")

    async with httpx.AsyncClient(base_url=API, timeout=180.0) as client:
        headers = await login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        note("login=rp_merchant_a1 ok")
        all_rows: list[dict] = []
        for round_no in range(1, ROUNDS + 1):
            note(f"=== ROUND {round_no} ===")
            rows = await run_round(client, headers, round_no, stamp)
            all_rows.extend(rows)

    # Summary
    delivered_pass = [
        r
        for r in all_rows
        if r.get("status") == "DELIVERED" and r.get("passed") is True and int(r.get("totalScore") or 0) >= 75
    ]
    scored = [r for r in all_rows if r.get("totalScore") is not None]
    tech = [r for r in all_rows if "technical" in str(r.get("failureClass") or "").lower() or "GEMINI" in str(r.get("submitError") or "")]
    prerej = [r for r in all_rows if "pre_review" in str(r.get("failureClass") or "").lower() or "PRE_REVIEW" in str(r.get("failureClass") or "").upper()]
    detect_fail = [r for r in all_rows if r.get("failureClass") == "detection_not_passed"]

    note(f"summary.total_tasks={len(all_rows)}")
    note(f"summary.scored={len(scored)}")
    note(f"summary.delivered_pass_ge75={len(delivered_pass)}")
    note(f"summary.detection_not_passed={len(detect_fail)}")
    note(f"summary.pre_review_related={len(prerej)}")
    note(f"summary.tech_related={len(tech)}")
    if scored:
        scores = [int(r["totalScore"]) for r in scored]
        note(f"summary.score_min={min(scores)} max={max(scores)} avg={sum(scores)/len(scores):.1f}")

    # Per-round pass rate among completed detection outcomes
    for round_no in range(1, ROUNDS + 1):
        rr = [r for r in all_rows if r.get("round") == round_no]
        ok = [
            r
            for r in rr
            if r.get("status") == "DELIVERED" and r.get("passed") is True and int(r.get("totalScore") or 0) >= 75
        ]
        note(f"summary.round{round_no}_pass_rate={len(ok)}/{len(rr)}={len(ok)/max(len(rr),1):.2%}")

    # Provisional classification hints (final defect gate after human/code review)
    for r in all_rows:
        if r.get("submitHttp") and int(r.get("submitHttp") or 0) >= 400:
            hint = "NEEDS_REVIEW_SUBMIT"
        elif r.get("failureClass") == "detection_not_passed" and r.get("detector"):
            hint = "LIKELY_NOT_DEFECT_SAMPLE_OR_MODEL_SCORE" if int(r.get("totalScore") or 0) < 75 else "NEEDS_REVIEW"
        elif r.get("status") == "DELIVERED" and r.get("passed") is True:
            hint = "PASS"
        elif "pre_review" in str(r.get("failureClass") or "").lower():
            hint = "SECONDARY_PRE_REVIEW"
        elif r.get("failureClass") in {"GEMINI_TECHNICAL", "technical_failure"} or "technical" in str(
            r.get("failureClass") or ""
        ):
            hint = "SECONDARY_GEMINI_TECH"
        else:
            hint = "NEEDS_REVIEW"
        r["provisionalHint"] = hint
    note("provisional_table " + json.dumps(all_rows, ensure_ascii=False))
    note(f"ended_at={datetime.now(UTC).isoformat()}")
    note("SCORE_ROOTCAUSE_BASELINE_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
