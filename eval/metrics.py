#!/usr/bin/env python3
"""Compute metrics A/B/C per work order §6.4–6.5 with Wilson CI."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "manifest.csv"
DEFAULT_RAW = ROOT / "results" / "raw"
DEFAULT_OUT = ROOT / "results" / "summaries"


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = (z / den) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def load_results(path: Path) -> dict[tuple[str, str], dict]:
    """Map (stem, round) → latest non-duplicate result preferring non-tech_fail."""
    best: dict[tuple[str, str], dict] = {}
    if not path.is_file():
        return best
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            key = (obj["stem"], obj["round"])
            prev = best.get(key)
            if prev is None:
                best[key] = obj
                continue
            # Prefer successful over tech_fail; else newer ts
            if prev.get("verdict") == "tech_fail" and obj.get("verdict") != "tech_fail":
                best[key] = obj
            elif obj.get("ts", 0) >= prev.get("ts", 0) and not (
                obj.get("verdict") == "tech_fail" and prev.get("verdict") != "tech_fail"
            ):
                best[key] = obj
    return best


def load_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status") == "ok"]


def summarize_detector(detector_id: str, manifest: list[dict], results: dict) -> dict:
    by_round: dict[str, list] = defaultdict(list)
    for row in manifest:
        key = (row["stem"], row["round"])
        res = results.get(key)
        by_round[row["round"]].append((row, res))

    report: dict = {"detector_id": detector_id, "gates": {}, "rounds": {}}

    # --- Metric A on g0 ---
    g0 = by_round.get("g0", [])
    missing = [(r, x) for r, x in g0 if x is None]
    present = [(r, x) for r, x in g0 if x is not None]

    def split(rows):
        ai_miss = real_fp = uncertain = tech = correct = total_scored = 0
        ai_n = real_n = 0
        mismatches = []
        for row, res in rows:
            v = res["verdict"]
            if v == "tech_fail":
                tech += 1
                continue
            if v == "uncertain":
                uncertain += 1
                continue
            total_scored += 1
            label = row["label"]
            if label == "ai_generated":
                ai_n += 1
                if v == "physical_device":
                    ai_miss += 1
                    mismatches.append(row["stem"])
                else:
                    correct += 1
            elif label == "physical_device":
                real_n += 1
                if v == "ai_generated":
                    real_fp += 1
                    mismatches.append(row["stem"])
                else:
                    correct += 1
        return {
            "ai_n_scored": ai_n,
            "real_n_scored": real_n,
            "A_ai": (ai_miss / ai_n) if ai_n else float("nan"),
            "A_ai_ci": wilson_interval(ai_miss, ai_n) if ai_n else (float("nan"),) * 2,
            "A_real": (real_fp / real_n) if real_n else float("nan"),
            "A_real_ci": wilson_interval(real_fp, real_n) if real_n else (float("nan"),) * 2,
            "A_total": ((ai_miss + real_fp) / total_scored) if total_scored else float("nan"),
            "uncertain": uncertain,
            "tech_fail": tech,
            "missing_results": len(missing),
            "n_expected": len(g0),
            "mismatches": mismatches,
        }

    a = split(present)
    a["missing_results"] = len(missing)
    report["metric_A"] = a

    # Gates
    def ok_rate(val, thr):
        return (not math.isnan(val)) and val <= thr

    uncertain_rate_g0 = a["uncertain"] / max(1, a["n_expected"] - a["tech_fail"] - a["missing_results"])
    tech_rate_g0 = a["tech_fail"] / max(1, a["n_expected"])
    completeness = a["missing_results"] == 0 and a["n_expected"] >= 198
    gate_pass = (
        ok_rate(a["A_ai"], 0.30)
        and ok_rate(a["A_real"], 0.05)
        and uncertain_rate_g0 <= 0.05
        and tech_rate_g0 <= 0.02
        and completeness
    )
    report["gates"] = {
        "A_ai_le_30": ok_rate(a["A_ai"], 0.30),
        "A_real_le_5": ok_rate(a["A_real"], 0.05),
        "uncertain_le_5": uncertain_rate_g0 <= 0.05,
        "tech_fail_le_2": tech_rate_g0 <= 0.02,
        "complete_g0": completeness,
        "enter_main_metric_B": gate_pass,
        "uncertain_rate_g0": uncertain_rate_g0,
        "tech_fail_rate_g0": tech_rate_g0,
    }

    # --- Metric B/C per processed round ---
    for rnd in ("r1", "r2", "r3"):
        rows = by_round.get(rnd, [])
        miss = sum(1 for _, x in rows if x is None)
        ai_fail = unc = tech = phys = 0
        screenshot_ai = 0
        screenshot_n = 0
        for row, res in rows:
            if res is None:
                continue
            v = res["verdict"]
            if v == "tech_fail":
                tech += 1
                continue
            if v == "uncertain":
                unc += 1
                continue
            if v == "ai_generated":
                ai_fail += 1
            elif v == "physical_device":
                phys += 1
            # Q4 subclass: renamed pack uses 其他-* ; legacy names used 截屏
            if "截屏" in row["stem"] or row["stem"].startswith("其他-"):
                screenshot_n += 1
                if v == "ai_generated":
                    screenshot_ai += 1
        denom = ai_fail + phys  # = 198 - unc - tech - (implicit miss not in denom)
        # Effective denom excludes uncertain & tech_fail; missing must be flagged
        B = (ai_fail / denom) if denom else float("nan")
        C = (unc / max(1, denom + unc)) if (denom + unc) else float("nan")
        # work order: C_round = uncertain / 该轮有效处理图数 — use denom+unc as有效 after removing tech
        effective = denom + unc
        C = (unc / effective) if effective else float("nan")
        worst_B = ((ai_fail + unc) / (denom + unc)) if (denom + unc) else float("nan")
        report["rounds"][rnd] = {
            "n_rows": len(rows),
            "missing_results": miss,
            "physical": phys,
            "ai_generated": ai_fail,
            "uncertain": unc,
            "tech_fail": tech,
            "B_round": B,
            "B_ci": wilson_interval(ai_fail, denom) if denom else (float("nan"),) * 2,
            "C_round": C,
            "B_worst_case_uncertain_as_fail": worst_B,
            "pass_B_lt_5": (not math.isnan(B)) and B < 0.05 and miss == 0,
            "pass_C_le_5": (not math.isnan(C)) and C <= 0.05,
            "screenshot_subclass_ai_rate": (screenshot_ai / screenshot_n) if screenshot_n else None,
            "screenshot_n": screenshot_n,
        }

    return report


def render_md(reports: list[dict]) -> str:
    lines = [
        "# 测试报告（指标汇总）",
        "",
        "> **声明**：本报告仅为模型判定结果，**不构成**任何平台上传验收承诺。",
        "> Gemini 定量对比按 Q8 **未执行**；见调研报告定性差异。",
        "",
    ]
    if not reports:
        lines += [
            "## 状态：未跑通全量",
            "",
            "原因见 `00-BLOCKERS.md`（测试资产缺失或检测器未安装）。",
            "",
        ]
        return "\n".join(lines) + "\n"

    for rep in reports:
        lines.append(f"## 检测器 `{rep['detector_id']}`")
        lines.append("")
        g = rep["gates"]
        a = rep["metric_A"]
        lines.append("### 门禁（指标 A）")
        lines.append("")
        lines.append(f"- A_ai (漏检) = {a['A_ai']:.4%} CI{a['A_ai_ci']}")
        lines.append(f"- A_real (误报) = {a['A_real']:.4%} CI{a['A_real_ci']}")
        lines.append(f"- A_total = {a['A_total']:.4%}")
        lines.append(f"- uncertain={a['uncertain']} tech_fail={a['tech_fail']} missing={a['missing_results']}")
        lines.append(f"- **进入主口径**: `{g['enter_main_metric_B']}`")
        lines.append("")
        lines.append("### 各轮未通过率（指标 B）")
        lines.append("")
        lines.append("| 轮次 | B_round | Wilson95% | C_uncertain | B最坏(unc计失败) | 通过B<5% |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for rnd in ("r1", "r2", "r3"):
            r = rep["rounds"].get(rnd, {})
            lines.append(
                f"| {rnd} | {r.get('B_round')} | {r.get('B_ci')} | {r.get('C_round')} | "
                f"{r.get('B_worst_case_uncertain_as_fail')} | {r.get('pass_B_lt_5')} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--detectors",
        default="lynote_univfd,nonescape_onnx,community_forensics",
    )
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if not args.manifest.is_file():
        print("manifest missing", file=sys.stderr)
        md = render_md([])
        (args.out_dir / "test_report.md").write_text(md, encoding="utf-8")
        raise SystemExit(2)

    manifest = load_manifest(args.manifest)
    reports = []
    for det in [x.strip() for x in args.detectors.split(",") if x.strip()]:
        raw = args.raw_dir / f"{det}.jsonl"
        results = load_results(raw)
        if not results:
            print(f"skip {det}: no results at {raw}")
            continue
        rep = summarize_detector(det, manifest, results)
        reports.append(rep)
        out_json = args.out_dir / f"{det}_metrics.json"
        out_json.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out_json}")

    md_path = args.out_dir / "test_report.md"
    md_path.write_text(render_md(reports), encoding="utf-8")
    # also copy to docs
    docs = ROOT / "docs" / "MH-YT-20261031-01" / "04-test-report.md"
    docs.write_text(render_md(reports), encoding="utf-8")
    print(f"wrote {md_path} and {docs}")
    raise SystemExit(0 if reports else 1)


if __name__ == "__main__":
    main()
