from __future__ import annotations

import asyncio

import pytest

from app.tasks.claim_gate import SerializedClaimGate


@pytest.mark.asyncio
async def test_empty_queue_is_polled_once_per_window_across_many_slots() -> None:
    stopping = asyncio.Event()
    gate: SerializedClaimGate[int] = SerializedClaimGate(
        poll_interval=0.2,
        stopping=stopping,
    )
    first_poll = asyncio.Event()
    calls = 0

    async def claim() -> int | None:
        nonlocal calls
        calls += 1
        first_poll.set()
        return None

    slots = [asyncio.create_task(gate.claim(claim)) for _ in range(20)]
    await asyncio.wait_for(first_poll.wait(), timeout=1)
    await asyncio.sleep(0.05)
    stopping.set()
    await asyncio.gather(*slots)

    assert calls == 1


@pytest.mark.asyncio
async def test_successful_claims_fill_all_available_slots_without_poll_delay() -> None:
    stopping = asyncio.Event()
    gate: SerializedClaimGate[int] = SerializedClaimGate(
        poll_interval=1,
        stopping=stopping,
    )
    queue = list(range(10))

    async def claim() -> int | None:
        return queue.pop(0) if queue else None

    claimed = await asyncio.gather(*(gate.claim(claim) for _ in range(10)))

    assert claimed == list(range(10))
