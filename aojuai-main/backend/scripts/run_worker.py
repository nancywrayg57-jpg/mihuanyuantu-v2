#!/usr/bin/env python3
"""按声明启动一个 worker：`python -m scripts.run_worker --worker <code>`。

统一入口的意义在于**运维侧只需要知道 code**，不需要知道业务模块路径。
manage.sh 从 `deploy/workers.json` 读到 code 就能起，加 worker 不用改运维脚本。

启动前会检查模块安装状态：模块没装就拒绝启动并返回非零——
否则会出现"路由没挂载、菜单没有，却有个进程在轮询它的表"这种荒唐状态。

    python -m scripts.run_worker --list                 # 看有哪些 worker
    python -m scripts.run_worker --worker sample_items_sync
    python -m scripts.run_worker --worker sample_items_sync --once   # 处理一个就退出
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.worker_registry import (  # noqa: E402
    build_task_source,
    discover_workers,
    installed_workers,
    resolve_concurrency,
    worker_by_code,
)
from app.core.worker_runtime import PollingWorker, run_worker_cli  # noqa: E402


def _list() -> int:
    installed = {item.code for item in installed_workers()}
    workers = discover_workers()
    if not workers:
        print("（当前没有任何 worker 声明）")
        return 0
    print(f"{'CODE':<28}{'MODULE':<18}{'INSTALLED':<11}{'CONCURRENCY':<12}LABEL")
    for item in workers:
        mark = "yes" if item.code in installed else "no"
        conc = resolve_concurrency(item) if item.code in installed else "-"
        print(f"{item.code:<28}{item.module_code or '(kernel)':<18}{mark:<11}{str(conc):<12}{item.label}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", help="worker code, see --list")
    parser.add_argument("--list", action="store_true", help="list declared workers and exit")
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--poll-interval", type=float)
    parser.add_argument("--once", action="store_true")
    options = parser.parse_args()

    if options.list or not options.worker:
        return _list()

    definition = worker_by_code(options.worker)
    if definition is None:
        known = ", ".join(item.code for item in discover_workers()) or "<none>"
        print(f"unknown worker {options.worker!r}; declared: {known}", file=sys.stderr)
        return 2

    if definition not in installed_workers():
        print(
            f"worker {definition.code!r} 属于模块 {definition.module_code!r}，"
            "该模块在本部署未安装，拒绝启动",
            file=sys.stderr,
        )
        return 3

    from app.core.logger import setup_logging

    setup_logging()
    import asyncio
    import signal
    from contextlib import suppress

    async def _amain() -> None:
        worker = PollingWorker(
            build_task_source(definition),
            name=definition.code,
            poll_interval=options.poll_interval or definition.poll_interval,
            concurrency=options.concurrency or resolve_concurrency(definition),
            max_concurrency=definition.max_concurrency,
            once=options.once,
        )
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(sig, worker.stop)
        await worker.run()

    asyncio.run(_amain())
    return 0


__all__ = ["main", "run_worker_cli"]


if __name__ == "__main__":
    raise SystemExit(main())
