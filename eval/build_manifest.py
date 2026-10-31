#!/usr/bin/env python3
"""Build manifest.csv for 198 originals + 3×198 processed images.

Layout (repo root, uploaded 2026-10-31):
  测试用/测试图/
  测试用/测试图_处理后/
  测试用/测试图_二次处理后/
  测试用/测试图_三次处理后/

Excluded: AI生图-即梦-0025..0029 (R-1). 校准图 not present / not scored.
Alignment: same stem across rounds (processed are .jpg).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

from eval.labels import (
    EXCLUDED_STEMS,
    is_excluded_original,
    label_for_stem,
    stem_of,
    subclass_for_stem,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "测试用"
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
    return sorted(
        p
        for p in dir_path.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


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
        _write_csv(out_csv, [])
        print(f"BLOCKED: assets missing at {data_root}", file=sys.stderr)
        return 2

    originals = list_images(g0)
    stem_to_g0: dict[str, list[Path]] = defaultdict(list)
    for p in originals:
        st = stem_of(p)
        if is_excluded_original(p):
            rows.append(
                _row(
                    st,
                    label_for_stem(st),
                    "g0",
                    p,
                    "excluded",
                    "R-1: no processed counterpart",
                )
            )
            continue
        stem_to_g0[st].append(p)

    for stem, paths in sorted(stem_to_g0.items()):
        if len(paths) > 1:
            anomalies.append(f"G0 duplicate stem `{stem}`: {[x.name for x in paths]}")
            for p in paths:
                rows.append(
                    _row(
                        stem,
                        label_for_stem(stem),
                        "g0",
                        p,
                        "conflict",
                        "duplicate stem; hold out of scoring",
                    )
                )
            continue
        p = paths[0]
        lab = label_for_stem(stem)
        note = subclass_for_stem(stem)
        if lab == "UNKNOWN":
            anomalies.append(f"G0 unknown label for stem `{stem}` ({p.name})")
            status = "anomaly"
            note = "unknown label from filename"
        else:
            status = "ok"
        if subclass_for_stem(stem) == "physical_other":
            note = "physical_other (Q4 screenshots/web-saved subclass)"
        rows.append(_row(stem, lab, "g0", p, status, note))

    ok_g0_stems = {r["stem"] for r in rows if r["round"] == "g0" and r["status"] == "ok"}

    for rnd, dirname in [
        ("r1", ROUND_DIRS["r1"]),
        ("r2", ROUND_DIRS["r2"]),
        ("r3", ROUND_DIRS["r3"]),
    ]:
        d = data_root / dirname
        files = list_images(d)
        by_stem: dict[str, list[Path]] = defaultdict(list)
        for p in files:
            by_stem[stem_of(p)].append(p)
        for stem, paths in sorted(by_stem.items()):
            if stem in EXCLUDED_STEMS:
                anomalies.append(f"{rnd} unexpected file for excluded stem `{stem}`")
            if len(paths) > 1:
                anomalies.append(
                    f"{rnd} naming conflict stem `{stem}`: {[x.name for x in paths]}"
                )
                for p in paths:
                    rows.append(
                        _row(
                            stem,
                            label_for_stem(stem),
                            rnd,
                            p,
                            "conflict",
                            "naming conflict",
                        )
                    )
                continue
            p = paths[0]
            if stem not in ok_g0_stems:
                anomalies.append(f"{rnd} orphan processed (no ok g0): `{p.name}`")
                status = "orphan"
                note = "no matching ok original"
            else:
                status = "ok"
                note = subclass_for_stem(stem)
            rows.append(_row(stem, label_for_stem(stem), rnd, p, status, note))
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

    _write_csv(out_csv, rows)
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[f"{r['round']}:{r['status']}"] += 1
    _write_anomalies(anom_md, anomalies, dict(counts))

    print(f"Wrote {len(rows)} rows → {out_csv}")
    print(f"Counts: {dict(counts)}")
    ok198 = counts.get("g0:ok", 0)
    if ok198 != 198:
        print(f"WARNING: g0:ok={ok198}, expected 198", file=sys.stderr)
        return 1
    for rnd in ("r1", "r2", "r3"):
        if counts.get(f"{rnd}:ok", 0) != 198:
            print(
                f"WARNING: {rnd}:ok={counts.get(f'{rnd}:ok', 0)}, expected 198",
                file=sys.stderr,
            )
            return 1
    # label balance check
    ai = sum(1 for r in rows if r["round"] == "g0" and r["status"] == "ok" and r["label"] == "ai_generated")
    phys = sum(1 for r in rows if r["round"] == "g0" and r["status"] == "ok" and r["label"] == "physical_device")
    print(f"G0 label balance: ai_generated={ai} physical_device={phys} (expect 66/132)")
    if ai != 66 or phys != 132:
        print("WARNING: label balance != 66/132", file=sys.stderr)
        return 1
    return 0


def _row(stem, label, rnd, path: Path, status, note) -> dict:
    return {
        "stem": stem,
        "label": label,
        "round": rnd,
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
        "status": status,
        "note": note,
    }


def _write_csv(out_csv: Path, rows: list[dict]) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["stem", "label", "round", "path", "sha256", "status", "note"],
        )
        w.writeheader()
        w.writerows(rows)


def _write_anomalies(path: Path, anomalies: list[str], counts: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 异常样本登记（不得静默丢弃）",
        "",
        "生成命令: `python -m eval.build_manifest`",
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
    # Always document R-1 explicitly
    lines += [
        "",
        "## R-1 排除（已登记，不计分母）",
        "",
    ]
    for s in sorted(EXCLUDED_STEMS):
        lines.append(f"- `{s}`")
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
