#!/usr/bin/env python3
"""Build manifest.csv for 198 originals + 3×198 processed images.

Expected layout (work order appendix A):
  data/测试用/测试图/
  data/测试用/测试图_处理后/
  data/测试用/测试图_二次处理后/
  data/测试用/测试图_三次处理后/

Excluded: 5 png without processed counterparts; 校准图.
Naming conflicts are written to anomalies, never silently dropped.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

from eval.labels import ROUND_SUFFIXES, is_excluded_original, label_for_stem, stem_of

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "测试用"
DEFAULT_OUT = ROOT / "data" / "manifest.csv"
DEFAULT_ANOM = ROOT / "docs" / "MH-YT-20261031-01" / "anomalies.md"

ROUND_DIRS = {
    "g0": "测试图",
    "r1": "测试图_处理后",
    "r2": "测试图_二次处理后",
    "r3": "测试图_三次处理后",
}


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def list_images(dir_path: Path) -> list[Path]:
    if not dir_path.is_dir():
        return []
    files = []
    for p in sorted(dir_path.iterdir()):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            files.append(p)
    return files


def build(data_root: Path, out_csv: Path, anom_md: Path) -> int:
    anomalies: list[str] = []
    rows: list[dict] = []

    g0 = data_root / ROUND_DIRS["g0"]
    if not data_root.is_dir() or not g0.is_dir() or not list_images(g0):
        anomalies.append(
            f"CRITICAL: test assets missing under `{data_root}` "
            f"(expected `{ROUND_DIRS['g0']}/` with images). Blocker B-02."
        )
        _write_anomalies(anom_md, anomalies, {})
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "stem",
                    "label",
                    "round",
                    "path",
                    "sha256",
                    "status",
                    "note",
                ],
            )
            w.writeheader()
        print(
            f"BLOCKED: assets missing at {data_root}. Empty manifest header → {out_csv}",
            file=sys.stderr,
        )
        return 2

    # --- originals ---
    originals = list_images(g0)
    stem_to_g0: dict[str, list[Path]] = defaultdict(list)
    for p in originals:
        if is_excluded_original(p):
            rows.append(
                {
                    "stem": p.stem,
                    "label": label_for_stem(p.stem),
                    "round": "g0",
                    "path": str(p.relative_to(ROOT)),
                    "sha256": sha256_file(p),
                    "status": "excluded",
                    "note": "R-1: png without processed counterpart",
                }
            )
            continue
        stem_to_g0[stem_of(p)].append(p)

    for stem, paths in sorted(stem_to_g0.items()):
        if len(paths) > 1:
            anomalies.append(f"G0 duplicate stem `{stem}`: {[x.name for x in paths]}")
            for p in paths:
                rows.append(
                    {
                        "stem": stem,
                        "label": label_for_stem(stem),
                        "round": "g0",
                        "path": str(p.relative_to(ROOT)),
                        "sha256": sha256_file(p),
                        "status": "conflict",
                        "note": "duplicate stem; do not score until resolved",
                    }
                )
            continue
        p = paths[0]
        lab = label_for_stem(stem)
        note = ""
        if lab == "UNKNOWN":
            anomalies.append(f"G0 unknown label for stem `{stem}` ({p.name})")
            status = "anomaly"
            note = "unknown label from filename"
        else:
            status = "ok"
        if "截屏" in stem:
            note = (note + "; " if note else "") + "screenshot subclass (Q4)"
        rows.append(
            {
                "stem": stem,
                "label": lab,
                "round": "g0",
                "path": str(p.relative_to(ROOT)),
                "sha256": sha256_file(p),
                "status": status,
                "note": note,
            }
        )

    ok_g0_stems = {r["stem"] for r in rows if r["round"] == "g0" and r["status"] == "ok"}

    # --- processed rounds ---
    for rnd, dirname in [("r1", ROUND_DIRS["r1"]), ("r2", ROUND_DIRS["r2"]), ("r3", ROUND_DIRS["r3"])]:
        d = data_root / dirname
        files = list_images(d)
        by_stem: dict[str, list[Path]] = defaultdict(list)
        for p in files:
            by_stem[stem_of(p)].append(p)
        for stem, paths in sorted(by_stem.items()):
            if len(paths) > 1:
                anomalies.append(
                    f"{rnd} naming conflict stem `{stem}`: {[x.name for x in paths]} "
                    "(e.g. `_legacy_... (2).jpg`); hold out of scoring"
                )
                for p in paths:
                    rows.append(
                        {
                            "stem": stem,
                            "label": label_for_stem(stem),
                            "round": rnd,
                            "path": str(p.relative_to(ROOT)),
                            "sha256": sha256_file(p),
                            "status": "conflict",
                            "note": "naming conflict",
                        }
                    )
                continue
            p = paths[0]
            if stem not in ok_g0_stems:
                anomalies.append(f"{rnd} orphan processed (no ok g0): `{p.name}`")
                status = "orphan"
                note = "no matching ok original"
            else:
                status = "ok"
                note = ""
            rows.append(
                {
                    "stem": stem,
                    "label": label_for_stem(stem),
                    "round": rnd,
                    "path": str(p.relative_to(ROOT)),
                    "sha256": sha256_file(p),
                    "status": status,
                    "note": note,
                }
            )
        missing = ok_g0_stems - set(by_stem.keys())
        for stem in sorted(missing):
            anomalies.append(f"{rnd} missing processed for stem `{stem}`")
            rows.append(
                {
                    "stem": stem,
                    "label": label_for_stem(stem),
                    "round": rnd,
                    "path": "",
                    "sha256": "",
                    "status": "missing",
                    "note": "missing processed file",
                }
            )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["stem", "label", "round", "path", "sha256", "status", "note"],
        )
        w.writeheader()
        w.writerows(rows)

    counts = defaultdict(int)
    for r in rows:
        counts[f"{r['round']}:{r['status']}"] += 1
    _write_anomalies(anom_md, anomalies, dict(counts))

    ok198 = counts.get("g0:ok", 0)
    print(f"Wrote {len(rows)} rows → {out_csv}")
    print(f"Counts: {dict(counts)}")
    if ok198 != 198:
        print(f"WARNING: g0:ok={ok198}, expected 198", file=sys.stderr)
        return 1
    for rnd in ("r1", "r2", "r3"):
        if counts.get(f"{rnd}:ok", 0) != 198:
            print(f"WARNING: {rnd}:ok={counts.get(f'{rnd}:ok', 0)}, expected 198", file=sys.stderr)
            return 1
    return 0


def _write_anomalies(path: Path, anomalies: list[str], counts: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 异常样本登记（不得静默丢弃）",
        "",
        f"生成命令: `python -m eval.build_manifest`",
        "",
        "## 计数快照",
        "",
        "```",
        str(counts) if counts else "(empty)",
        "```",
        "",
        "## 清单",
        "",
    ]
    if not anomalies:
        lines.append("- （无异常）")
    else:
        for a in anomalies:
            lines.append(f"- {a}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--anomalies", type=Path, default=DEFAULT_ANOM)
    args = ap.parse_args()
    raise SystemExit(build(args.data_root, args.out, args.anomalies))


if __name__ == "__main__":
    main()
