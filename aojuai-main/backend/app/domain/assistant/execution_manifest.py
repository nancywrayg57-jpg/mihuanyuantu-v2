"""Assistant execution manifest helpers.

Execution manifests describe module-level intents and tools without coupling the
assistant foundation to a specific business module.
"""

from __future__ import annotations

import re
from typing import Any

_LOOKUP_FILLERS = (
    "请问",
    "请",
    "帮我",
    "帮忙",
    "一下",
    "现在",
    "我想",
    "我要",
    "想要",
    "看看",
    "看下",
)


def normalize_execution_route_path(value: Any) -> str:
    route = str(value or "").strip()
    if not route:
        return "/"
    if not route.startswith("/"):
        route = f"/{route.lstrip('/')}"
    return route.rstrip("/") or "/"


def normalize_execution_lookup_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
    for filler in _LOOKUP_FILLERS:
        text = text.replace(filler, " ")
    return re.sub(r"\s+", " ", text).strip()


def compact_execution_lookup_text(value: Any) -> str:
    return normalize_execution_lookup_text(value).replace(" ", "")


def as_manifest_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_text_list(value: Any, *, limit: int = 24) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for raw in value:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
        if len(items) >= limit:
            break
    return items


def _tool_field_terms(tool: dict[str, Any], *, limit: int = 24) -> list[str]:
    terms: list[str] = []
    for field in as_manifest_list(tool.get("params")):
        if not isinstance(field, dict):
            continue
        terms.extend(
            [
                str(field.get("key") or "").strip(),
                str(field.get("label") or "").strip(),
                str(field.get("description") or "").strip(),
                *_as_text_list(field.get("examples"), limit=6),
                *_as_text_list(field.get("enumValues"), limit=6),
            ]
        )
        for option in as_manifest_list(field.get("enumOptions")):
            if isinstance(option, dict):
                terms.append(str(option.get("value") or "").strip())
                terms.append(str(option.get("label") or "").strip())
        if len([item for item in terms if item]) >= limit:
            break
    return [item for item in terms if item][:limit]


def _required_tool_fields(tool: dict[str, Any]) -> list[str]:
    required: list[str] = []
    for field in as_manifest_list(tool.get("params")):
        if not isinstance(field, dict) or field.get("required") is not True:
            continue
        key = str(field.get("key") or "").strip()
        if key:
            required.append(key)
    return required


def _is_read_like_tool(tool: dict[str, Any]) -> bool:
    if tool.get("confirmationRequired") is True:
        return False
    tool_id = str(tool.get("id") or "").strip().lower()
    if any(marker in tool_id for marker in (".create", ".update", ".delete", ".submit", ".review", ".approve")):
        return False
    access_mode = str(tool.get("accessMode") or "").strip().lower()
    tool_type = str(tool.get("toolType") or tool.get("mode") or "").strip().lower()
    mode = str(tool.get("mode") or "").strip().lower()
    return access_mode in {"read", "query"} or tool_type in {"query", "preview", "read"} or mode in {"query", "read"}


def _first_route_path(route_prefixes: list[Any]) -> str | None:
    for route_prefix in route_prefixes:
        route = normalize_execution_route_path(route_prefix)
        if route != "/":
            return route
    return None


def build_execution_manifest_from_tool_definitions(
    *,
    module_code: str,
    module_name: str,
    route_prefixes: list[Any] | None,
    tool_definitions: list[dict[str, Any]] | None,
    summary: str | None = None,
    keywords: list[Any] | None = None,
) -> dict[str, Any]:
    """Build planner metadata from published assistant tool definitions."""
    normalized_route_prefixes = [
        normalize_execution_route_path(item)
        for item in (route_prefixes or [])
        if str(item or "").strip()
    ]
    entry_path = _first_route_path(normalized_route_prefixes)
    intents: list[dict[str, Any]] = []
    for tool in tool_definitions or []:
        if not isinstance(tool, dict):
            continue
        tool_id = str(tool.get("id") or "").strip()
        if not tool_id:
            continue
        status = str(tool.get("status") or "active").strip().lower() or "active"
        required_fields = _required_tool_fields(tool)
        read_like = _is_read_like_tool(tool)
        default_params = dict(tool.get("defaultParams") or {})
        missing_fields = [field for field in required_fields if field not in default_params]
        route_path = normalize_execution_route_path(tool.get("routePath") or tool.get("targetRoutePath") or entry_path or "")
        label = str(tool.get("label") or tool_id).strip()
        tool_summary = str(tool.get("summary") or tool.get("description") or label).strip()
        auto_execute = (
            status == "active"
            and read_like
            and not missing_fields
            and tool.get("assistantAutoExecute", True) is not False
        )
        intent = {
            "id": f"{tool_id}.intent",
            "label": label,
            "summary": tool_summary,
            "description": str(tool.get("description") or tool_summary).strip(),
            "toolId": tool_id,
            "routePath": route_path if route_path != "/" else None,
            "keywords": [
                item
                for item in [
                    label,
                    tool_summary,
                    str(tool.get("resource") or "").strip(),
                    str(tool.get("resourceLabel") or "").strip(),
                    *_tool_field_terms(tool),
                ]
                if item
            ],
            "examples": _as_text_list(tool.get("examples"), limit=12),
            "autoExecute": auto_execute,
            "confirmationRequired": bool(tool.get("confirmationRequired")),
            "requiredFields": required_fields,
            "defaultParams": default_params,
        }
        intents.append(intent)
    return {
        "moduleCode": str(module_code or "").strip(),
        "moduleName": str(module_name or module_code or "").strip(),
        "entryPath": entry_path,
        "routePrefixes": normalized_route_prefixes,
        "keywords": _as_text_list(list(keywords or []), limit=16),
        "summary": str(summary or "").strip(),
        "intents": intents,
    }


def build_execution_manifest_from_capability_provider(
    *,
    provider: Any,
    module_name: str,
    fallback_route_prefixes: list[Any] | None = None,
) -> dict[str, Any]:
    """Build planner metadata from a registered capability provider."""
    from app.domain.assistant.capability_registry import build_provider_tool_definitions

    route_prefixes = [
        str(prefix or "").strip()
        for prefix, _payload in list(getattr(provider, "scope_rules", []) or [])
        if str(prefix or "").strip()
    ] or list(fallback_route_prefixes or [])
    return build_execution_manifest_from_tool_definitions(
        module_code=str(getattr(provider, "module_code", "") or "").strip(),
        module_name=module_name,
        route_prefixes=route_prefixes,
        tool_definitions=build_provider_tool_definitions(provider),
        summary=f"{module_name} 已发布的 AI 助手能力。",
    )


def collect_execution_fragments(
    value: Any,
    *,
    min_len: int = 2,
    max_len: int = 4,
    limit: int = 30,
) -> list[str]:
    normalized = normalize_execution_lookup_text(value)
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


def score_execution_text_match(query_text: str, candidate_text: Any, *, weight: int = 1) -> int:
    compact_query = compact_execution_lookup_text(query_text)
    compact_candidate = compact_execution_lookup_text(candidate_text)
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
    for fragment in collect_execution_fragments(query_text):
        if fragment not in compact_candidate:
            continue
        score += len(fragment) * weight
        matched += 1
        if matched >= 5:
            break
    return score


def manifest_module_terms(manifest: dict[str, Any]) -> list[Any]:
    return [
        manifest.get("moduleCode"),
        manifest.get("moduleName"),
        manifest.get("summary"),
        manifest.get("description"),
        manifest.get("entryPath"),
        *as_manifest_list(manifest.get("routePrefixes") or manifest.get("route_prefixes")),
        *as_manifest_list(manifest.get("keywords")),
        *as_manifest_list(manifest.get("aliases")),
    ]


def manifest_intent_terms(intent: dict[str, Any]) -> list[Any]:
    return [
        intent.get("id"),
        intent.get("label"),
        intent.get("summary"),
        intent.get("description"),
        intent.get("toolId") or intent.get("tool_id"),
        intent.get("routePath") or intent.get("route_path"),
        *as_manifest_list(intent.get("keywords")),
        *as_manifest_list(intent.get("aliases")),
        *as_manifest_list(intent.get("examples")),
        *as_manifest_list(intent.get("utterances")),
    ]


def score_manifest_intent(
    *,
    query_text: str,
    manifest: dict[str, Any],
    intent: dict[str, Any],
    active_module_code: str | None = None,
    current_route_path: str | None = None,
) -> int:
    score = 0
    for term in manifest_module_terms(manifest):
        score += score_execution_text_match(query_text, term, weight=1)
    for term in manifest_intent_terms(intent):
        score += score_execution_text_match(query_text, term, weight=2)
    module_code = str(manifest.get("moduleCode") or manifest.get("module_code") or "").strip()
    if module_code and module_code == str(active_module_code or "").strip():
        score += 28
    intent_route = normalize_execution_route_path(
        intent.get("routePath")
        or intent.get("route_path")
        or manifest.get("entryPath")
        or manifest.get("routePath")
        or ""
    )
    if current_route_path and intent_route == normalize_execution_route_path(current_route_path):
        score += 24
    return score


def best_manifest_intent_match(
    *,
    query_text: str,
    manifest: dict[str, Any],
    active_module_code: str | None = None,
    current_route_path: str | None = None,
    threshold: int = 95,
) -> tuple[int, dict[str, Any]] | None:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for intent in as_manifest_list(manifest.get("intents")):
        if not isinstance(intent, dict):
            continue
        score = score_manifest_intent(
            query_text=query_text,
            manifest=manifest,
            intent=intent,
            active_module_code=active_module_code,
            current_route_path=current_route_path,
        )
        if score >= threshold:
            ranked.append((score, intent))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0]


def infer_action_from_execution_manifest(
    *,
    manifest: dict[str, Any],
    text: str,
    active_module_code: str | None = None,
    current_route_path: str | None = None,
    threshold: int = 95,
) -> dict[str, Any] | None:
    match = best_manifest_intent_match(
        query_text=text,
        manifest=manifest,
        active_module_code=active_module_code,
        current_route_path=current_route_path,
        threshold=threshold,
    )
    if match is None:
        return None
    _score, intent = match
    tool_id = str(intent.get("toolId") or intent.get("tool_id") or "").strip()
    if not tool_id:
        return None
    route_path = normalize_execution_route_path(
        intent.get("routePath")
        or intent.get("route_path")
        or manifest.get("entryPath")
        or manifest.get("routePath")
        or ""
    )
    module_code = str(manifest.get("moduleCode") or manifest.get("module_code") or "").strip() or None
    required_fields = [
        str(item or "").strip()
        for item in as_manifest_list(intent.get("requiredFields") or intent.get("required_fields"))
        if str(item or "").strip()
    ]
    default_params = dict(intent.get("defaultParams") or {})
    missing_fields = [field for field in required_fields if field not in default_params]
    return {
        "toolId": tool_id,
        "toolLabel": str(intent.get("toolLabel") or intent.get("label") or tool_id).strip(),
        "mode": "collect" if missing_fields else "ready",
        "summary": str(intent.get("summary") or intent.get("label") or "准备执行查询。").strip(),
        "targetRoutePath": route_path if route_path != "/" else None,
        "targetModuleCode": module_code,
        "confirmationRequired": bool(intent.get("confirmationRequired")) is True,
        "canExecute": not missing_fields,
        "autoExecute": bool(intent.get("autoExecute")) and not missing_fields,
        "confirmText": str(intent.get("confirmText") or "确认执行").strip(),
        "collectedParams": default_params,
        "missingFields": missing_fields,
    }
