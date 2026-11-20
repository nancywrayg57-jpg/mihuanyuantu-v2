"""W3-A: queueSummary on processing-tasks list (sequential single-worker copy)."""

from __future__ import annotations

import math

import pytest

from app.capabilities.realphotos.api.s1 import (
    _QUEUE_MINUTES_PER_IMAGE_MAX,
    _QUEUE_MINUTES_PER_IMAGE_MIN,
    _queue_summary,
)


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def __await__(self):
        async def _inner():
            return self._value

        return _inner().__await__()


class _FakeDb:
    def __init__(self, ahead: int) -> None:
        self.ahead = ahead

    def scalar(self, _stmt):  # noqa: ANN001
        return _ScalarResult(self.ahead)


@pytest.mark.asyncio
async def test_queue_summary_empty_is_honest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REALPHOTOS_PROCESS_CONCURRENCY", "1")
    from app.core.config import settings

    monkeypatch.setattr(settings, "REALPHOTOS_PROCESS_CONCURRENCY", 1, raising=False)
    summary = await _queue_summary(_FakeDb(0))
    assert summary["aheadCount"] == 0
    assert summary["estimatedWaitMinutesMin"] == 0
    assert summary["estimatedWaitMinutesMax"] == 0
    assert summary["processConcurrency"] == 1
    assert summary["processingMode"] == "sequential_single_worker"
    assert summary["available"] is True


@pytest.mark.asyncio
async def test_queue_summary_estimates_wait_from_ahead(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "REALPHOTOS_PROCESS_CONCURRENCY", 1, raising=False)
    summary = await _queue_summary(_FakeDb(2))
    assert summary["aheadCount"] == 2
    assert summary["processConcurrency"] == 1
    assert summary["estimatedWaitMinutesMin"] == int(math.ceil(2 * _QUEUE_MINUTES_PER_IMAGE_MIN))
    assert summary["estimatedWaitMinutesMax"] == int(math.ceil(2 * _QUEUE_MINUTES_PER_IMAGE_MAX))


@pytest.mark.asyncio
async def test_queue_summary_divides_by_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "REALPHOTOS_PROCESS_CONCURRENCY", 2, raising=False)
    summary = await _queue_summary(_FakeDb(4))
    assert summary["processConcurrency"] == 2
    assert summary["processingMode"] == "parallel_process_slots"
    assert summary["estimatedWaitMinutesMin"] == int(math.ceil(2 * _QUEUE_MINUTES_PER_IMAGE_MIN))
    assert summary["estimatedWaitMinutesMax"] == int(math.ceil(2 * _QUEUE_MINUTES_PER_IMAGE_MAX))
