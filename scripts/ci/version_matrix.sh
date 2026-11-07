#!/usr/bin/env bash
# ALIGN-GAP G5: print architecture / lock / workflow version matrix.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
python3 - <<'PY'
from __future__ import annotations

import json
import re
from pathlib import Path

root = Path(".")
arch = (root / "docs/蜜獾原图-v2-项目架构-v1.0.md").read_text(encoding="utf-8")
ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
pyproject = (root / "aojuai-main/backend/pyproject.toml").read_text(encoding="utf-8")
pkg = json.loads((root / "aojuai-main/frontend/package.json").read_text(encoding="utf-8"))

def first(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    return m.group(1) if m else "unknown"

arch_py = first(r"Python\s+(3\.\d+)", arch)
arch_pnpm = first(r"pnpm\s+(\d+)", arch)
arch_node = first(r"Node\.js\s+(\d+)", arch)
req_py = first(r'requires-python\s*=\s*"([^"]+)"', pyproject)
ci_py = first(r'python-version:\s*"?([0-9.]+)"?', ci)
ci_node = first(r'node-version:\s*"?([0-9.]+)"?', ci)
m = re.search(r"pnpm/action-setup[\s\S]{0,120}?version:\s*([0-9]+)", ci)
ci_pnpm = m.group(1) if m else "unknown"
pkg_mgr = str(pkg.get("packageManager") or "unset")

print("version_matrix=recorded")
print(f"arch_python={arch_py} arch_pnpm={arch_pnpm} arch_node={arch_node}")
print(f"lock_requires_python={req_py} packageManager={pkg_mgr}")
print(f"workflow_python={ci_py} workflow_pnpm={ci_pnpm} workflow_node={ci_node}")

# Honest align: CI pins verified install surface; architecture states recommended targets.
# Do not silently bump CI to 3.12/pnpm10 without Owner lockfile verification.
if ci_py == "3.11" and ">=3.11" in req_py and ci_pnpm == "9":
    print(
        "version_align=accepted_risk "
        "reason=ci_pins_verified_311_pnpm9_arch_recommends_312_pnpm10 "
        "owner_record=ALIGN-GAP-A5BC-G5"
    )
else:
    print("version_align=recorded_review_needed")
PY
