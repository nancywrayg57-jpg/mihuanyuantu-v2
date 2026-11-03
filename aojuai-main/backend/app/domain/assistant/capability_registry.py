from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssistantCapabilityProviderSpec:
    """Module capability provider registered with the assistant foundation."""

    module_code: str
    scope_rules: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    tool_definitions: list[dict[str, Any]] = field(default_factory=list)
    toolset_module_code: str | None = None
    role_profiles: list[dict[str, Any]] = field(default_factory=list)
    skill_packs: list[dict[str, Any]] = field(default_factory=list)
    blocked_intents: list[dict[str, Any]] = field(default_factory=list)
    tool_lifecycle: list[dict[str, Any]] = field(default_factory=list)
    resource_labels: dict[str, str] = field(default_factory=dict)
    portal_scope_ids: frozenset[str] = field(default_factory=frozenset)


_ASSISTANT_CAPABILITY_PROVIDERS: dict[str, AssistantCapabilityProviderSpec] = {}


def register_assistant_capability_provider(
    provider: AssistantCapabilityProviderSpec,
) -> AssistantCapabilityProviderSpec:
    module_code = str(getattr(provider, "module_code", "") or "").strip()
    if not module_code:
        raise ValueError("assistant capability provider requires non-empty module_code")
    _ASSISTANT_CAPABILITY_PROVIDERS[module_code] = provider
    return provider


def get_assistant_capability_provider(module_code: str) -> AssistantCapabilityProviderSpec | None:
    return _ASSISTANT_CAPABILITY_PROVIDERS.get(str(module_code or "").strip())


def list_assistant_capability_providers() -> list[AssistantCapabilityProviderSpec]:
    return [provider for _, provider in sorted(_ASSISTANT_CAPABILITY_PROVIDERS.items(), key=lambda item: item[0])]


def _normalize_route_path(value: Any) -> str:
    route = str(value or "/").strip() or "/"
    if not route.startswith("/"):
        route = f"/{route.lstrip('/')}"
    return route.rstrip("/") or "/"


def resolve_capability_route_scope(
    provider: AssistantCapabilityProviderSpec,
    route: str,
) -> dict[str, Any]:
    normalized = _normalize_route_path(route)
    if not provider.scope_rules:
        return {
            "id": "default",
            "label": "default",
            "routePrefix": "/",
        }
    for prefix, payload in provider.scope_rules:
        normalized_prefix = _normalize_route_path(prefix)
        if normalized == normalized_prefix or normalized.startswith(f"{normalized_prefix}/"):
            data = deepcopy(payload)
            data["routePrefix"] = normalized_prefix
            return data
    fallback_prefix, fallback_payload = provider.scope_rules[0]
    fallback = deepcopy(fallback_payload)
    fallback["routePrefix"] = _normalize_route_path(fallback_prefix)
    return fallback


def build_provider_tool_definitions(
    provider: AssistantCapabilityProviderSpec,
) -> list[dict[str, Any]]:
    if provider.tool_definitions:
        return [deepcopy(item) for item in provider.tool_definitions]

    toolset_module_code = str(getattr(provider, "toolset_module_code", "") or "").strip()
    if not toolset_module_code:
        return []

    from app.domain.assistant.toolset_registry import (
        build_registered_tool_definitions,
        get_assistant_module_toolset,
    )

    toolset = get_assistant_module_toolset(toolset_module_code)
    if toolset is None:
        return []
    return [dict(item) for item in build_registered_tool_definitions(toolset)]


def build_scoped_tool_catalog(
    provider: AssistantCapabilityProviderSpec,
    permission_codes: set[str],
    route: str,
) -> list[dict[str, Any]]:
    normalized_permissions = {str(item) for item in permission_codes if str(item).strip()}
    has_wildcard = "*:*:*" in normalized_permissions or "*.*.*" in normalized_permissions
    scope = resolve_capability_route_scope(provider, route)
    scope_id = str(scope.get("id") or "default").strip() or "default"

    items: list[dict[str, Any]] = []
    for definition in build_provider_tool_definitions(provider):
        item = deepcopy(definition)
        required_permissions = [str(code).strip() for code in item.get("requiredPermissions") or [] if str(code).strip()]
        scope_ids = [str(code).strip() for code in item.get("scopeIds") or [] if str(code).strip()]
        scope_allowed = scope_id in scope_ids if scope_ids else True
        permission_allowed = True
        if required_permissions:
            permission_allowed = scope_id in provider.portal_scope_ids or has_wildcard or bool(
                set(required_permissions) & normalized_permissions
            )
        item["available"] = bool(scope_allowed and permission_allowed and item.get("status") == "active")
        item["availabilityReason"] = None
        if not scope_allowed:
            item["availabilityReason"] = f"当前路由归属 {scope_id}，不在该工具适用范围"
        elif not permission_allowed:
            item["availabilityReason"] = "当前账号缺少所需权限"
        elif item.get("status") != "active":
            item["availabilityReason"] = "该能力已进入规划，但执行链路尚未完成"
        items.append(item)
    return items


def resolve_provider_role_profile(
    provider: AssistantCapabilityProviderSpec,
    scope_id: str,
    tool_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    available_tool_ids = {str(item.get("id") or "").strip() for item in tool_catalog if item.get("available")}
    tool_map = {str(item.get("id") or "").strip(): item for item in tool_catalog if str(item.get("id") or "").strip()}
    base = next((deepcopy(item) for item in provider.role_profiles if item.get("id") == scope_id), None)
    if base is None:
        return {
            "id": scope_id,
            "label": scope_id,
            "actorKind": scope_id,
            "primaryGoals": [],
            "aiCapabilities": [],
            "preferredToolIds": [],
            "availableToolIds": [],
            "blockedToolIds": [],
            "starterFlows": [],
        }

    preferred_tool_ids = [str(item).strip() for item in base.get("preferredToolIds") or [] if str(item).strip()]
    base["availableToolIds"] = [item for item in preferred_tool_ids if item in available_tool_ids]
    base["blockedToolIds"] = [item for item in preferred_tool_ids if item not in available_tool_ids]
    base["availableToolLabels"] = [
        str(tool_map[item].get("label") or item)
        for item in base["availableToolIds"]
        if item in tool_map
    ]
    return base


def build_provider_role_matrix(
    provider: AssistantCapabilityProviderSpec,
    tool_catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        resolve_provider_role_profile(provider, str(item.get("id") or ""), tool_catalog)
        for item in provider.role_profiles
        if str(item.get("id") or "").strip()
    ]


def build_provider_skill_pack_catalog(
    provider: AssistantCapabilityProviderSpec,
    scope_id: str,
    tool_catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    available_tool_ids = {str(item.get("id") or "").strip() for item in tool_catalog if item.get("available")}
    skill_packs: list[dict[str, Any]] = []
    for item in provider.skill_packs:
        if scope_id not in [str(value).strip() for value in item.get("scopeIds") or [] if str(value).strip()]:
            continue
        preferred_tool_ids = [str(tool_id).strip() for tool_id in item.get("preferredToolIds") or [] if str(tool_id).strip()]
        available_skill_tool_ids = [tool_id for tool_id in preferred_tool_ids if tool_id in available_tool_ids]
        blocked_skill_tool_ids = [tool_id for tool_id in preferred_tool_ids if tool_id not in available_tool_ids]
        skill_packs.append(
            {
                "id": str(item.get("id") or "").strip(),
                "label": str(item.get("label") or "").strip(),
                "description": str(item.get("description") or "").strip(),
                "triggerHint": str(item.get("triggerHint") or "").strip(),
                "scopeIds": [str(value).strip() for value in item.get("scopeIds") or [] if str(value).strip()],
                "preferredToolIds": preferred_tool_ids,
                "availableToolIds": available_skill_tool_ids,
                "blockedToolIds": blocked_skill_tool_ids,
                "available": True if not preferred_tool_ids else bool(available_skill_tool_ids),
            }
        )
    return sorted(
        skill_packs,
        key=lambda item: (
            0 if item.get("available") else 1,
            str(item.get("label") or item.get("id") or ""),
        ),
    )


def build_provider_blocked_intent_catalog(
    provider: AssistantCapabilityProviderSpec,
    scope_id: str,
    tool_catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    available_tool_ids = {str(item.get("id") or "").strip() for item in tool_catalog if item.get("available")}
    items: list[dict[str, Any]] = []
    for item in provider.blocked_intents:
        if scope_id not in [str(value).strip() for value in item.get("scopeIds") or [] if str(value).strip()]:
            continue
        fallback_tool_ids = [
            str(tool_id).strip()
            for tool_id in (item.get("fallbackToolIdsByScope", {}).get(scope_id) or [])
            if str(tool_id).strip()
        ]
        available_fallback_tool_ids = [tool_id for tool_id in fallback_tool_ids if tool_id in available_tool_ids]
        items.append(
            {
                "id": str(item.get("id") or "").strip(),
                "label": str(item.get("label") or "").strip(),
                "scopeIds": [str(value).strip() for value in item.get("scopeIds") or [] if str(value).strip()],
                "skillPackId": str(item.get("skillPackByScope", {}).get(scope_id) or "").strip() or None,
                "summary": str(item.get("summaryByScope", {}).get(scope_id) or "").strip(),
                "reason": str(item.get("reasonByScope", {}).get(scope_id) or "").strip(),
                "triggerPatterns": list(item.get("triggerPatterns") or []),
                "fallbackToolIds": fallback_tool_ids,
                "availableFallbackToolIds": available_fallback_tool_ids,
                "suggestedReplies": [
                    str(reply).strip()
                    for reply in (item.get("suggestedRepliesByScope", {}).get(scope_id) or [])
                    if str(reply).strip()
                ],
            }
        )
    return items


def build_provider_capability_manifest(
    provider: AssistantCapabilityProviderSpec,
    scope_id: str,
    tool_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    role_profile = resolve_provider_role_profile(provider, scope_id, tool_catalog)
    skill_packs = build_provider_skill_pack_catalog(provider, scope_id, tool_catalog)
    preferred_tool_ids = {str(item).strip() for item in role_profile.get("preferredToolIds") or [] if str(item).strip()}

    resource_groups: dict[str, dict[str, Any]] = {}
    tool_type_groups: dict[str, dict[str, Any]] = {}
    available_tool_count = 0
    blocked_tool_count = 0

    for item in tool_catalog:
        if item.get("status") != "active":
            continue
        tool_id = str(item.get("id") or "").strip()
        if not tool_id:
            continue
        resource_id = str(item.get("resource") or "misc").strip() or "misc"
        tool_type = str(item.get("toolType") or "query").strip() or "query"
        available = bool(item.get("available"))

        if available:
            available_tool_count += 1
        else:
            blocked_tool_count += 1

        tool_summary = {
            "toolId": tool_id,
            "label": str(item.get("label") or tool_id),
            "summary": str(item.get("summary") or ""),
            "toolType": tool_type,
            "accessMode": str(item.get("accessMode") or "read"),
            "available": available,
            "preferred": tool_id in preferred_tool_ids,
            "requiredPermissions": list(item.get("requiredPermissions") or []),
            "availabilityReason": item.get("availabilityReason"),
            "paramKeys": [str(field.get("key")) for field in item.get("params") or [] if str(field.get("key") or "").strip()],
        }

        resource_group = resource_groups.setdefault(
            resource_id,
            {
                "id": resource_id,
                "label": provider.resource_labels.get(resource_id, resource_id),
                "toolCount": 0,
                "availableToolCount": 0,
                "preferredToolIds": [],
                "tools": [],
            },
        )
        resource_group["toolCount"] += 1
        if available:
            resource_group["availableToolCount"] += 1
        if tool_summary["preferred"]:
            resource_group["preferredToolIds"].append(tool_id)
        resource_group["tools"].append(tool_summary)

        tool_type_group = tool_type_groups.setdefault(
            tool_type,
            {
                "id": tool_type,
                "label": next(
                    (
                        str(entry.get("label") or entry.get("id") or "").strip()
                        for entry in provider.tool_lifecycle
                        if str(entry.get("id") or "").strip() == tool_type
                    ),
                    tool_type,
                ),
                "toolCount": 0,
                "availableToolCount": 0,
                "tools": [],
            },
        )
        tool_type_group["toolCount"] += 1
        if available:
            tool_type_group["availableToolCount"] += 1
        tool_type_group["tools"].append(tool_summary)

    def _sort_tools(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            values,
            key=lambda item: (
                0 if item.get("preferred") else 1,
                0 if item.get("available") else 1,
                str(item.get("label") or item.get("toolId") or ""),
            ),
        )

    resource_group_list = sorted(
        resource_groups.values(),
        key=lambda item: (-int(item.get("availableToolCount") or 0), str(item.get("label") or item.get("id") or "")),
    )
    for item in resource_group_list:
        item["tools"] = _sort_tools(list(item.get("tools") or []))
        item["preferredToolIds"] = sorted({str(tool_id).strip() for tool_id in item.get("preferredToolIds") or [] if str(tool_id).strip()})

    tool_type_group_list: list[dict[str, Any]] = []
    seen_lifecycle_ids: set[str] = set()
    for lifecycle in provider.tool_lifecycle:
        lifecycle_id = str(lifecycle.get("id") or "").strip()
        if not lifecycle_id:
            continue
        seen_lifecycle_ids.add(lifecycle_id)
        group = tool_type_groups.get(lifecycle_id)
        if not group:
            continue
        group["tools"] = _sort_tools(list(group.get("tools") or []))
        tool_type_group_list.append(group)
    for lifecycle_id, group in sorted(tool_type_groups.items(), key=lambda item: item[0]):
        if lifecycle_id in seen_lifecycle_ids:
            continue
        group["tools"] = _sort_tools(list(group.get("tools") or []))
        tool_type_group_list.append(group)

    resource_summary = [
        {
            "resource": str(item.get("id") or ""),
            "label": str(item.get("label") or ""),
            "toolCount": int(item.get("toolCount") or 0),
            "availableToolCount": int(item.get("availableToolCount") or 0),
            "preferredToolIds": list(item.get("preferredToolIds") or []),
        }
        for item in resource_group_list
    ]
    lifecycle_summary = [
        {
            "mode": str(item.get("id") or ""),
            "label": str(item.get("label") or ""),
            "toolCount": int(item.get("toolCount") or 0),
            "availableToolCount": int(item.get("availableToolCount") or 0),
        }
        for item in tool_type_group_list
    ]

    available_ranked_tool_ids = {
        str(tool.get("toolId") or "")
        for group in resource_group_list
        for tool in group.get("tools") or []
        if tool.get("available")
    }
    starter_flows = []
    for item in role_profile.get("starterFlows") or []:
        first_tool_id = str(item.get("firstToolId") or "").strip()
        starter_flows.append(
            {
                **deepcopy(item),
                "firstToolAvailable": first_tool_id in available_ranked_tool_ids,
            }
        )

    provider_tool_definitions = build_provider_tool_definitions(provider)
    planned_tool_ids = sorted(
        str(item.get("id") or "").strip()
        for item in provider_tool_definitions
        if str(item.get("id") or "").strip()
        and item.get("status") != "active"
        and scope_id in [str(value).strip() for value in item.get("scopeIds") or [] if str(value).strip()]
    )

    return {
        "providerModuleCode": provider.module_code,
        "compositionMode": "assistant_internal_registry",
        "scopeId": scope_id,
        "roleLabel": str(role_profile.get("label") or scope_id),
        "availableToolCount": available_tool_count,
        "blockedToolCount": blocked_tool_count,
        "skillCount": len(skill_packs),
        "availableSkillCount": sum(1 for item in skill_packs if item.get("available")),
        "preferredToolIds": list(role_profile.get("availableToolIds") or []),
        "recommendedToolIds": list(role_profile.get("availableToolIds") or [])[:8],
        "skillPacks": skill_packs,
        "resourceSummary": resource_summary,
        "lifecycleSummary": lifecycle_summary,
        "resourceGroups": resource_group_list,
        "toolTypeGroups": tool_type_group_list,
        "starterFlows": starter_flows,
        "plannedToolIds": planned_tool_ids,
    }


def build_provider_capability_source(
    provider: AssistantCapabilityProviderSpec,
    permission_codes: set[str],
    route: str,
) -> dict[str, Any]:
    scope = resolve_capability_route_scope(provider, route)
    scope_id = str(scope.get("id") or "default").strip() or "default"
    tool_catalog = build_scoped_tool_catalog(provider, permission_codes, route)
    return {
        "providerModuleCode": provider.module_code,
        "compositionMode": "assistant_internal_registry",
        "scope": scope,
        "currentRoleProfile": resolve_provider_role_profile(provider, scope_id, tool_catalog),
        "roleProfiles": build_provider_role_matrix(provider, tool_catalog),
        "skillPacks": build_provider_skill_pack_catalog(provider, scope_id, tool_catalog),
        "blockedIntentCatalog": build_provider_blocked_intent_catalog(provider, scope_id, tool_catalog),
        "toolCatalog": tool_catalog,
        "capabilityManifest": build_provider_capability_manifest(provider, scope_id, tool_catalog),
    }
