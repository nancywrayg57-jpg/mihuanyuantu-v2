from __future__ import annotations

from typing import Any


_PROMPT_SCALAR_TYPES = (str, int, float, bool)
_DEFAULT_POLICY_KEYS: tuple[str, ...] = (
    "auth",
    "readScope",
    "writeGuard",
    "importantOptionalFieldRule",
    "toolAvailabilityRule",
    "blockedIntentRule",
    "frontendTokenRule",
)
_PROMPT_FIELD_DETAIL_LEVELS = {"full", "compact"}


def compact_prompt_value(value: Any, *, max_items: int = 8) -> Any:
    if value is None or isinstance(value, _PROMPT_SCALAR_TYPES):
        return value
    if isinstance(value, list):
        if all(item is None or isinstance(item, _PROMPT_SCALAR_TYPES) for item in value):
            return [item for item in value[:max_items]]
        return None
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for key, nested_value in value.items():
            nested_compact = compact_prompt_value(nested_value, max_items=max_items)
            if nested_compact is None:
                continue
            compacted[str(key)] = nested_compact
        return compacted or None
    return None


def build_prompt_field_catalog(
    params: list[dict[str, Any]] | None,
    *,
    max_fields: int = 16,
    detail_level: str = "full",
) -> list[dict[str, Any]]:
    normalized_detail_level = str(detail_level or "full").strip().lower()
    if normalized_detail_level not in _PROMPT_FIELD_DETAIL_LEVELS:
        normalized_detail_level = "full"
    field_catalog: list[dict[str, Any]] = []
    for field in params or []:
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "").strip()
        if not key:
            continue
        item = {
            "key": key,
            "label": str(field.get("label") or key).strip() or key,
            "type": str(field.get("type") or "").strip(),
            "required": field.get("required") is True,
            "description": str(field.get("description") or "").strip(),
        }
        importance = str(field.get("importance") or "").strip().lower()
        if importance:
            item["importance"] = importance
        downstream_effects = [
            str(effect).strip()
            for effect in (field.get("downstreamEffects") or [])
            if str(effect).strip()
        ][:8]
        if downstream_effects:
            item["downstreamEffects"] = downstream_effects
        follow_up_hint = str(field.get("followUpHint") or "").strip()
        if follow_up_hint:
            item["followUpHint"] = follow_up_hint
        required_when = field.get("requiredWhen")
        if isinstance(required_when, dict):
            dependency_key = str(required_when.get("key") or "").strip()
            if dependency_key:
                dependency: dict[str, Any] = {"key": dependency_key}
                if "equals" in required_when:
                    dependency["equals"] = required_when.get("equals")
                dependency_values = (
                    list(required_when.get("in") or [])
                    if isinstance(required_when.get("in"), list)
                    else []
                )
                if dependency_values:
                    dependency["in"] = dependency_values[:8]
                dependency_description = str(required_when.get("description") or "").strip()
                if dependency_description:
                    dependency["description"] = dependency_description
                item["requiredWhen"] = dependency
        if normalized_detail_level == "full":
            examples = [
                str(example).strip()
                for example in (field.get("examples") or [])
                if str(example).strip()
            ][:3]
            if examples:
                item["examples"] = examples
            enum_options = [
                {
                    "value": str(option.get("value") or "").strip(),
                    "label": str(option.get("label") or option.get("value") or "").strip(),
                }
                for option in (field.get("enumOptions") or [])
                if isinstance(option, dict) and str(option.get("value") or "").strip()
            ][:8]
            if enum_options:
                item["enumOptions"] = enum_options
            elif isinstance(field.get("enumValues"), list):
                enum_values = [
                    str(option).strip()
                    for option in field.get("enumValues") or []
                    if str(option).strip()
                ][:8]
                if enum_values:
                    item["enumValues"] = enum_values
        field_catalog.append(item)
        if len(field_catalog) >= max_fields:
            break
    return field_catalog


def build_prompt_preferred_tool_ids(
    *,
    current_role_profile: dict[str, Any] | None = None,
    capability_manifest: dict[str, Any] | None = None,
    prior_action: dict[str, Any] | None = None,
) -> list[str]:
    preferred_ids: list[str] = []
    prior_tool_id = str((prior_action or {}).get("toolId") or "").strip()
    if prior_tool_id:
        preferred_ids.append(prior_tool_id)

    manifest = capability_manifest if isinstance(capability_manifest, dict) else {}
    role_profile = current_role_profile if isinstance(current_role_profile, dict) else {}
    for source in (
        list(manifest.get("recommendedToolIds") or []),
        list(manifest.get("plannedToolIds") or [])[:8],
        list(role_profile.get("availableToolIds") or [])[:8],
    ):
        for item in source:
            tool_id = str(item or "").strip()
            if tool_id:
                preferred_ids.append(tool_id)

    deduped_ids: list[str] = []
    seen_ids: set[str] = set()
    for tool_id in preferred_ids:
        if tool_id in seen_ids:
            continue
        seen_ids.add(tool_id)
        deduped_ids.append(tool_id)
    return deduped_ids


def rank_prompt_tool_catalog(
    tool_catalog: list[dict[str, Any]] | None,
    *,
    preferred_tool_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    normalized_tools = [dict(item) for item in (tool_catalog or []) if isinstance(item, dict)]
    focus_index = {
        str(tool_id).strip(): index
        for index, tool_id in enumerate(preferred_tool_ids or [])
        if str(tool_id).strip()
    }

    def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int, int]:
        index, tool = item
        tool_id = str(tool.get("id") or "").strip()
        focus_rank = focus_index.get(tool_id)
        return (
            0 if focus_rank is not None else 1,
            focus_rank if focus_rank is not None else 9999,
            index,
        )

    ranked = sorted(enumerate(normalized_tools), key=sort_key)
    return [tool for _index, tool in ranked]


def build_prompt_tool_catalog(
    tool_catalog: list[dict[str, Any]] | None,
    *,
    max_tools: int = 24,
    only_available: bool = True,
    only_active: bool = True,
    include_internal_contract: bool = True,
    include_params: bool = True,
    field_detail_level: str = "full",
    preferred_tool_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    prompt_tools: list[dict[str, Any]] = []
    for tool in rank_prompt_tool_catalog(tool_catalog, preferred_tool_ids=preferred_tool_ids):
        if not isinstance(tool, dict):
            continue
        tool_id = str(tool.get("id") or "").strip()
        if not tool_id:
            continue
        if only_available and tool.get("available") is False:
            continue
        if only_active and str(tool.get("status") or "active").strip().lower() != "active":
            continue
        tool_type = str(tool.get("toolType") or "").strip() or (
            "mutation" if tool.get("confirmationRequired") is True else "query"
        )
        item = {
            "id": tool_id,
            "label": str(tool.get("label") or tool_id).strip() or tool_id,
            "summary": str(tool.get("summary") or "").strip(),
            "toolType": tool_type,
            "resource": str(tool.get("resource") or "").strip(),
            "confirmationRequired": tool.get("confirmationRequired") is True,
        }
        if include_params:
            item["params"] = build_prompt_field_catalog(
                list(tool.get("params") or []),
                detail_level=field_detail_level,
            )
        if include_internal_contract and isinstance(tool.get("internalContract"), dict):
            internal_contract = tool["internalContract"]
            contract_payload = {
                "paramSource": str(internal_contract.get("paramSource") or "").strip(),
                "requestModel": str(internal_contract.get("requestModel") or "").strip(),
                "requestModelModule": str(internal_contract.get("requestModelModule") or "").strip(),
            }
            contract_payload = {key: value for key, value in contract_payload.items() if value}
            if contract_payload:
                item["internalContract"] = contract_payload
        prompt_tools.append(item)
        if len(prompt_tools) >= max_tools:
            break
    return prompt_tools


def build_prompt_blocked_intent_catalog(
    blocked_catalog: list[dict[str, Any]] | None,
    *,
    max_items: int = 8,
) -> list[dict[str, Any]]:
    prompt_items: list[dict[str, Any]] = []
    for item in blocked_catalog or []:
        if not isinstance(item, dict):
            continue
        intent_id = str(item.get("id") or "").strip()
        if not intent_id:
            continue
        payload = {
            "id": intent_id,
            "label": str(item.get("label") or intent_id).strip() or intent_id,
            "summary": str(item.get("summary") or "").strip(),
            "reason": str(item.get("reason") or "").strip(),
            "fallbackToolIds": [
                str(tool_id).strip()
                for tool_id in (item.get("availableFallbackToolIds") or item.get("fallbackToolIds") or [])
                if str(tool_id).strip()
            ][:8],
        }
        prompt_items.append(payload)
        if len(prompt_items) >= max_items:
            break
    return prompt_items


def build_prompt_operation_policy(
    operation_policy: dict[str, Any] | None,
    *,
    allowed_keys: tuple[str, ...] = _DEFAULT_POLICY_KEYS,
) -> dict[str, Any]:
    if not isinstance(operation_policy, dict):
        return {}
    payload: dict[str, Any] = {}
    for key in allowed_keys:
        value = str(operation_policy.get(key) or "").strip()
        if value:
            payload[key] = value
    return payload


def build_generic_prompt_context(
    *,
    module_code: str,
    module_name: str,
    route_path: str,
    context_data: dict[str, Any] | None,
    tool_catalog_max_tools: int = 24,
    tool_catalog_include_internal_contract: bool = True,
    tool_catalog_include_params: bool = True,
    tool_catalog_field_detail_level: str = "full",
    tool_catalog_preferred_ids: list[str] | None = None,
) -> dict[str, Any]:
    source = context_data if isinstance(context_data, dict) else {}
    payload: dict[str, Any] = {
        "moduleCode": str(module_code or "").strip(),
        "moduleName": str(module_name or module_code or "").strip(),
        "routePath": str(route_path or "/").strip() or "/",
    }

    for key in ("scope", "query", "currentRoleProfile"):
        compact_value = compact_prompt_value(source.get(key))
        if compact_value:
            payload[key] = compact_value

    current_resource_keys = (
        "currentResource",
        "currentWorkspace",
        "currentSession",
    )
    for key in current_resource_keys:
        compact_value = compact_prompt_value(source.get(key))
        if compact_value:
            payload[key] = compact_value

    tool_catalog = build_prompt_tool_catalog(
        list(source.get("toolCatalog") or []),
        max_tools=tool_catalog_max_tools,
        include_internal_contract=tool_catalog_include_internal_contract,
        include_params=tool_catalog_include_params,
        field_detail_level=tool_catalog_field_detail_level,
        preferred_tool_ids=tool_catalog_preferred_ids,
    )
    if tool_catalog:
        payload["toolCatalog"] = tool_catalog

    blocked_intents = build_prompt_blocked_intent_catalog(list(source.get("blockedIntentCatalog") or []))
    operation_policy = build_prompt_operation_policy(
        source.get("operationPolicy") if isinstance(source.get("operationPolicy"), dict) else None
    )
    if blocked_intents:
        payload["blockedIntentCatalog"] = blocked_intents
    if operation_policy:
        payload["operationPolicy"] = operation_policy

    capability_manifest = source.get("capabilityManifest")
    if isinstance(capability_manifest, dict):
        capability_summary = {}
        for key in ("availableToolCount", "blockedToolCount", "recommendedToolIds", "plannedToolIds"):
            compact_value = compact_prompt_value(capability_manifest.get(key))
            if compact_value:
                capability_summary[key] = compact_value
        if capability_summary:
            payload["capabilitySummary"] = capability_summary

    return payload
