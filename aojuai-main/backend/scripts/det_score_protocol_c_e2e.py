#!/usr/bin/env python3
"""Protocol C Q1 chase after OPEN_PARTIAL + optional R4 overrides off.

Uses the ALIGN e2e runner shape: 26mm, score_fn rerank, n=12, seed=20261113.
Layer0 default off (ALIGN_LAYER0_IMG2IMG=0). CA already 0 in code.
Copies evidence to docs/.../DET-SCORE-OPTIMIZE-protocol-c-2026-11-14.txt
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
ALIGN_LOG = Path("/tmp/five-layer-legacy-align-e2e.log")
EVIDENCE = REPO / "docs" / "mihuanyuantu-v2" / "input" / "DET-SCORE-OPTIMIZE-protocol-c-2026-11-14.txt"


def main() -> int:
    for key in list(os.environ):
        if "proxy" in key.lower():
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    # Protocol C with post-whitelist defaults (no R4 overrides).
    os.environ["ALIGN_LAYER0_IMG2IMG"] = "0"
    os.environ.pop("ALIGN_LAYER0_OPTICAL_STRENGTH", None)
    os.environ.pop("ALIGN_NOISE_INTENSITY", None)
    os.environ.pop("ALIGN_FIXED_MODE_SCALE", None)
    os.environ["ALIGN_SAMPLE_N"] = os.environ.get("ALIGN_SAMPLE_N") or "12"

    sys.path.insert(0, str(BACKEND))
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")

    # Import after env so setdefault in align e2e keeps Layer0=0.
    from scripts.five_layer_legacy_align_e2e import main as align_main

    header = (
        "=== DET-SCORE protocol C (Q1 chase) ===\n"
        "layer0_img2img=0 ca_intensity=0 r4_overrides=off score_fn=on focal=26mm\n"
        "NOTE: wraps five_layer_legacy_align_e2e.py\n"
    )
    rc = align_main()
    body = ALIGN_LOG.read_text(encoding="utf-8") if ALIGN_LOG.exists() else ""
    EVIDENCE.write_text(header + body, encoding="utf-8")
    print(f"evidence_copy={EVIDENCE} rc={rc}")
    # Map align exit 4 (SHORTFALL) to 0 for orchestration if needed? Keep rc so caller sees shortfall.
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
