#!/usr/bin/env python3
"""AD-001 process 入口：仅认领 heartbeat/noop/process_image。

用法：
  python -m scripts.run_realphotos_process_worker
  python -m scripts.run_realphotos_process_worker --once
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


async def _run(*, once: bool, poll_interval: float) -> int:
    from app.capabilities.realphotos.worker import build_role_task_source
    from app.core.logger import get_logger, setup_logging
    from app.core.worker_runtime import PollingWorker
    from app.infrastructure.database.session import init_db

    setup_logging()
    logger = get_logger("realphotos_process_worker")
    await init_db()
    source = build_role_task_source(role="process", worker_id="realphotos_process")
    worker = PollingWorker(
        source,
        name="realphotos_process",
        poll_interval=poll_interval,
        concurrency=1,
        max_concurrency=4,
        once=once,
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            pass
    logger.info("realphotos_process_worker_started", once=once, poll_interval=poll_interval)
    await worker.run()
    logger.info("realphotos_process_worker_stopped")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    options = parser.parse_args()
    return asyncio.run(_run(once=options.once, poll_interval=max(0.2, float(options.poll_interval))))


if __name__ == "__main__":
    raise SystemExit(main())
