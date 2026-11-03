"""Repository-wide static governance checks."""

from .common import GovernanceDiscoveryError, ScanResult, Violation, assert_clean
from .suite import run_all_checks

__all__ = [
    "GovernanceDiscoveryError",
    "ScanResult",
    "Violation",
    "assert_clean",
    "run_all_checks",
]
