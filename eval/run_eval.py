#!/usr/bin/env python3
"""Batch evaluation with JSONL cache + resume (work order C1/C2).

Never invents labels. Tech failures are recorded as tech_fail.
Same (detector, sha256, threshold) hits cache and is not re-billed/re-run.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from eval.adapters import AVAILABLE, get_adapter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "manifest.csv"
DEFAULT_OUT_DIR = ROOT / "results" / "raw"


def load_cache(path: Path) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if not path.is_file():
        return cache
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            key = obj.get("cache_key")
            if key:
                cache[key] = obj
    return cache


def cache_key(detector_id: str, sha256: str, threshold: float) -> str:
    return f"{detector_id}|{sha256}|{threshold:.4f}"


def iter_manifest(manifest: Path, rounds: set[str] | None):
    with manifest.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") != "ok":
                continue
            if rounds and row["round"] not in rounds:
                continue
            if not row.get("path"):
                continue
            yield row


def run(
    detector_id: str,
    manifest: Path,
    out_dir: Path,
    threshold: float,
    rounds: set[str] | None,
    limit: int | None,
) -> int:
    if not manifest.is_file():
        print(f"manifest missing: {manifest}", file=sys.stderr)
        return 2
    detect = get_adapter(detector_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{detector_id}.jsonl"
    cache = load_cache(out_path)

    n_total = n_run = n_hit = n_fail = 0
    t_start = time.time()
    with out_path.open("a", encoding="utf-8") as out:
        for row in iter_manifest(manifest, rounds):
            if limit is not None and n_total >= limit:
                break
            n_total += 1
            abs_path = ROOT / row["path"]
            sha = row["sha256"]
            key = cache_key(detector_id, sha, threshold)
            if key in cache and cache[key].get("verdict") != "tech_fail":
                n_hit += 1
                continue
            # Allow retry of previous tech_fail by re-running
            result = detect(str(abs_path), threshold=threshold)
            payload = result.to_dict()
            payload.update(
                {
                    "cache_key": key,
                    "stem": row["stem"],
                    "label": row["label"],
                    "round": row["round"],
                    "ts": time.time(),
                }
            )
            out.write(json.dumps(payload, ensure_ascii=False) + "\n")
            out.flush()
            cache[key] = payload
            n_run += 1
            if result.verdict == "tech_fail":
                n_fail += 1
            if n_run % 10 == 0:
                print(
                    f"[{detector_id}] run={n_run} hit={n_hit} fail={n_fail} "
                    f"elapsed={time.time()-t_start:.1f}s last={result.verdict}"
                )

    print(
        f"DONE {detector_id}: considered={n_total} newly_run={n_run} "
        f"cache_hit={n_hit} tech_fail_new={n_fail} → {out_path}"
    )
    return 0 if n_total > 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--detectors",
        default="lynote_univfd,nonescape_onnx,community_forensics",
        help=f"comma list; available={AVAILABLE}",
    )
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--rounds", default="g0,r1,r2,r3")
    ap.add_argument("--limit", type=int, default=None, help="debug cap on rows")
    args = ap.parse_args()
    rounds = {x.strip() for x in args.rounds.split(",") if x.strip()}
    code = 0
    for det in [x.strip() for x in args.detectors.split(",") if x.strip()]:
        rc = run(det, args.manifest, args.out_dir, args.threshold, rounds, args.limit)
        code = code or rc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
