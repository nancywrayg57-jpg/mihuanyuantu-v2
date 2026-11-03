"""后台任务 worker 的通用轮询运行时。

骨架取自 nextjs-plugins 的三个 worker（harness / agent / ppt_master）——
它们 90% 是同一份代码，差别只有"认领哪种任务"。这里把骨架收成一份，
业务只需实现 `TaskSource`。

与参考实现刻意不同的两处：

1. **默认并发是 1，不是 10。** 参考实现的默认值 10 在 plugins 里没暴露问题，
   是因为 manage.sh 总会显式传 `--concurrency`（其默认是 1）。但作为基座默认值，
   "没传就起 10 个槽"是个陷阱：声明写漏一个字段就会悄悄起 10 条连接。
   宁可默认小了被人调大，也不要默认大了打满数据库。
2. **并发上限由调用方给**，不再是模块级常量。每个 worker 的合理上限不一样
   （`WorkerDefinition.max_concurrency`），上限写死在运行时里就等于所有 worker 一刀切。
"""

from __future__ import annotations

import argparse
import asyncio
import signal
from contextlib import suppress
from typing import Any, Protocol

from app.core.config import settings
from app.core.logger import get_logger, setup_logging
from app.infrastructure.database import close_db
from app.tasks.claim_gate import SerializedClaimGate

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_WORKER_CONCURRENCY = 1
DEFAULT_MAX_WORKER_CONCURRENCY = 20


class TaskSource(Protocol):
    """隔离任务认领与执行的业务差异，让轮询生命周期只维护一份。"""

    async def claim(self) -> dict[str, Any] | None: ...

    async def run(self, claimed: dict[str, Any]) -> None: ...

    def describe(self, claimed: dict[str, Any]) -> dict[str, Any]: ...


class PollingWorker:
    """为一个任务源提供可停止、失败隔离的并发轮询。"""

    def __init__(
        self,
        task_source: TaskSource,
        *,
        name: str,
        poll_interval: float,
        concurrency: int = DEFAULT_WORKER_CONCURRENCY,
        max_concurrency: int = DEFAULT_MAX_WORKER_CONCURRENCY,
        once: bool = False,
    ) -> None:
        self.task_source = task_source
        # name 必填：多个 worker 同时在跑时，日志里没有名字就分不清是谁在报错。
        self.name = name
        self.poll_interval = max(0.5, float(poll_interval))
        self.once = bool(once)
        self.concurrency = self._worker_concurrency(
            concurrency, once=self.once, max_concurrency=max_concurrency
        )
        self._stopping = asyncio.Event()
        self._claim_gate: SerializedClaimGate[dict[str, Any]] = SerializedClaimGate(
            poll_interval=self.poll_interval,
            stopping=self._stopping,
        )

    @staticmethod
    def _worker_concurrency(value: int | None, *, once: bool, max_concurrency: int) -> int:
        if once:
            return 1
        # 防止配置失误把数据库连接和下游服务同时打满。
        ceiling = max(1, int(max_concurrency))
        return max(1, min(ceiling, int(value or DEFAULT_WORKER_CONCURRENCY)))

    def stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        logger.info(
            "worker_started",
            worker=self.name,
            poll_interval=self.poll_interval,
            concurrency=self.concurrency,
            once=self.once,
        )
        try:
            slots = [
                asyncio.create_task(self._run_slot(slot_id=index + 1))
                for index in range(self.concurrency)
            ]
            await asyncio.gather(*slots)
        finally:
            await close_db()
            logger.info("worker_stopped", worker=self.name)

    async def _run_slot(self, *, slot_id: int) -> None:
        while not self._stopping.is_set():
            try:
                claimed = await self._claim_gate.claim(self.task_source.claim)
            except Exception as exc:
                logger.warning(
                    "worker_claim_failed",
                    slot_id=slot_id,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                await self._sleep()
                continue

            if claimed is None:
                if self.once:
                    self.stop()
                    break
                await self._sleep()
                continue

            # describe 是业务实现的，出错不能拖垮 slot——日志字段没了可以忍，worker 死了不行。
            try:
                described = self.task_source.describe(claimed)
            except Exception:  # noqa: BLE001
                described = {}
            task_fields = {"worker": self.name, "slot_id": slot_id, **described}
            logger.info("task_claimed", **task_fields)
            try:
                await self.task_source.run(claimed)
                logger.info("task_finished", **task_fields)
            except Exception as exc:
                failure_fields = {
                    **task_fields,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                logger.warning("task_failed", **failure_fields)

            if self.once:
                self.stop()
                break

    async def _sleep(self) -> None:
        # 等待停止事件而不是裸 sleep，保证进程关闭无需等完整轮询周期。
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_interval)


def _setting_float(name: str | None, default: float) -> float:
    if not name:
        return default
    try:
        return float(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def _setting_int(name: str | None, default: int) -> int:
    if not name:
        return default
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def run_worker_cli(
    task_source: TaskSource,
    *,
    name: str,
    default_concurrency: int = 1,
    poll_env: str | None = None,
    concurrency_env: str | None = None,
) -> None:
    """用统一的命令行和信号处理启动一个任务源。"""

    parser = argparse.ArgumentParser(description=f"Run AOJU {name} worker.")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=_setting_float(poll_env, DEFAULT_POLL_INTERVAL),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=_setting_int(concurrency_env, default_concurrency),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Claim and process at most one task, then exit.",
    )
    args = parser.parse_args()

    setup_logging()

    async def _amain() -> None:
        worker = PollingWorker(
            task_source,
            name=name,
            poll_interval=args.poll_interval,
            concurrency=args.concurrency,
            once=args.once,
        )
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(sig, worker.stop)
        await worker.run()

    asyncio.run(_amain())
