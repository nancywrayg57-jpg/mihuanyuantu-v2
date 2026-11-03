"""样例能力包的 worker 声明——同时是**新模块要照抄的模板**。

它演示三件事，缺一不可：

1. 用 `WorkerDefinition` 声明，不改任何中央文件、不改 manage.sh
2. `TaskSource` 只实现三个方法，轮询/并发/优雅退出全部由基座运行时负责
3. 业务处理跑在 `run_agent_loop` 里，于是**天然有预算上限和可复盘轨迹**

这里刻意不连数据库：样例的价值是把契约演示清楚，而不是塞满业务。
真实模块的 `claim()` 应当是一条带 `FOR UPDATE SKIP LOCKED` 的认领语句
（参考 nextjs-plugins 的 `app/domain/harness/async_runtime.py::claim_pending_harness_run`）。
"""

from __future__ import annotations

from typing import Any

from app.core.agent_loop import (
    LoopBudget,
    LoopContext,
    PhaseResult,
    run_agent_loop,
)
from app.core.logger import get_logger
from app.core.worker_registry import WorkerDefinition

logger = get_logger(__name__)

WORKER = WorkerDefinition(
    code="sample_items_review",
    label="样例条目复核",
    module_code="sample_items",
    task_source_factory="app.capabilities.sample_items.worker:build_task_source",
    default_concurrency=1,
    max_concurrency=4,
    poll_interval=2.0,
    description="官方样例：演示 TaskSource 契约与 PDCA 宏循环的最小接法",
)


class SampleItemTaskSource:
    """样例任务源。真实实现请把 `claim` 换成数据库认领语句。"""

    def __init__(self) -> None:
        # 样例不连库，用一个空队列表示"没有待办"，让 worker 正常空转
        self._pending: list[dict[str, Any]] = []

    async def claim(self) -> dict[str, Any] | None:
        return self._pending.pop(0) if self._pending else None

    async def run(self, claimed: dict[str, Any]) -> None:
        outcome = await run_agent_loop(
            model="pdca",
            handlers={
                "plan": self._plan,
                "do": self._do,
                "check": self._check,
                "act": self._act,
            },
            # 预算是必填的：无人值守的循环没有上限迟早烧穿账单
            context=LoopContext(
                state={"item_id": claimed.get("item_id")},
                budget=LoopBudget(max_iterations=3, max_seconds=60),
            ),
        )
        logger.info(
            "sample_items_review_finished",
            item_id=claimed.get("item_id"),
            stop_reason=outcome.stop_reason,
            iterations=outcome.iterations,
        )

    def describe(self, claimed: dict[str, Any]) -> dict[str, Any]:
        return {"item_id": claimed.get("item_id"), "tenant_id": claimed.get("tenant_id")}

    # —— PDCA 四个阶段：真实模块在这里调模型、查库、跑工具 ——

    async def _plan(self, context: LoopContext) -> PhaseResult:
        return PhaseResult(state_patch={"goal": "复核条目描述是否完整"}, note="定出本轮目标")

    async def _do(self, context: LoopContext) -> PhaseResult:
        return PhaseResult(state_patch={"draft": "（此处产出结果）"}, note="产出草稿", cost=1.0)

    async def _check(self, context: LoopContext) -> PhaseResult:
        # 收敛与否**只在 Check 决定**——这是 PDCA 与 OODA 的关键差别
        ok = bool(context.state.get("draft"))
        return PhaseResult(note="草稿已产出" if ok else "草稿为空", converged=ok)

    async def _act(self, context: LoopContext) -> PhaseResult:
        return PhaseResult(state_patch={"finalized": True}, note="定稿")


def build_task_source() -> SampleItemTaskSource:
    return SampleItemTaskSource()
