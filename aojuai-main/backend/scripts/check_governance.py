#!/usr/bin/env python3
"""Deployment preflight for repository-wide static governance rules."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from governance_tools import GovernanceDiscoveryError, run_all_checks  # noqa: E402


def main() -> int:
    try:
        results = run_all_checks(BACKEND_ROOT)
    except GovernanceDiscoveryError as exc:
        print(f"governance discovery failure: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"governance scanner error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    violations = [violation for result in results for violation in result.violations]
    for result in results:
        status = "FAIL" if result.violations else "PASS"
        print(f"{status} {result.rule}: discovered {len(result.discovered)} targets")
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
