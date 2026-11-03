"""智能体宏循环内核的行为契约。

重点锁三件**出错就会很贵**的事：预算真的能拦住循环、缺阶段处理器必须报错、
轨迹要如实反映每一步。这三条任何一条破了，症状都是"循环看起来在跑，
但要么停不下来烧钱，要么少做了检查还以为做了"。
"""

from __future__ import annotations

import pytest

from app.core.agent_loop import (
    OODA,
    PDCA,
    LoopBudget,
    LoopContext,
    LoopHooks,
    LoopModel,
    LoopPhase,
    PhaseResult,
    get_loop_model,
    list_loop_models,
    register_loop_model,
    run_agent_loop,
)


def _handlers(model: LoopModel, **overrides):
    async def noop(_context):
        return PhaseResult()

    return {code: overrides.get(code, noop) for code in model.phase_codes()}


@pytest.mark.asyncio
async def test_converged_stops_immediately() -> None:
    async def check(_context):
        return PhaseResult(converged=True, note="达标")

    outcome = await run_agent_loop(model=PDCA, handlers=_handlers(PDCA, check=check))
    assert outcome.stop_reason == "converged"
    assert outcome.iterations == 1


@pytest.mark.asyncio
async def test_max_iterations_caps_a_never_converging_loop() -> None:
    """永不收敛的循环必须被轮数上限拦住——这是无人值守场景的兜底。"""
    outcome = await run_agent_loop(
        model=PDCA,
        handlers=_handlers(PDCA),
        context=LoopContext(budget=LoopBudget(max_iterations=3)),
    )
    assert outcome.stop_reason == "max_iterations"
    assert outcome.iterations == 3


@pytest.mark.asyncio
async def test_cost_budget_stops_the_loop() -> None:
    """成本维度也要能拦。只有轮数上限的话，单轮很贵的循环照样烧穿。"""

    async def do(_context):
        return PhaseResult(cost=10.0, note="很贵的一步")

    outcome = await run_agent_loop(
        model=PDCA,
        handlers=_handlers(PDCA, do=do),
        context=LoopContext(budget=LoopBudget(max_iterations=100, max_cost=25)),
    )
    assert outcome.stop_reason == "budget_exhausted"
    assert outcome.spent_cost >= 25
    assert outcome.iterations == 3  # 第三轮结束后累计 30 >= 25


@pytest.mark.asyncio
async def test_abort_from_a_phase_stops_the_rest_of_the_iteration() -> None:
    calls: list[str] = []

    async def do(_context):
        calls.append("do")
        return PhaseResult(abort=True, note="外部依赖挂了")

    async def check(_context):
        calls.append("check")
        return PhaseResult()

    outcome = await run_agent_loop(model=PDCA, handlers=_handlers(PDCA, do=do, check=check))
    assert outcome.stop_reason == "aborted"
    assert "check" not in calls, "abort 之后不该继续跑后面的阶段"


@pytest.mark.asyncio
async def test_missing_handler_is_rejected_not_skipped() -> None:
    """缺处理器必须报错。跳过阶段会让轨迹说谎——看起来走完一轮，其实没做检查。"""
    handlers = _handlers(PDCA)
    handlers.pop("check")
    with pytest.raises(ValueError, match="missing handlers"):
        await run_agent_loop(model=PDCA, handlers=handlers)


@pytest.mark.asyncio
async def test_trace_records_every_phase_in_order() -> None:
    outcome = await run_agent_loop(
        model=OODA,
        handlers=_handlers(OODA),
        context=LoopContext(budget=LoopBudget(max_iterations=2)),
    )
    phases = [entry.phase for entry in outcome.trace.entries]
    assert phases == list(OODA.phase_codes()) * 2


@pytest.mark.asyncio
async def test_state_patches_accumulate_across_phases() -> None:
    async def plan(_context):
        return PhaseResult(state_patch={"goal": "g"})

    async def do(context):
        assert context.state["goal"] == "g", "后一阶段要能看到前一阶段写入的状态"
        return PhaseResult(state_patch={"draft": "d"})

    outcome = await run_agent_loop(
        model=PDCA,
        handlers=_handlers(PDCA, plan=plan, do=do),
        context=LoopContext(budget=LoopBudget(max_iterations=1)),
    )
    assert outcome.state == {"goal": "g", "draft": "d"}


@pytest.mark.asyncio
async def test_hooks_run_around_phases() -> None:
    seen: list[str] = []

    async def before(_ctx, phase):
        seen.append(f"before:{phase.code}")

    async def after(_ctx, phase, _result):
        seen.append(f"after:{phase.code}")

    await run_agent_loop(
        model=PDCA,
        handlers=_handlers(PDCA),
        context=LoopContext(budget=LoopBudget(max_iterations=1)),
        hooks=LoopHooks(before_phase=before, after_phase=after),
    )
    assert seen[:2] == ["before:plan", "after:plan"]


@pytest.mark.asyncio
async def test_absolute_ceiling_stops_a_loop_whose_budget_is_broken() -> None:
    """纵深防御：即使预算判定失效，内核也必须自己停下来。

    这条是变异测试逼出来的——把 `LoopBudget.exhausted` 改成永远返回 None 之后，
    循环会永远跑下去，测试直接挂死而不是变红。挂死的测试比失败的测试难查得多，
    失控的循环在生产上则是真金白银。
    """
    from app.core.agent_loop import ABSOLUTE_ITERATION_CEILING

    class NeverExhausted(LoopBudget):
        def exhausted(self, *, iteration: int):  # noqa: ARG002
            return None

    outcome = await run_agent_loop(
        model=PDCA,
        handlers=_handlers(PDCA),
        context=LoopContext(budget=NeverExhausted()),
    )
    assert outcome.stop_reason == "max_iterations"
    assert outcome.iterations == ABSOLUTE_ITERATION_CEILING


def test_builtin_models_are_registered() -> None:
    codes = {model.code for model in list_loop_models()}
    assert {"pdca", "ooda"} <= codes
    assert get_loop_model("pdca").phase_codes() == ("plan", "do", "check", "act")
    assert get_loop_model("ooda").phase_codes() == ("observe", "orient", "decide", "act")


def test_third_party_model_can_be_registered_without_editing_the_kernel() -> None:
    """下游要加第三种循环（比如 pi 那类）不该改内核文件。"""
    model = LoopModel(
        code="probe_loop",
        label="探针循环",
        suited_for="test",
        phases=(LoopPhase("only", "Only", "single phase"),),
    )
    register_loop_model(model)
    assert get_loop_model("probe_loop") is model


def test_duplicate_phase_codes_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate phase codes"):
        register_loop_model(
            LoopModel(
                code="bad_loop",
                label="x",
                suited_for="x",
                phases=(LoopPhase("a", "A", ""), LoopPhase("a", "A2", "")),
            )
        )
