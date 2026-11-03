"""智能体循环内核：把"一个 worker 到底在做什么"定义清楚。

## 为什么基座需要这一层

下游分支已经出现三个 worker（harness / agent / ppt_master），骨架 90% 相同，
差别只有"认领哪种任务"。但**真正会被反复重写的不是骨架，是循环本身**——
每个业务模块都要回答同一组问题：

- 一次运行分几步？每步产出什么？
- 什么时候算做完了？什么时候该停下来别烧钱了？
- 中间状态存在哪？出错重来时从哪一步接上？
- 每一步做了什么判断，事后怎么复盘？

这些问题各写各的，就会出现"看起来都在跑智能体，但没有一个能复盘"。
所以基座给出**循环模型**这个一等概念，业务模块选一种模型、填各阶段的处理器。

## 两种内置循环模型

选哪个取决于**任务是收敛型还是响应型**：

| | PDCA | OODA |
|---|---|---|
| 阶段 | Plan → Do → Check → Act | Observe → Orient → Decide → Act |
| 适合 | **收敛型**：有明确目标、每轮质量应当变好 | **响应型**：环境在变，要快速重新判断 |
| 停止条件 | 质量达标 / 不再改善 | 态势稳定 / 无需再动作 |
| 典型场景 | 内容生成后自检重写、方案迭代、复盘改进 | 监控告警处置、对话式排障、实时运营 |
| 关键产物 | 每轮的**检查结论**（Check） | 每轮的**态势判断**（Orient） |

两者共享同一套骨架：迭代、预算、终止判据、可复盘轨迹。差别只在阶段序列与
各阶段的语义。所以它们是同一个引擎的两种**策略**，不是两套代码。

模型是**可注册**的：`register_loop_model()` 允许下游加第三种（比如 PI 类循环），
不需要改本文件。

## 微循环 vs 宏循环：这一层管的是**宏**

对照 pi（github.com/earendil-works/pi）的分层会更清楚。pi 的 `agent-loop.ts` 是
**微循环**：一个 turn 内 LLM ↔ tool calls 的往返，停止条件是"模型不再要求调工具"。
它的 `harness/` 才是有状态编排层（session、compaction、steering 队列、suspend/resume）。

本文件是**宏循环**：决定"要不要再来一轮、这一轮的目标是什么、什么时候算做完"。
一次 `Do`/`Act` 阶段内部，完全可以去跑一整个微循环（一个带工具的 LLM 会话）。
两者不冲突，是上下层：

    宏循环（本文件）  Plan → Do ─────────────→ Check → Act
                              │
    微循环（业务实现）        └── LLM ⇄ tool ⇄ LLM ⇄ tool … 直到模型不再调工具

**为什么基座只收宏循环**：微循环强依赖具体的模型 SDK、工具协议、流式协议，
各分支差异大且变化快；宏循环只依赖"阶段"和"状态"，是真正共性的部分。

## 刻意与 pi 不同的一点：预算是必填的

pi 的循环**没有内置轮数/预算上限**，只有 AbortSignal（见其 agent-loop.ts）。
对本仓不合适：这里的循环跑在无人值守的后台 worker 里，没有人盯着终端随时 Ctrl-C。
所以 `LoopBudget` 是 `LoopContext` 的必备字段，三个维度（轮数/墙钟/业务成本）
任一耗尽即停。**没有上限的无人值守循环迟早会烧穿账单**。

## 不在这一层的东西

具体的 LLM 调用、检索、工具适配、计费——都不在这。这一层只管
"循环怎么转、什么时候停、怎么留痕"。业务把这些塞进阶段处理器里。
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

__all__ = [
    "ABSOLUTE_ITERATION_CEILING",
    "LoopBudget",
    "LoopContext",
    "LoopHooks",
    "LoopModel",
    "LoopOutcome",
    "LoopPhase",
    "LoopTrace",
    "PhaseHandler",
    "PhaseResult",
    "StopReason",
    "get_loop_model",
    "list_loop_models",
    "register_loop_model",
    "run_agent_loop",
]

StopReason = Literal["converged", "max_iterations", "budget_exhausted", "aborted", "failed"]

# 绝对轮数上限：**任何情况下**都不允许超过，包括预算被误配成极大值、
# 或者未来有人不小心改坏了预算判定。这是纵深防御的第二道——
# 变异测试证明过：把预算检查去掉之后循环会永远跑下去，测试直接挂死。
# 无人值守的循环失控的代价是真金白银，所以内核自己也要有兜底。
ABSOLUTE_ITERATION_CEILING = 1000


@dataclass(frozen=True)
class LoopPhase:
    """循环里的一个阶段。`code` 是稳定标识，写进轨迹与日志，不要改。"""

    code: str
    label: str
    description: str


@dataclass
class LoopBudget:
    """预算。**不设上限的循环迟早会烧穿账单**，所以这是必填项而不是可选项。

    三个维度任一耗尽都停：迭代次数、墙钟时间、业务自定义成本（token/积分/调用次数）。
    `spent` 由阶段处理器通过 `PhaseResult.cost` 累加，内核不猜业务的计价方式。
    """

    max_iterations: int = 8
    max_seconds: float | None = None
    max_cost: float | None = None
    spent_cost: float = 0.0
    started_at: float = field(default_factory=time.monotonic)

    def exhausted(self, *, iteration: int) -> StopReason | None:
        if iteration >= self.max_iterations:
            return "max_iterations"
        if self.max_seconds is not None and (time.monotonic() - self.started_at) >= self.max_seconds:
            return "budget_exhausted"
        if self.max_cost is not None and self.spent_cost >= self.max_cost:
            return "budget_exhausted"
        return None


@dataclass
class PhaseResult:
    """一个阶段的产出。

    - `state_patch`：合并进 `LoopContext.state` 的增量。用增量而不是整体替换，
      是为了让轨迹能回答"这一步**改了什么**"。
    - `converged`：只有阶段处理器知道任务算不算做完了，内核不猜。
    - `abort`：出现不该继续的情况（比如输入非法、外部依赖挂了），立刻停。
    - `cost`：本阶段花掉的业务成本，累加进预算。
    """

    state_patch: Mapping[str, Any] = field(default_factory=dict)
    note: str = ""
    converged: bool = False
    abort: bool = False
    cost: float = 0.0


@dataclass
class LoopContext:
    """跨迭代携带的状态。

    `state` 是业务自己的字典；内核只负责合并与留痕，不解释其内容。
    """

    state: dict[str, Any] = field(default_factory=dict)
    iteration: int = 0
    budget: LoopBudget = field(default_factory=LoopBudget)
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceEntry:
    iteration: int
    phase: str
    note: str
    cost: float
    elapsed_ms: int
    converged: bool
    aborted: bool


@dataclass
class LoopTrace:
    """可复盘轨迹：每个阶段做了什么、花了多少、是否收敛。

    这是循环内核存在的一半理由——没有轨迹的智能体循环出了问题只能靠猜。
    """

    entries: list[TraceEntry] = field(default_factory=list)

    def record(self, entry: TraceEntry) -> None:
        self.entries.append(entry)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "iteration": item.iteration,
                "phase": item.phase,
                "note": item.note,
                "cost": item.cost,
                "elapsedMs": item.elapsed_ms,
                "converged": item.converged,
                "aborted": item.aborted,
            }
            for item in self.entries
        ]


@dataclass
class LoopOutcome:
    stop_reason: StopReason
    iterations: int
    state: dict[str, Any]
    trace: LoopTrace
    spent_cost: float


class PhaseHandler(Protocol):
    """阶段处理器：业务把 LLM 调用、检索、工具执行塞进这里。"""

    def __call__(self, context: LoopContext) -> Awaitable[PhaseResult]: ...


@dataclass(frozen=True)
class LoopModel:
    """一种循环模型 = 一串有序阶段 + 一句话说明它适合什么。"""

    code: str
    label: str
    phases: tuple[LoopPhase, ...]
    suited_for: str

    def phase_codes(self) -> tuple[str, ...]:
        return tuple(phase.code for phase in self.phases)


PDCA = LoopModel(
    code="pdca",
    label="PDCA 改进循环",
    suited_for="收敛型任务：有明确目标，每轮质量应当变好（内容生成自检重写、方案迭代、复盘改进）",
    phases=(
        LoopPhase("plan", "Plan 计划", "基于当前状态定出这一轮要达成什么、怎么做"),
        LoopPhase("do", "Do 执行", "按计划产出结果"),
        LoopPhase("check", "Check 检查", "对照目标评估结果，给出可判定的结论——**收敛与否在这一步决定**"),
        LoopPhase("act", "Act 处置", "把检查结论固化：达标则定稿，未达标则写下一轮的改进方向"),
    ),
)

OODA = LoopModel(
    code="ooda",
    label="OODA 响应循环",
    suited_for="响应型任务：环境在变，需要快速重新判断（告警处置、对话式排障、实时运营）",
    phases=(
        LoopPhase("observe", "Observe 观察", "采集当前事实，不做解释"),
        LoopPhase("orient", "Orient 研判", "把事实转成态势判断——**这一步是 OODA 的重心**，决定后面动作对不对"),
        LoopPhase("decide", "Decide 决策", "在候选动作里选一个，并说明理由"),
        LoopPhase("act", "Act 行动", "执行决策并观察反馈；态势稳定则收敛"),
    ),
)


_MODELS: dict[str, LoopModel] = {PDCA.code: PDCA, OODA.code: OODA}


def register_loop_model(model: LoopModel) -> None:
    """注册新的循环模型。下游要加第三种循环时用这个，不要改本文件。"""
    if not model.phases:
        raise ValueError(f"loop model {model.code!r} must declare at least one phase")
    codes = [phase.code for phase in model.phases]
    if len(set(codes)) != len(codes):
        raise ValueError(f"loop model {model.code!r} has duplicate phase codes: {codes}")
    existing = _MODELS.get(model.code)
    if existing is not None and existing != model:
        raise ValueError(f"loop model {model.code!r} is already registered with a different definition")
    _MODELS[model.code] = model


def get_loop_model(code: str) -> LoopModel:
    try:
        return _MODELS[code]
    except KeyError:
        known = ", ".join(sorted(_MODELS)) or "<none>"
        raise KeyError(f"unknown loop model {code!r}; registered: {known}") from None


def list_loop_models() -> tuple[LoopModel, ...]:
    return tuple(_MODELS[code] for code in sorted(_MODELS))


@dataclass(frozen=True)
class LoopHooks:
    """循环钩子。取自 pi 的 hook 思路（beforeToolCall / shouldStopAfterTurn），
    但作用在**阶段**与**轮次**上。

    钩子是给横切关注点用的：留痕、限流、人工审批、注入外部信号。
    业务逻辑本身应该写在阶段处理器里，不要塞进钩子——钩子里出异常会中断整轮。
    """

    before_phase: Callable[[LoopContext, LoopPhase], Awaitable[None]] | None = None
    after_phase: Callable[[LoopContext, LoopPhase, PhaseResult], Awaitable[None]] | None = None
    should_stop_after_iteration: Callable[[LoopContext], Awaitable[bool]] | None = None


async def run_agent_loop(
    *,
    model: LoopModel | str,
    handlers: Mapping[str, PhaseHandler],
    context: LoopContext | None = None,
    should_abort: Callable[[], bool] | None = None,
    hooks: LoopHooks | None = None,
) -> LoopOutcome:
    """跑一个智能体循环，直到收敛、预算耗尽、或被中止。

    `handlers` 必须覆盖模型的**每一个**阶段——缺一个就报错而不是跳过。
    跳过阶段会让轨迹说谎（看起来走完了一轮，其实少做了检查），
    这类静默降级比直接失败难查得多。
    """
    resolved = get_loop_model(model) if isinstance(model, str) else model
    missing = [code for code in resolved.phase_codes() if code not in handlers]
    if missing:
        raise ValueError(f"loop model {resolved.code!r} is missing handlers for phases: {missing}")

    ctx = context or LoopContext()
    trace = LoopTrace()
    stop_reason: StopReason = "max_iterations"

    while True:
        if ctx.iteration >= ABSOLUTE_ITERATION_CEILING:
            stop_reason = "max_iterations"
            break
        exhausted = ctx.budget.exhausted(iteration=ctx.iteration)
        if exhausted is not None:
            stop_reason = exhausted
            break
        if should_abort is not None and should_abort():
            stop_reason = "aborted"
            break

        ctx.iteration += 1
        converged = False
        aborted = False

        for phase in resolved.phases:
            started = time.monotonic()
            if hooks is not None and hooks.before_phase is not None:
                await hooks.before_phase(ctx, phase)
            result = await handlers[phase.code](ctx)
            if hooks is not None and hooks.after_phase is not None:
                await hooks.after_phase(ctx, phase, result)
            if result.state_patch:
                ctx.state.update(result.state_patch)
            ctx.budget.spent_cost += float(result.cost or 0.0)
            trace.record(
                TraceEntry(
                    iteration=ctx.iteration,
                    phase=phase.code,
                    note=result.note,
                    cost=float(result.cost or 0.0),
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                    converged=bool(result.converged),
                    aborted=bool(result.abort),
                )
            )
            if result.abort:
                aborted = True
                break
            if result.converged:
                converged = True

        if aborted:
            stop_reason = "aborted"
            break
        if converged:
            stop_reason = "converged"
            break
        if hooks is not None and hooks.should_stop_after_iteration is not None:
            if await hooks.should_stop_after_iteration(ctx):
                stop_reason = "converged"
                break

    return LoopOutcome(
        stop_reason=stop_reason,
        iterations=ctx.iteration,
        state=dict(ctx.state),
        trace=trace,
        spent_cost=ctx.budget.spent_cost,
    )


def describe_models() -> Sequence[dict[str, Any]]:
    """给文档与 CLI 用的模型说明。"""
    return [
        {
            "code": item.code,
            "label": item.label,
            "suitedFor": item.suited_for,
            "phases": [
                {"code": phase.code, "label": phase.label, "description": phase.description}
                for phase in item.phases
            ],
        }
        for item in list_loop_models()
    ]
