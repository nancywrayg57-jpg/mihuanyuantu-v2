"""统一 AI client 工厂：全仓所有 OpenAI 兼容调用的单一封装入口。

各域（assistant/harness/aippt/ppt-master/cms_ai…）此前各自构造 OpenAIClient，
api_mode/流式/reasoning/缓存路由键等能力零散接入。统一到这里之后：

- **max_tokens 可空**：None/0 表示不下发（跟随模型默认，推荐）；正数才下发。
- **api_mode 三模式**：chat_completions（流式/非流式）与 responses（仅流式，
  非流式调用由 client 内部自动流式聚合）。
- **reasoning 默认关闭**：SVG/JSON/工具类生成靠契约约束，思考层收益低、时延
  成本高（实测关闭全线提速 16-45%）；对话场景可显式传 "default" 保留模型默认。
- **缓存路由键**：多上游网关按 user/prompt_cache_key 粘性路由，保住提示词缓存。

保持零业务依赖（仅内核+assistant 客户端），可整体回流 nextjs-base。
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.assistant.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

# reasoning 白名单(顶层设计 2026-08-12):非法值绝不出网——上游对未知
# reasoning 取值的行为不可控(参数错误或静默降级都有先例),配置层的任何
# 垃圾值在此归一为 None(不注入)。
AI_REASONING_EFFORT_WHITELIST = frozenset({"none", "minimal", "low", "medium", "high", "xhigh"})


def ai_cache_scope(domain: str, tenant_id: int | str) -> str:
    """缓存路由键的唯一命名权威:aoju-{domain}-tenant-{id}。

    全仓禁止在业务域内手写该格式;新增域一律经本函数取值,保证
    审计/网关侧可按统一前缀聚合。
    """
    normalized_domain = str(domain or "").strip().lower().replace("_", "-") or "app"
    return f"aoju-{normalized_domain}-tenant-{int(tenant_id)}"


def _default_reasoning_effort() -> str | None:
    value = str(os.getenv("AOJU_AI_REASONING_EFFORT", "none") or "none").strip().lower()
    # 迁移决策(2026-08-12):历史上 env "auto" 会把字面量 "auto" 发给上游,
    # 属未定义行为;白名单化后显式归 None(不注入,跟随模型默认)。
    if value in {"default", "", "auto"}:
        return None
    return value


def _normalize_reasoning_effort(value: str | None) -> str | None:
    if value == "auto":
        value = _default_reasoning_effort()
    if value in (None, "default", ""):
        return None
    normalized = str(value).strip().lower()
    if normalized not in AI_REASONING_EFFORT_WHITELIST:
        logger.warning("ai_reasoning_effort_rejected value=%s", normalized)
        return None
    return normalized


def build_ai_client(
    *,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_seconds: float = 120.0,
    api_mode: str = "chat_completions",
    reasoning_effort: str | None = "auto",
    cache_scope: str | None = None,
    tools: list[dict] | None = None,
) -> OpenAIClient:
    """构造统一配置的 OpenAIClient。

    reasoning_effort:
      - "auto"（默认）→ 取环境默认（AOJU_AI_REASONING_EFFORT，默认 "none"）
      - "default" / None → 不注入（跟随模型默认，对话场景用）
      - 其他值（"none"/"low"/"high"…）→ 原样注入
    max_tokens: None 或 <=0 → 不下发（模型默认）。
    """
    # 延迟导入:core 层不得在模块加载期拖起 app.domain 全量初始化
    # (aippt 顶层 import factory 会形成环;干净解释器可独立 import 本模块)
    from app.domain.assistant.openai_client import OpenAIClient

    client = OpenAIClient(
        base_url=str(base_url or "").strip(),
        api_key=str(api_key or "").strip(),
        model=str(model or "").strip(),
        temperature=temperature,
        max_tokens=int(max_tokens) if max_tokens and int(max_tokens) > 0 else 0,
        timeout_seconds=float(timeout_seconds or 120.0),
        api_mode=str(api_mode or "chat_completions").strip() or "chat_completions",
    )
    client.reasoning_effort = _normalize_reasoning_effort(reasoning_effort)
    if cache_scope:
        client.prompt_cache_scope = str(cache_scope)
    if tools:
        client.tools = list(tools)
    return client
