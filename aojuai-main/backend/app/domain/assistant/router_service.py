"""AOJU Backend - Assistant Text Routing Service"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.feature_switches import label_for_module, list_module_catalog, resolve_module_from_route_path
from app.domain.assistant.adapters import AdapterRegistry
from app.domain.assistant.route_directory_service import AssistantScopeDirectoryService

_TEXT_ENTRY_ROUTES = {"/", "/assistant", "/message-channel"}
_ROUTING_STATE_KEY = "_assistantRouting"
_ROUTING_FILLERS = (
    "请问",
    "请",
    "帮我",
    "帮忙",
    "一下",
    "当前",
    "现在",
    "我想",
    "我要",
    "想要",
    "查询",
    "查看",
    "看看",
    "看下",
    "打开",
    "进入",
    "前往",
    "跳转",
    "导航",
    "页面",
    "模块",
    "系统",
    "后台",
    "首页",
    "相关",
    "功能",
    "在哪",
    "哪里",
)
_ROUTING_THRESHOLD = 120
_TEXT_ENTRY_THRESHOLD = 90


@dataclass(frozen=True)
class AssistantRouteDecision:
    """Effective route selected for a single assistant turn."""

    route_path: str
    module_code: str | None
    module_name: str | None
    confidence: int
    source: str
    reason: str

    def to_context(self) -> dict[str, Any]:
        return {
            "activeRoutePath": self.route_path,
            "activeModuleCode": self.module_code,
            "activeModuleName": self.module_name,
            "confidence": self.confidence,
            "source": self.source,
            "reason": self.reason,
        }


def is_text_entry_route(route_path: str | None, context_params: dict[str, Any] | None = None) -> bool:
    route = _normalize_route_path(route_path)
    source = str((context_params or {}).get("source") or "").strip()
    return source == "message_channel" or route in _TEXT_ENTRY_ROUTES


def is_message_channel_context(route_path: str | None, context_params: dict[str, Any] | None = None) -> bool:
    route = _normalize_route_path(route_path)
    source = str((context_params or {}).get("source") or "").strip()
    return source == "message_channel" or route == "/message-channel"


def routing_state_key() -> str:
    return _ROUTING_STATE_KEY


def _normalize_route_path(value: Any) -> str:
    route = str(value or "").strip()
    if not route:
        return "/"
    if not route.startswith("/"):
        route = f"/{route.lstrip('/')}"
    return route.rstrip("/") or "/"


def _normalize_lookup_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
    for filler in _ROUTING_FILLERS:
        text = text.replace(filler, " ")
    return re.sub(r"\s+", " ", text).strip()


def _compact_lookup_text(value: Any) -> str:
    return _normalize_lookup_text(value).replace(" ", "")


def _collect_fragments(value: Any, *, min_len: int = 2, max_len: int = 4, limit: int = 30) -> list[str]:
    normalized = _normalize_lookup_text(value)
    if not normalized:
        return []
    fragments: list[str] = []
    seen: set[str] = set()
    for token in normalized.split():
        compact_token = token.replace(" ", "")
        if len(compact_token) < min_len:
            continue
        upper_len = min(max_len, len(compact_token))
        for size in range(upper_len, min_len - 1, -1):
            for start in range(0, len(compact_token) - size + 1):
                fragment = compact_token[start : start + size]
                if fragment in seen:
                    continue
                seen.add(fragment)
                fragments.append(fragment)
                if len(fragments) >= limit:
                    return fragments
    return fragments


def _score_text_match(query_text: str, candidate_text: Any, *, weight: int) -> int:
    compact_query = _compact_lookup_text(query_text)
    compact_candidate = _compact_lookup_text(candidate_text)
    if not compact_query or not compact_candidate:
        return 0
    score = 0
    if compact_query == compact_candidate:
        score += 180 * weight
    elif compact_candidate in compact_query:
        score += 90 * weight + min(len(compact_candidate), 12) * weight
    elif compact_query in compact_candidate:
        score += 70 * weight + min(len(compact_query), 12) * weight
    matched = 0
    for fragment in _collect_fragments(query_text):
        if fragment not in compact_candidate:
            continue
        score += len(fragment) * weight
        matched += 1
        if matched >= 5:
            break
    return score


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class AssistantRouterService:
    """Route text-only assistant turns to the best module/route without coupling business code."""

    def __init__(self, db) -> None:
        self.db = db

    @staticmethod
    def _candidate_from_route_item(item: dict[str, Any], *, source: str) -> dict[str, Any] | None:
        route_path = _normalize_route_path(item.get("routePath") or item.get("path"))
        if route_path == "/" or item.get("canNavigate") is False:
            return None
        module_code = str(item.get("moduleCode") or resolve_module_from_route_path(route_path) or "").strip() or None
        module_name = str(item.get("moduleName") or (label_for_module(module_code) if module_code else "") or "").strip() or None
        title = str(item.get("title") or item.get("label") or route_path).strip()
        terms = [
            title,
            module_name,
            module_code,
            route_path,
            item.get("pageSummary"),
            *[str(value or "").strip() for value in _as_list(item.get("queryHints"))],
        ]
        return {
            "routePath": route_path,
            "moduleCode": module_code,
            "moduleName": module_name,
            "title": title,
            "terms": terms,
            "source": source,
        }

    @staticmethod
    def _candidate_from_manifest(manifest: dict[str, Any], *, source: str) -> dict[str, Any] | None:
        module_code = str(manifest.get("moduleCode") or manifest.get("module_code") or "").strip() or None
        if not module_code or module_code == "default":
            return None
        module_name = str(
            manifest.get("moduleName")
            or manifest.get("module_name")
            or label_for_module(module_code)
            or module_code
        ).strip()
        route_prefixes = [
            _normalize_route_path(value)
            for value in _as_list(manifest.get("routePrefixes") or manifest.get("route_prefixes"))
            if str(value or "").strip()
        ]
        route_path = _normalize_route_path(manifest.get("entryPath") or manifest.get("routePath") or (route_prefixes[0] if route_prefixes else ""))
        if route_path == "/":
            return None
        keywords = [
            *[str(value or "").strip() for value in _as_list(manifest.get("keywords"))],
            *[str(value or "").strip() for value in _as_list(manifest.get("aliases"))],
        ]
        terms = [
            module_name,
            module_code,
            route_path,
            manifest.get("summary"),
            manifest.get("description"),
            *route_prefixes,
            *keywords,
        ]
        return {
            "routePath": route_path,
            "moduleCode": module_code,
            "moduleName": module_name,
            "title": module_name,
            "terms": terms,
            "source": source,
        }

    @classmethod
    def _score_candidate(
        cls,
        *,
        query_text: str,
        candidate: dict[str, Any],
        current_route_path: str,
        active_module_code: str | None,
    ) -> int:
        route_path = str(candidate.get("routePath") or "").strip()
        if not route_path or route_path == current_route_path:
            return 0
        score = 0
        for term in _as_list(candidate.get("terms")):
            score += _score_text_match(query_text, term, weight=1)
        compact_query = _compact_lookup_text(query_text)
        module_code = str(candidate.get("moduleCode") or "").strip()
        module_name = _compact_lookup_text(candidate.get("moduleName"))
        if module_code and module_code == str(active_module_code or "").strip():
            score += 18
        if module_name and module_name in compact_query:
            score += 80
        if str(candidate.get("source") or "") == "scope":
            score += 20
        elif str(candidate.get("source") or "") == "adapter":
            score += 12
        return score

    @staticmethod
    def _active_module_from_context(session_context: dict[str, Any] | None, context_params: dict[str, Any] | None) -> str | None:
        for source in (context_params, session_context):
            if not isinstance(source, dict):
                continue
            routing = source.get(_ROUTING_STATE_KEY)
            if isinstance(routing, dict):
                value = str(routing.get("activeModuleCode") or "").strip()
                if value:
                    return value
        return None

    async def route_turn(
        self,
        *,
        message: str,
        current_route_path: str,
        context_params: dict[str, Any] | None,
        session_context: dict[str, Any] | None,
        tenant_id: int,
        user_id: int,
    ) -> AssistantRouteDecision | None:
        normalized_message = str(message or "").strip()
        if not normalized_message:
            return None
        current_route = _normalize_route_path(current_route_path)
        active_module_code = self._active_module_from_context(session_context, context_params)
        candidates: list[dict[str, Any]] = []
        seen_routes: set[str] = set()

        def collect(candidate: dict[str, Any] | None) -> None:
            if not isinstance(candidate, dict):
                return
            route_path = str(candidate.get("routePath") or "").strip()
            if not route_path or route_path in seen_routes:
                return
            seen_routes.add(route_path)
            candidates.append(candidate)

        if not is_message_channel_context(current_route, context_params):
            try:
                scope_directory = await AssistantScopeDirectoryService(self.db).build_scope_directory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    current_route_path=current_route,
                )
            except Exception:
                scope_directory = {}
            for scope_key in ("currentScope", "moduleScope", "globalScope"):
                scope = scope_directory.get(scope_key) if isinstance(scope_directory, dict) else None
                if not isinstance(scope, dict):
                    continue
                if isinstance(scope.get("item"), dict):
                    collect(self._candidate_from_route_item(scope["item"], source="scope"))
                for item in _as_list(scope.get("items")):
                    if isinstance(item, dict):
                        collect(self._candidate_from_route_item(item, source="scope"))

        for adapter in AdapterRegistry.list_all():
            manifest_builder = getattr(adapter, "get_routing_manifest", None)
            manifest = manifest_builder() if callable(manifest_builder) else {}
            if isinstance(manifest, dict):
                collect(self._candidate_from_manifest(manifest, source="adapter"))

        for item in list_module_catalog():
            if isinstance(item, dict):
                collect(
                    self._candidate_from_manifest(
                        {
                            "moduleCode": item.get("code"),
                            "moduleName": item.get("label"),
                            "summary": item.get("description"),
                            "aliases": item.get("aliases"),
                            "routePrefixes": item.get("routePrefixes"),
                        },
                        source="catalog",
                    )
                )

        ranked: list[tuple[int, dict[str, Any]]] = []
        for candidate in candidates:
            score = self._score_candidate(
                query_text=normalized_message,
                candidate=candidate,
                current_route_path=current_route,
                active_module_code=active_module_code,
            )
            if score > 0:
                ranked.append((score, candidate))
        if not ranked:
            return None
        ranked.sort(
            key=lambda pair: (
                pair[0],
                1 if pair[1].get("source") == "scope" else 0,
                len(str(pair[1].get("title") or "")),
            ),
            reverse=True,
        )
        score, selected = ranked[0]
        threshold = _TEXT_ENTRY_THRESHOLD if is_text_entry_route(current_route, context_params) else _ROUTING_THRESHOLD
        if score < threshold:
            return None
        route_path = str(selected.get("routePath") or "").strip()
        module_code = str(selected.get("moduleCode") or "").strip() or resolve_module_from_route_path(route_path)
        module_name = str(selected.get("moduleName") or "").strip() or (label_for_module(module_code) if module_code else "")
        return AssistantRouteDecision(
            route_path=route_path,
            module_code=module_code or None,
            module_name=module_name or None,
            confidence=score,
            source=str(selected.get("source") or "router"),
            reason=f"根据当前文本匹配到 {module_name or module_code or route_path}",
        )
