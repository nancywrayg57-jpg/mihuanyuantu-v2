"""AOJU Backend - Assistant Global Execution Planner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.feature_switches import label_for_module, resolve_module_from_route_path
from app.domain.assistant.adapters import AdapterRegistry
from app.domain.assistant.execution_manifest import (
    as_manifest_list,
    best_manifest_intent_match,
    normalize_execution_route_path,
)
from app.domain.assistant.router_service import AssistantRouterService, is_text_entry_route

_INTENT_THRESHOLD_TEXT_ENTRY = 95
_INTENT_THRESHOLD_PAGE = 220
_CANDIDATE_THRESHOLD = 24
_AMBIGUOUS_MARGIN = 18


@dataclass(frozen=True)
class AssistantExecutionPlan:
    """Effective execution scope selected for one assistant turn."""

    route_path: str
    module_code: str | None
    module_name: str | None
    confidence: int
    source: str
    reason: str
    intent_id: str | None = None
    tool_id: str | None = None
    auto_execute: bool = False
    default_params: dict[str, Any] | None = None

    def to_context(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "activeRoutePath": self.route_path,
            "activeModuleCode": self.module_code,
            "activeModuleName": self.module_name,
            "confidence": self.confidence,
            "source": self.source,
            "reason": self.reason,
        }
        if self.intent_id:
            payload["activeIntentId"] = self.intent_id
        if self.tool_id:
            payload["activeToolId"] = self.tool_id
        if isinstance(self.default_params, dict) and self.default_params:
            payload["collectedParams"] = dict(self.default_params)
        if self.auto_execute:
            payload["autoExecute"] = True
        return payload


def _manifest_route_path(manifest: dict[str, Any], intent: dict[str, Any] | None = None) -> str:
    source = intent if isinstance(intent, dict) else {}
    route = (
        source.get("routePath")
        or source.get("route_path")
        or manifest.get("entryPath")
        or manifest.get("routePath")
    )
    if not route:
        route_prefixes = as_manifest_list(manifest.get("routePrefixes") or manifest.get("route_prefixes"))
        route = route_prefixes[0] if route_prefixes else "/"
    return normalize_execution_route_path(route)


def _active_module_from_context(*sources: dict[str, Any] | None) -> str | None:
    for source in sources:
        if not isinstance(source, dict):
            continue
        routing = source.get("_assistantRouting")
        if not isinstance(routing, dict):
            continue
        module_code = str(routing.get("activeModuleCode") or "").strip()
        if module_code:
            return module_code
    return None


class AssistantExecutionPlanner:
    """Resolve a turn-level execution scope before prompt/action handling."""

    def __init__(self, db) -> None:
        self.db = db

    async def collect_candidates(
        self,
        *,
        message: str,
        current_route_path: str,
        context_params: dict[str, Any] | None,
        session_context: dict[str, Any] | None,
        tenant_id: int,
        user_id: int,
        limit: int = 12,
    ) -> list[AssistantExecutionPlan]:
        """Collect likely module/tool candidates without making the final decision."""
        del tenant_id, user_id
        normalized_message = str(message or "").strip()
        if not normalized_message:
            return []

        current_route = normalize_execution_route_path(current_route_path)
        active_module_code = _active_module_from_context(context_params, session_context)
        ranked: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
        for adapter in AdapterRegistry.list_all():
            manifest_builder = getattr(adapter, "get_execution_manifest", None)
            manifest = manifest_builder() if callable(manifest_builder) else None
            if not isinstance(manifest, dict):
                continue
            for intent in as_manifest_list(manifest.get("intents")):
                if not isinstance(intent, dict):
                    continue
                from app.domain.assistant.execution_manifest import score_manifest_intent

                score = score_manifest_intent(
                    query_text=normalized_message,
                    manifest=manifest,
                    intent=intent,
                    active_module_code=active_module_code,
                    current_route_path=current_route,
                )
                if score >= _CANDIDATE_THRESHOLD:
                    ranked.append((score, manifest, intent))

        ranked.sort(key=lambda item: item[0], reverse=True)
        candidates: list[AssistantExecutionPlan] = []
        seen_tool_ids: set[str] = set()
        for score, manifest, intent in ranked:
            tool_id = str(intent.get("toolId") or intent.get("tool_id") or "").strip()
            if not tool_id or tool_id in seen_tool_ids:
                continue
            seen_tool_ids.add(tool_id)
            route_path = _manifest_route_path(manifest, intent)
            module_code = str(manifest.get("moduleCode") or manifest.get("module_code") or "").strip()
            if not module_code:
                module_code = resolve_module_from_route_path(route_path) or ""
            module_name = str(manifest.get("moduleName") or manifest.get("module_name") or "").strip()
            if not module_name and module_code:
                module_name = label_for_module(module_code)
            candidates.append(
                AssistantExecutionPlan(
                    route_path=route_path,
                    module_code=module_code or None,
                    module_name=module_name or None,
                    confidence=score,
                    source="candidate_tool",
                    reason=str(intent.get("summary") or intent.get("label") or "候选模块工具").strip(),
                    intent_id=str(intent.get("id") or "").strip() or None,
                    tool_id=tool_id,
                    auto_execute=bool(intent.get("autoExecute")),
                    default_params=dict(intent.get("defaultParams") or {}),
                )
            )
            if len(candidates) >= max(1, min(limit, 20)):
                break
        return candidates

    async def plan_turn(
        self,
        *,
        message: str,
        current_route_path: str,
        context_params: dict[str, Any] | None,
        session_context: dict[str, Any] | None,
        tenant_id: int,
        user_id: int,
    ) -> AssistantExecutionPlan | None:
        normalized_message = str(message or "").strip()
        if not normalized_message:
            return None

        current_route = normalize_execution_route_path(current_route_path)
        active_module_code = _active_module_from_context(context_params, session_context)
        text_entry = is_text_entry_route(current_route, context_params)
        intent_threshold = _INTENT_THRESHOLD_TEXT_ENTRY if text_entry else _INTENT_THRESHOLD_PAGE
        ranked: list[tuple[int, Any, dict[str, Any], dict[str, Any]]] = []

        for adapter in AdapterRegistry.list_all():
            manifest_builder = getattr(adapter, "get_execution_manifest", None)
            manifest = manifest_builder() if callable(manifest_builder) else None
            if not isinstance(manifest, dict):
                continue
            match = best_manifest_intent_match(
                query_text=normalized_message,
                manifest=manifest,
                active_module_code=active_module_code,
                current_route_path=current_route,
                threshold=intent_threshold,
            )
            if match is None:
                continue
            score, intent = match
            ranked.append((score, adapter, manifest, intent))

        if ranked:
            ranked.sort(key=lambda item: item[0], reverse=True)
            if len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= _AMBIGUOUS_MARGIN:
                score, _adapter, manifest, intent = ranked[0]
                route_path = _manifest_route_path(manifest, intent)
                module_code = str(manifest.get("moduleCode") or manifest.get("module_code") or "").strip()
                if not module_code:
                    module_code = resolve_module_from_route_path(route_path) or ""
                module_name = str(manifest.get("moduleName") or manifest.get("module_name") or "").strip()
                if not module_name and module_code:
                    module_name = label_for_module(module_code)
                intent_id = str(intent.get("id") or "").strip() or None
                tool_id = str(intent.get("toolId") or intent.get("tool_id") or "").strip() or None
                return AssistantExecutionPlan(
                    route_path=route_path,
                    module_code=module_code or None,
                    module_name=module_name or None,
                    confidence=score,
                    source="tool_intent",
                    reason=str(intent.get("summary") or intent.get("label") or "匹配到模块工具意图").strip(),
                    intent_id=intent_id,
                    tool_id=tool_id,
                    auto_execute=bool(intent.get("autoExecute")),
                    default_params=dict(intent.get("defaultParams") or {}),
                )

        route_decision = await AssistantRouterService(self.db).route_turn(
            message=normalized_message,
            current_route_path=current_route,
            context_params=context_params,
            session_context=session_context,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if route_decision is None:
            return None
        return AssistantExecutionPlan(
            route_path=route_decision.route_path,
            module_code=route_decision.module_code,
            module_name=route_decision.module_name,
            confidence=route_decision.confidence,
            source=route_decision.source,
            reason=route_decision.reason,
        )
