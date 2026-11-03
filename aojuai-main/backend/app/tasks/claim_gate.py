"""Coordinate idle polling without reducing task execution concurrency."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Generic, TypeVar


ClaimedT = TypeVar("ClaimedT")


class SerializedClaimGate(Generic[ClaimedT]):
    """Let one slot poll an empty queue while allowing fast concurrent claims.

    A worker may expose 20 execution slots, but an empty queue does not need 20
    identical database queries every poll interval. Successful claims leave the
    gate open so the remaining slots can fill immediately; an empty result or a
    claim error defers all slots until the next poll window.
    """

    def __init__(self, *, poll_interval: float, stopping: asyncio.Event) -> None:
        self.poll_interval = max(0.05, float(poll_interval))
        self.stopping = stopping
        self._lock = asyncio.Lock()
        self._next_claim_at = 0.0

    async def claim(self, callback: Callable[[], Awaitable[ClaimedT | None]]) -> ClaimedT | None:
        loop = asyncio.get_running_loop()
        while not self.stopping.is_set():
            delay = 0.0
            async with self._lock:
                delay = self._next_claim_at - loop.time()
                if delay <= 0:
                    try:
                        claimed = await callback()
                    except Exception:
                        self._next_claim_at = loop.time() + self.poll_interval
                        raise
                    if claimed is None:
                        self._next_claim_at = loop.time() + self.poll_interval
                    return claimed

            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.stopping.wait(), timeout=max(0.01, delay))
        return None
