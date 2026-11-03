"""大模型用量事件与收集器（计量层，不含价格）。

设计背景见 docs/dev/issues/DEEP_INSIGHT_BILLING_GAP.md：差异化计费的前提是
"用量在源头按模型拆分"。本模块只做一件事——让每一次真实的模型/工具调用
在它已经拿到 usage 的地方上报一条 ``UsageEvent``，由包住业务动作的
``collect_usage()`` 收集；计价与扣费在别处（credits.pricing / settlement）。

约定：
- 没有收集器时 ``record_usage`` 静默返回 False，旧路径零影响；
- 收集器可嵌套，子级事件会同时向上冒泡到父级（深度洞察的阶段收集器嵌在
  任务收集器里，任务侧看到全部，阶段侧只看到自己的）；
- 事件只带模型名等事实，**不带密钥、不带价格**。
"""

from __future__ import annotations

import contextvars
import functools
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

UsageKind = Literal["llm", "image", "tool_call", "tts", "asr", "flat"]

_PROMPT_KEYS = (
    "prompt_tokens",  # OpenAI chat / DeepSeek / 千帆 / GLM / Kimi / 豆包
    "input_tokens",  # OpenAI responses / Anthropic（不含缓存部分，见下）
    "promptTokenCount",  # Gemini（含缓存部分）
    "prompt_eval_count",  # Ollama
    "inputTokenCount",
    "inputTokens",
    "promptTokens",
)
_COMPLETION_KEYS = (
    "completion_tokens",
    "output_tokens",
    "candidatesTokenCount",  # Gemini（不含 thoughts，见下）
    "eval_count",  # Ollama
    "completionTokenCount",
    "outputTokenCount",
    "outputTokens",
    "completionTokens",
)
_TOTAL_KEYS = ("total_tokens", "totalTokenCount", "totalToken", "totalTokens")


def _to_int(raw: object) -> int:
    """容忍字符串/浮点数字；None、非数字、负数一律按 0。"""
    if raw is None or isinstance(raw, bool):
        return 0
    try:
        value = int(float(raw)) if isinstance(raw, str) else int(raw)
    except (TypeError, ValueError):
        return 0
    return max(value, 0)


def _first_int(payload: dict[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return _to_int(payload.get(key))
    return 0


@dataclass(slots=True)
class UsageEvent:
    """一次可计费调用的事实记录。"""

    kind: UsageKind
    model: str = ""
    provider: str | None = None
    api_type: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0  # 缓存命中（读）：已计入 input_tokens，只是价格不同
    cache_write_tokens: int = 0  # 缓存写入（Anthropic cache_creation）：已计入 input_tokens，按输入价（可配）
    reasoning_tokens: int = 0  # 思考 token：已计入 output_tokens，只作明细
    quantity: Decimal = Decimal(0)
    unit_key: str | None = None
    estimated: bool = False
    stage: str | None = None
    source: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    extra: dict[str, Any] = field(default_factory=dict)
    settled_tx_id: int | None = None  # 已被哪笔流水结算；根动作只对未结算事件计价（防嵌套双计）

    @property
    def total_tokens(self) -> int:
        return int(self.input_tokens) + int(self.output_tokens)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["occurred_at"] = self.occurred_at.isoformat()
        payload["quantity"] = str(self.quantity)
        payload["totalTokens"] = self.total_tokens
        return payload


def normalize_usage_payload(usage: object) -> dict[str, int]:
    """把各家 usage 形状归一为 input / output / cached / cache_write / reasoning 五个整数。

    口径（计价语义固定）：
    - input_tokens = 全部输入（含缓存命中与缓存写入部分）；cached_tokens ⊆ input，cache_write ⊆ input。
    - output_tokens = 全部输出（含思考）；reasoning_tokens ⊆ output。
    各家差异：
    - OpenAI chat/responses：prompt|input_tokens 已含缓存；cached 在 *_tokens_details.cached_tokens；
      reasoning 在 completion|output_tokens_details.reasoning_tokens。
    - DeepSeek：prompt_tokens = prompt_cache_hit_tokens + prompt_cache_miss_tokens；hit 即 cached
      （新版同时给 prompt_tokens_details.cached_tokens，取其大者）。
    - Anthropic：input_tokens **不含**缓存；cache_read_input_tokens（命中）与
      cache_creation_input_tokens（写入）要加回 input。
    - Gemini：promptTokenCount 已含缓存，cachedContentTokenCount 即 cached；candidatesTokenCount
      **不含** thoughtsTokenCount，输出要相加。
    - Ollama：prompt_eval_count / eval_count。数值允许字符串与浮点。
    total 只用于输入输出都缺时的兜底（全部记到输入侧，不虚增输出价）。
    """
    payload = usage if isinstance(usage, dict) else {}
    input_tokens = _first_int(payload, _PROMPT_KEYS)
    output_tokens = _first_int(payload, _COMPLETION_KEYS)

    # --- 缓存命中（读） ---
    cached = 0
    for key in ("prompt_tokens_details", "input_tokens_details"):
        details = payload.get(key)
        if isinstance(details, dict):
            cached = max(cached, _to_int(details.get("cached_tokens")))
    cached = max(cached, _to_int(payload.get("cached_tokens")))
    deepseek_hit = _to_int(payload.get("prompt_cache_hit_tokens"))
    deepseek_miss = _to_int(payload.get("prompt_cache_miss_tokens"))
    if deepseek_hit or deepseek_miss:
        cached = max(cached, deepseek_hit)
        if input_tokens <= 0:
            input_tokens = deepseek_hit + deepseek_miss
    anthropic_read = _to_int(payload.get("cache_read_input_tokens"))
    anthropic_write = _to_int(payload.get("cache_creation_input_tokens"))
    if anthropic_read or anthropic_write:
        # Anthropic 的 input_tokens 不含缓存部分：加回，保持"input = 全部输入"的口径
        input_tokens += anthropic_read + anthropic_write
        cached = max(cached, anthropic_read)
    cached = max(cached, _to_int(payload.get("cachedContentTokenCount")))  # Gemini（promptTokenCount 已含）
    cache_write = max(anthropic_write, _to_int(payload.get("cache_write_tokens")))
    for key in ("prompt_tokens_details", "input_tokens_details"):
        details = payload.get(key)
        if isinstance(details, dict):
            # 部分网关（gateway-a.example.com 实测）在 details 里给 cache_write_tokens；input 已含该部分
            cache_write = max(cache_write, _to_int(details.get("cache_write_tokens")))

    # --- 思考 token ---
    reasoning = 0
    for key in ("completion_tokens_details", "output_tokens_details"):
        details = payload.get(key)
        if isinstance(details, dict):
            reasoning = max(reasoning, _to_int(details.get("reasoning_tokens")))
    reasoning = max(reasoning, _to_int(payload.get("reasoning_tokens")))
    thoughts = _to_int(payload.get("thoughtsTokenCount"))
    if thoughts:
        # Gemini：candidatesTokenCount 不含 thoughts，输出侧要加回
        output_tokens += thoughts
        reasoning = max(reasoning, thoughts)

    if input_tokens <= 0 and output_tokens <= 0:
        total = _first_int(payload, _TOTAL_KEYS)
        if total > 0:
            input_tokens = total
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": min(cached, input_tokens) if input_tokens else cached,
        "cache_write_tokens": min(cache_write, input_tokens) if input_tokens else cache_write,
        "reasoning_tokens": min(reasoning, output_tokens) if output_tokens else reasoning,
    }


class UsageCollector:
    """收集一段业务动作内的全部用量事件；可嵌套。"""

    __slots__ = ("events", "parent", "stage", "label", "snapshot_attached", "overflow")

    MAX_EVENTS = 2000  # 超过后按 (kind, model, stage) 聚合，防止长任务把流水 extra 撑爆

    def __init__(self, *, parent: UsageCollector | None = None, stage: str | None = None, label: str | None = None):
        self.events: list[UsageEvent] = []
        self.parent = parent
        self.stage = stage
        self.label = label
        self.snapshot_attached = False
        self.overflow = 0

    @property
    def is_root(self) -> bool:
        return self.parent is None

    def add(self, event: UsageEvent) -> None:
        if not event.stage and self.stage:
            event.stage = self.stage
        self._append(event)
        if self.parent is not None:
            self.parent.add(event)

    def _append(self, event: UsageEvent) -> None:
        # 不在收集时聚合复制：复制会破坏父子收集器共享的事件身份，子级 settled 标记
        # 无法传到父级（codex 评审 2026-08-26）。上限只在 to_items() 输出时压缩。
        self.events.append(event)
        if len(self.events) > self.MAX_EVENTS:
            self.overflow += 1

    def unsettled_events(self) -> list[UsageEvent]:
        return [event for event in self.events if event.settled_tx_id is None]

    def mark_settled(self, tx_id: int) -> int:
        """把本收集器（含子级冒泡上来的）尚未结算的事件标为已由 tx_id 结算。

        嵌套场景：planner 在子收集器里先扣费，其事件同时存在于根收集器；打标后
        根动作结算时自动跳过，避免同一段用量被两笔流水各计一次。
        """
        count = 0
        for event in self.events:
            if event.settled_tx_id is None:
                event.settled_tx_id = int(tx_id)
                count += 1
        return count

    def tag_untagged(self, stage: str) -> int:
        """给尚无 stage 的事件补阶段标签（runner 按阶段顺序推进时回填），返回补标数。"""
        count = 0
        for event in self.events:
            if not event.stage:
                event.stage = stage
                count += 1
        return count

    def __len__(self) -> int:
        return len(self.events)

    def totals(self) -> dict[str, int]:
        return {
            "inputTokens": sum(e.input_tokens for e in self.events if e.kind == "llm"),
            "outputTokens": sum(e.output_tokens for e in self.events if e.kind == "llm"),
            "cachedTokens": sum(e.cached_tokens for e in self.events if e.kind == "llm"),
            "cacheWriteTokens": sum(e.cache_write_tokens for e in self.events if e.kind == "llm"),
            "reasoningTokens": sum(e.reasoning_tokens for e in self.events if e.kind == "llm"),
            "llmCalls": sum(1 for e in self.events if e.kind == "llm"),
            "toolCalls": int(sum(e.quantity for e in self.events if e.kind == "tool_call")),
            "images": int(sum(e.quantity for e in self.events if e.kind == "image")),
        }

    def by_model(self) -> dict[str, dict[str, int]]:
        grouped: dict[str, dict[str, int]] = {}
        for event in self.events:
            if event.kind != "llm":
                continue
            bucket = grouped.setdefault(event.model or "", {"inputTokens": 0, "outputTokens": 0, "cachedTokens": 0, "cacheWriteTokens": 0, "reasoningTokens": 0, "calls": 0})
            bucket["inputTokens"] += event.input_tokens
            bucket["outputTokens"] += event.output_tokens
            bucket["cachedTokens"] += event.cached_tokens
            bucket["cacheWriteTokens"] += event.cache_write_tokens
            bucket["reasoningTokens"] += event.reasoning_tokens
            bucket["calls"] += 1
        return grouped

    def by_stage(self) -> dict[str, dict[str, int]]:
        grouped: dict[str, dict[str, int]] = {}
        for event in self.events:
            bucket = grouped.setdefault(event.stage or "", {"inputTokens": 0, "outputTokens": 0, "calls": 0, "units": 0})
            bucket["inputTokens"] += event.input_tokens
            bucket["outputTokens"] += event.output_tokens
            bucket["calls"] += 1 if event.kind == "llm" else 0
            bucket["units"] += int(event.quantity) if event.kind != "llm" else 0
        return grouped

    def to_items(self) -> list[dict[str, Any]]:
        """流水明细：超过 MAX_EVENTS 的部分按 (kind, model, stage) 聚合成一条，避免 extra 撑爆。"""
        events = [e for e in self.events]
        if len(events) <= self.MAX_EVENTS:
            return [event.to_dict() for event in events]
        head = [event.to_dict() for event in events[: self.MAX_EVENTS]]
        grouped: dict[tuple[str, str, str | None], UsageEvent] = {}
        for event in events[self.MAX_EVENTS :]:
            key = (event.kind, event.model, event.stage)
            agg = grouped.get(key)
            if agg is None:
                agg = UsageEvent(
                    kind=event.kind,
                    model=event.model,
                    provider=event.provider,
                    api_type=event.api_type,
                    stage=event.stage,
                    source=event.source,
                    occurred_at=event.occurred_at,
                    extra={"aggregated": 0},
                )
                grouped[key] = agg
            agg.input_tokens += event.input_tokens
            agg.output_tokens += event.output_tokens
            agg.cached_tokens += event.cached_tokens
            agg.cache_write_tokens += event.cache_write_tokens
            agg.reasoning_tokens += event.reasoning_tokens
            agg.quantity += event.quantity
            agg.estimated = agg.estimated or event.estimated
            agg.extra["aggregated"] = int(agg.extra["aggregated"]) + 1
        return head + [agg.to_dict() for agg in grouped.values()]


_USAGE_COLLECTOR: contextvars.ContextVar[UsageCollector | None] = contextvars.ContextVar(
    "aoju_credit_usage_collector",
    default=None,
)

_SUPPRESSED_SOURCES: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar(
    "aoju_credit_usage_suppressed_sources",
    default=frozenset(),
)


@contextmanager
def suppress_usage_sources(*sources: str) -> Iterator[None]:
    """临时屏蔽某些上报来源。

    用于"外层已按阶段上报、内层共享客户端又会再报一次"的场景（深度洞察的
    responses provider 走 OpenAIClient）：外层带 stage 记账，内层 openai_client 静默。
    """
    merged = _SUPPRESSED_SOURCES.get() | frozenset(str(item) for item in sources if item)
    token = _SUPPRESSED_SOURCES.set(merged)
    try:
        yield
    finally:
        _SUPPRESSED_SOURCES.reset(token)


def _source_suppressed(source: str | None) -> bool:
    return bool(source) and source in _SUPPRESSED_SOURCES.get()


def current_usage_collector() -> UsageCollector | None:
    return _USAGE_COLLECTOR.get()


@contextmanager
def collect_usage(*, stage: str | None = None, label: str | None = None, root: bool = False) -> Iterator[UsageCollector]:
    """包住一次业务动作；嵌套时自动挂到外层收集器下。

    ContextVar 会随 asyncio.create_task / gather 复制到子任务，子任务里的
    record_usage 仍写进同一个收集器对象（列表是共享引用）。
    root=True：强制新开根收集器、不挂父级——用于 detached 后台任务，避免它继承
    已结束请求的旧收集器（codex 评审 2026-08-26）。
    """
    collector = UsageCollector(parent=None if root else _USAGE_COLLECTOR.get(), stage=stage, label=label)
    token = _USAGE_COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _USAGE_COLLECTOR.reset(token)


def record_usage(event: UsageEvent) -> bool:
    """上报一条事件；没有收集器时返回 False（旧路径零影响）。"""
    collector = _USAGE_COLLECTOR.get()
    if collector is None or _source_suppressed(event.source):
        return False
    collector.add(event)
    return True


def record_llm_usage(
    *,
    model: str,
    usage: object,
    api_type: str | None = None,
    provider: str | None = None,
    stage: str | None = None,
    source: str | None = None,
    estimated: bool = False,
    web_search_calls: int = 0,
    extra: dict[str, Any] | None = None,
) -> bool:
    """模型调用的便捷上报：归一 usage，并把 Responses 内置搜索次数拆成 tool_call 事件。"""
    collector = _USAGE_COLLECTOR.get()
    if collector is None or _source_suppressed(source):
        return False
    normalized = normalize_usage_payload(usage)
    collector.add(
        UsageEvent(
            kind="llm",
            model=str(model or ""),
            provider=provider,
            api_type=api_type,
            input_tokens=normalized["input_tokens"],
            output_tokens=normalized["output_tokens"],
            cached_tokens=normalized["cached_tokens"],
            cache_write_tokens=normalized["cache_write_tokens"],
            reasoning_tokens=normalized["reasoning_tokens"],
            estimated=bool(estimated),
            stage=stage,
            source=source,
            extra=dict(extra or {}),
        )
    )
    calls = _to_int(web_search_calls)
    if calls > 0:
        collector.add(
            UsageEvent(
                kind="tool_call",
                model=str(model or ""),
                provider=provider,
                api_type=api_type,
                quantity=Decimal(calls),
                unit_key="web_search",
                stage=stage,
                source=source,
            )
        )
    return True


def record_unit_usage(
    *,
    kind: UsageKind,
    quantity: Decimal | int | float,
    model: str = "",
    unit_key: str | None = None,
    provider: str | None = None,
    api_type: str | None = None,
    stage: str | None = None,
    source: str | None = None,
    estimated: bool = False,
    extra: dict[str, Any] | None = None,
) -> bool:
    """按件/按量事件（图片张数、工具次数、TTS 字符、ASR 秒数）。"""
    if kind == "llm":
        raise ValueError("llm 用量请用 record_llm_usage")
    try:
        amount = Decimal(str(quantity))
    except Exception:  # noqa: BLE001 - 非法数量按 0 处理
        amount = Decimal(0)
    if amount <= 0:
        return False
    return record_usage(
        UsageEvent(
            kind=kind,
            model=str(model or ""),
            provider=provider,
            api_type=api_type,
            quantity=amount,
            unit_key=unit_key,
            stage=stage,
            source=source,
            estimated=bool(estimated),
            extra=dict(extra or {}),
        )
    )


def usage_snapshot_for_extra(
    collector: UsageCollector | None = None, *, root_only: bool = False, once: bool = False
) -> dict[str, Any] | None:
    """把当前（或指定）收集器的事件压成可写入 credit_transactions.extra 的形状。

    形状：{"items": [...], "totals": {...}, "byModel": {...}, "byStage": {...}}；没有事件时返回 None。
    root_only：只有根收集器（业务根动作）才产出快照——子阶段不得各自落账；
    once：同一收集器只产出一次，避免同一根动作内多笔流水重复携带相同事件
    （codex 评审 2026-08-26：exactly-once 归属）。
    """
    target = collector if collector is not None else _USAGE_COLLECTOR.get()
    if target is None or not target.events:
        return None
    if root_only and not target.is_root:
        return None
    if once and target.snapshot_attached:
        return None
    target.snapshot_attached = True
    view = UsageCollector(stage=target.stage, label=target.label)
    view.events = target.unsettled_events()
    if not view.events:
        return None
    snapshot: dict[str, Any] = {
        "items": view.to_items(),
        "totals": view.totals(),
        "byModel": view.by_model(),
        "byStage": view.by_stage(),
    }
    settled_elsewhere = len(target.events) - len(view.events)
    if settled_elsewhere:
        snapshot["settledElsewhere"] = settled_elsewhere
    if target.overflow:
        snapshot["overflowEvents"] = target.overflow
    return snapshot


def tag_recent_usage(stage: str) -> int:
    """给当前收集器里尚未打标的事件补阶段（供按阶段顺序推进的 runner 使用）。"""
    collector = _USAGE_COLLECTOR.get()
    if collector is None:
        return 0
    return collector.tag_untagged(stage)


def collects_usage(label: str | None = None, *, stage: str | None = None, root: bool = False) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """把一个 async 方法/异步生成器整体包进 collect_usage()。

    用于一次业务动作的入口（一次对话回复、一次任务执行、一次工具调用）：
    动作内所有模型调用的用量都会落到同一个收集器，扣费时由
    ``usage_snapshot_for_extra`` 一并写进流水 extra。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.isasyncgenfunction(func):

            @functools.wraps(func)
            async def agen_wrapper(*args: Any, **kwargs: Any):
                with collect_usage(stage=stage, label=label, root=root):
                    async for item in func(*args, **kwargs):
                        yield item

            return agen_wrapper
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def coro_wrapper(*args: Any, **kwargs: Any):
                with collect_usage(stage=stage, label=label, root=root):
                    return await func(*args, **kwargs)

            return coro_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any):
            with collect_usage(stage=stage, label=label, root=root):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator
