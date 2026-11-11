#!/usr/bin/env python3
"""独立投递消费入口（AD-001 最小）：realphotos_notify_worker。

用法：
  python -m scripts.run_realphotos_notify_worker
  python -m scripts.run_realphotos_notify_worker --once
  python -m scripts.run_realphotos_notify_worker --poll-interval 1.0

不改 heartbeat 为唯一投递路径；本进程可单独启停。
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


async def _ensure_schema() -> None:
    from scripts.product_gap_fix_schema import ensure_product_gap_fix_schema
    from app.infrastructure.database.session import engine

    await ensure_product_gap_fix_schema(engine)


async def _tick_once() -> dict | None:
    from app.capabilities.realphotos.services.notify_outbox import RealphotosNotifyOutboxService
    from app.infrastructure.database.session import async_session_factory

    async with async_session_factory() as db:
        result = await RealphotosNotifyOutboxService(db).deliver_one()
        if result is None:
            await db.rollback()
            return None
        await db.commit()
        return result


async def _run(*, once: bool, poll_interval: float) -> int:
    from app.core.logger import get_logger, setup_logging
    from app.infrastructure.database.session import init_db

    setup_logging()
    logger = get_logger("realphotos_notify_worker")
    await init_db()
    await _ensure_schema()
    stop = asyncio.Event()

    def _stop(*_args: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    logger.info("realphotos_notify_worker_started", once=once, poll_interval=poll_interval)
    while not stop.is_set():
        result = await _tick_once()
        if result is not None:
            logger.info("realphotos_notify_delivered", **result)
            if once:
                return 0
            continue
        if once:
            return 0
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_interval)
        except TimeoutError:
            continue
    logger.info("realphotos_notify_worker_stopped")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    options = parser.parse_args()
    return asyncio.run(_run(once=options.once, poll_interval=max(0.2, float(options.poll_interval))))


if __name__ == "__main__":
    raise SystemExit(main())
