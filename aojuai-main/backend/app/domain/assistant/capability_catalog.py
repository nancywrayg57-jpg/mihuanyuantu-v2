"""AOJU Backend - Assistant Capability Catalog Helpers"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any


def build_generic_capability_manifest(
    *,
    scope_id: str,
    role_profile: dict[str, Any] | None,
    tool_catalog: list[dict[str, Any]] | None,
    skill_packs: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    normalized_role = role_profile if isinstance(role_profile, dict) else {}
    normalized_tools = [item for item in (tool_catalog or []) if isinstance(item, dict)]
    normalized_skills = [item for item in (skill_packs or []) if isinstance(item, dict)]

    preferred_tool_ids = {
        str(item).strip()
        for item in normalized_role.get("preferredToolIds", []) or []
        if str(item).strip()
    }
    available_tool_ids = {
        str(item.get("id") or "").strip()
        for item in normalized_tools
        if str(item.get("id") or "").strip() and bool(item.get("available"))
    }

    resource_groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "id": "",
            "label": "",
            "toolCount": 0,
            "availableToolCount": 0,
            "preferredToolIds": [],
        }
    )
    lifecycle_groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "mode": "",
            "label": "",
            "toolCount": 0,
            "availableToolCount": 0,
        }
    )

    available_tool_count = 0
    blocked_tool_count = 0

    for item in normalized_tools:
        tool_id = str(item.get("id") or "").strip()
        if not tool_id:
            continue
        resource_id = str(item.get("resource") or "misc").strip() or "misc"
        mode = str(item.get("mode") or item.get("toolType") or "read").strip() or "read"
        resource_label = str(item.get("resourceLabel") or resource_id).strip() or resource_id
        mode_label = str(item.get("modeLabel") or mode).strip() or mode
        available = bool(item.get("available"))

        if available:
            available_tool_count += 1
        else:
            blocked_tool_count += 1

        resource_group = resource_groups[resource_id]
        resource_group["id"] = resource_id
        resource_group["label"] = resource_label
        resource_group["toolCount"] += 1
        if available:
            resource_group["availableToolCount"] += 1
        if tool_id in preferred_tool_ids:
            resource_group["preferredToolIds"].append(tool_id)

        lifecycle_group = lifecycle_groups[mode]
        lifecycle_group["mode"] = mode
        lifecycle_group["label"] = mode_label
        lifecycle_group["toolCount"] += 1
        if available:
            lifecycle_group["availableToolCount"] += 1

    resource_summary = sorted(
        [
            {
                "resource": str(item.get("id") or "").strip(),
                "label": str(item.get("label") or item.get("id") or "").strip(),
                "toolCount": int(item.get("toolCount") or 0),
                "availableToolCount": int(item.get("availableToolCount") or 0),
                "preferredToolIds": sorted(
                    {
                        str(tool_id).strip()
                        for tool_id in item.get("preferredToolIds", []) or []
                        if str(tool_id).strip()
                    }
                ),
            }
            for item in resource_groups.values()
        ],
        key=lambda item: (-int(item["availableToolCount"]), str(item["label"] or item["resource"])),
    )
    lifecycle_summary = sorted(
        [
            {
                "mode": str(item.get("mode") or "").strip(),
                "label": str(item.get("label") or item.get("mode") or "").strip(),
                "toolCount": int(item.get("toolCount") or 0),
                "availableToolCount": int(item.get("availableToolCount") or 0),
            }
            for item in lifecycle_groups.values()
        ],
        key=lambda item: (-int(item["availableToolCount"]), str(item["label"] or item["mode"])),
    )

    recommended_tool_ids = [
        tool_id
        for tool_id in normalized_role.get("availableToolIds", []) or []
        if str(tool_id).strip() in available_tool_ids
    ]
    if not recommended_tool_ids:
        recommended_tool_ids = sorted(available_tool_ids)[:8]

    return {
        "scopeId": scope_id,
        "roleLabel": str(normalized_role.get("label") or scope_id).strip() or scope_id,
        "availableToolCount": available_tool_count,
        "blockedToolCount": blocked_tool_count,
        "skillCount": len(normalized_skills),
        "availableSkillCount": sum(1 for item in normalized_skills if bool(item.get("available", True))),
        "preferredToolIds": sorted(preferred_tool_ids),
        "recommendedToolIds": recommended_tool_ids[:8],
        "skillPacks": deepcopy(normalized_skills),
        "resourceSummary": resource_summary,
        "lifecycleSummary": lifecycle_summary,
    }


def build_generic_capability_source(
    *,
    module_code: str,
    scope_id: str,
    role_profile: dict[str, Any] | None,
    tool_catalog: list[dict[str, Any]] | None,
    skill_packs: list[dict[str, Any]] | None,
    operation_policy: dict[str, Any] | None = None,
    composition_mode: str = "assistant_generic_catalog",
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard capability source for lightweight module adapters."""
    normalized_role = deepcopy(role_profile) if isinstance(role_profile, dict) else {}
    normalized_tools = [deepcopy(item) for item in (tool_catalog or []) if isinstance(item, dict)]
    normalized_skills = [deepcopy(item) for item in (skill_packs or []) if isinstance(item, dict)]
    payload = {
        "providerModuleCode": str(module_code or "").strip(),
        "compositionMode": str(composition_mode or "").strip() or "assistant_generic_catalog",
        "currentRoleProfile": normalized_role,
        "skillPacks": normalized_skills,
        "toolCatalog": normalized_tools,
        "capabilityManifest": build_generic_capability_manifest(
            scope_id=scope_id,
            role_profile=normalized_role,
            tool_catalog=normalized_tools,
            skill_packs=normalized_skills,
        ),
        "operationPolicy": deepcopy(operation_policy) if isinstance(operation_policy, dict) else {},
    }
    if isinstance(extra_payload, dict) and extra_payload:
        payload.update(deepcopy(extra_payload))
    return payload
