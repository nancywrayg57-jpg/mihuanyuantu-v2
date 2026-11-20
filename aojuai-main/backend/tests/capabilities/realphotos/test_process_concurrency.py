"""W3-B: process concurrency clamp + lease floor for multi-slot safety."""

from __future__ import annotations

from app.capabilities.realphotos.process_concurrency import (
    PROCESS_CONCURRENCY_MAX,
    clamp_process_concurrency,
)
from app.capabilities.realphotos.services.job_service import (
    PROCESS_JOB_LEASE_SECONDS,
    QUEUE_POLICY,
)


def test_clamp_defaults_and_bounds() -> None:
    assert clamp_process_concurrency(None) in range(1, PROCESS_CONCURRENCY_MAX + 1)
    assert clamp_process_concurrency(1) == 1
    assert clamp_process_concurrency(2) == 2
    assert clamp_process_concurrency(99) == PROCESS_CONCURRENCY_MAX
    assert clamp_process_concurrency(0) == 1
    assert clamp_process_concurrency("x") == 1


def test_process_lease_covers_multi_minute_jobs() -> None:
    # Concurrent slots reclaim running rows after lease_seconds under at_least_once.
    assert PROCESS_JOB_LEASE_SECONDS >= 900
    assert QUEUE_POLICY.lease_seconds == PROCESS_JOB_LEASE_SECONDS
    assert QUEUE_POLICY.delivery == "at_least_once"
