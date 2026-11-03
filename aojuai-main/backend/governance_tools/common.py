"""Shared result types for governance scanners."""

from __future__ import annotations

from dataclasses import dataclass


class GovernanceDiscoveryError(AssertionError):
    """Raised when a scanner silently discovers no applicable targets."""


@dataclass(frozen=True)
class Violation:
    rule: str
    source: str
    line: int
    message: str

    def render(self) -> str:
        location = f"{self.source}:{self.line}" if self.line else self.source
        return f"{self.rule} {location}: {self.message}"


@dataclass(frozen=True)
class ScanResult:
    rule: str
    discovered: tuple[str, ...]
    violations: tuple[Violation, ...]


def require_discovered(rule: str, targets: tuple[str, ...], label: str) -> None:
    if not targets:
        raise GovernanceDiscoveryError(f"{rule}: discovered no {label}")


def validate_allowlist(rule: str, allowlist: dict[str, str]) -> None:
    missing_reasons = sorted(key for key, reason in allowlist.items() if not reason.strip())
    if missing_reasons:
        joined = ", ".join(missing_reasons)
        raise GovernanceDiscoveryError(f"{rule}: allowlist entries need reasons: {joined}")


def assert_clean(result: ScanResult) -> None:
    details = "\n".join(item.render() for item in result.violations)
    assert not result.violations, details
