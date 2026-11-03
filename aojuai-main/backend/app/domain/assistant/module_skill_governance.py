"""AOJU Backend - Assistant Module Skill Governance"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.assistant.action_protocol import normalize_assistant_action
from app.domain.assistant.adapters import AdapterRegistry


def _normalize_rank(value: Any, *, default: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    return max(0, min(normalized, 999))


def _normalize_catalog_skill(item: Any, *, default_rank: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    skill_id = str(item.get("skillId") or item.get("skill_id") or item.get("id") or "").strip()
    if not skill_id:
        return None
    return {
        "skillId": skill_id,
        "label": str(item.get("label") or skill_id).strip() or skill_id,
        "description": str(item.get("description") or "").strip(),
        "scopeIds": [str(scope_id).strip() for scope_id in item.get("scopeIds", []) or [] if str(scope_id).strip()],
        "defaultRank": _normalize_rank(item.get("defaultRank", item.get("rank", item.get("priority"))), default=default_rank),
    }


def build_assistant_module_skill_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for adapter in AdapterRegistry.list_all():
        normalized_skills: list[dict[str, Any]] = []
        seen_skill_ids: set[str] = set()
        for index, item in enumerate(adapter.get_governance_skill_catalog(), start=1):
            normalized = _normalize_catalog_skill(item, default_rank=index)
            if not normalized:
                continue
            skill_id = str(normalized["skillId"])
            if skill_id in seen_skill_ids:
                continue
            seen_skill_ids.add(skill_id)
            normalized_skills.append(normalized)
        if not normalized_skills:
            continue
        catalog.append(
            {
                "moduleCode": str(adapter.module_code or "").strip(),
                "moduleName": str(adapter.module_name or adapter.module_code or "").strip(),
                "skills": sorted(
                    normalized_skills,
                    key=lambda item: (int(item.get("defaultRank") or 0), str(item.get("label") or item.get("skillId") or "")),
                ),
            }
        )
    return sorted(
        catalog,
        key=lambda item: (
            0 if str(item.get("moduleCode") or "").strip() == "default" else 1,
            str(item.get("moduleName") or item.get("moduleCode") or ""),
        ),
    )


def build_default_module_skill_governance() -> dict[str, Any]:
    return {
        "modules": [
            {
                "moduleCode": str(module.get("moduleCode") or "").strip(),
                "skillRules": [
                    {
                        "skillId": str(skill.get("skillId") or "").strip(),
                        "enabled": True,
                        "rank": int(skill.get("defaultRank") or index),
                    }
                    for index, skill in enumerate(module.get("skills", []) or [], start=1)
                    if str(skill.get("skillId") or "").strip()
                ],
            }
            for module in build_assistant_module_skill_catalog()
            if str(module.get("moduleCode") or "").strip()
        ]
    }


def _resolve_module_rules(
    *,
    module_code: str,
    capability_config: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    governance_source = capability_config.get("moduleSkillGovernance") if isinstance(capability_config, dict) else None
    effective_governance = merge_module_skill_governance(build_default_module_skill_governance(), governance_source)
    for module in effective_governance.get("modules", []) if isinstance(effective_governance, dict) else []:
        if not isinstance(module, dict):
            continue
        if str(module.get("moduleCode") or "").strip() != str(module_code or "").strip():
            continue
        raw_rules = module.get("skillRules", []) if isinstance(module.get("skillRules"), list) else []
        return {
            str(rule.get("skillId") or "").strip(): rule
            for rule in raw_rules
            if isinstance(rule, dict) and str(rule.get("skillId") or "").strip()
        }
    return {}


def _collect_skill_tool_ids(skill_pack: dict[str, Any]) -> list[str]:
    collected: list[str] = []
    seen_tool_ids: set[str] = set()
    for field_name in ("availableToolIds", "preferredToolIds"):
        for item in skill_pack.get(field_name, []) or []:
            tool_id = str(item).strip()
            if not tool_id or tool_id in seen_tool_ids:
                continue
            seen_tool_ids.add(tool_id)
            collected.append(tool_id)
    return collected


def _govern_skill_packs(
    *,
    module_code: str,
    skill_packs: list[dict[str, Any]],
    capability_config: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    module_rules = _resolve_module_rules(module_code=module_code, capability_config=capability_config)
    if not module_rules:
        return [deepcopy(item) for item in skill_packs if isinstance(item, dict)]

    governed_items: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(skill_packs, start=1):
        if not isinstance(item, dict):
            continue
        skill_id = str(item.get("id") or "").strip()
        if not skill_id:
            continue
        rule = module_rules.get(skill_id)
        if isinstance(rule, dict) and rule.get("enabled") is False:
            continue
        governed_items.append((_normalize_rank(rule.get("rank") if isinstance(rule, dict) else None, default=index), index, deepcopy(item)))

    governed_items.sort(key=lambda item: (item[0], item[1], str(item[2].get("label") or item[2].get("id") or "")))
    return [item[2] for item in governed_items]


def normalize_module_skill_governance(raw: Any) -> dict[str, Any]:
    modules_raw = raw.get("modules") if isinstance(raw, dict) else []
    normalized_modules: list[dict[str, Any]] = []
    for raw_module in modules_raw if isinstance(modules_raw, list) else []:
        if not isinstance(raw_module, dict):
            continue
        module_code = str(raw_module.get("moduleCode") or raw_module.get("module_code") or "").strip()
        if not module_code:
            continue
        raw_rules = raw_module.get("skillRules") or raw_module.get("skill_rules") or []
        normalized_rules: list[dict[str, Any]] = []
        seen_skill_ids: set[str] = set()
        for index, raw_rule in enumerate(raw_rules if isinstance(raw_rules, list) else [], start=1):
            if not isinstance(raw_rule, dict):
                continue
            skill_id = str(raw_rule.get("skillId") or raw_rule.get("skill_id") or raw_rule.get("id") or "").strip()
            if not skill_id or skill_id in seen_skill_ids:
                continue
            seen_skill_ids.add(skill_id)
            normalized_rules.append(
                {
                    "skillId": skill_id,
                    "enabled": raw_rule.get("enabled") is not False,
                    "rank": _normalize_rank(raw_rule.get("rank", raw_rule.get("priority")), default=index),
                }
            )
        normalized_modules.append(
            {
                "moduleCode": module_code,
                "skillRules": sorted(normalized_rules, key=lambda item: (int(item.get("rank") or 0), str(item.get("skillId") or ""))),
            }
        )
    return {"modules": normalized_modules}


def merge_module_skill_governance(base: Any, override: Any) -> dict[str, Any]:
    base_modules = normalize_module_skill_governance(base).get("modules", [])
    override_modules = normalize_module_skill_governance(override).get("modules", [])
    override_map = {
        str(module.get("moduleCode") or "").strip(): module
        for module in override_modules
        if str(module.get("moduleCode") or "").strip()
    }
    merged_modules: list[dict[str, Any]] = []

    for base_module in base_modules:
        module_code = str(base_module.get("moduleCode") or "").strip()
        if not module_code:
            continue
        base_rules = base_module.get("skillRules", []) if isinstance(base_module.get("skillRules"), list) else []
        base_rule_map = {
            str(rule.get("skillId") or "").strip(): rule
            for rule in base_rules
            if str(rule.get("skillId") or "").strip()
        }
        override_rules = (
            override_map.get(module_code, {}).get("skillRules", [])
            if isinstance(override_map.get(module_code, {}).get("skillRules"), list)
            else []
        )
        override_rule_map = {
            str(rule.get("skillId") or "").strip(): rule
            for rule in override_rules
            if str(rule.get("skillId") or "").strip()
        }

        merged_rules: list[dict[str, Any]] = []
        for index, base_rule in enumerate(base_rules, start=1):
            skill_id = str(base_rule.get("skillId") or "").strip()
            if not skill_id:
                continue
            merged_rule = deepcopy(base_rule)
            override_rule = override_rule_map.get(skill_id)
            if isinstance(override_rule, dict):
                merged_rule["enabled"] = override_rule.get("enabled") is not False
                merged_rule["rank"] = _normalize_rank(override_rule.get("rank"), default=index)
            else:
                merged_rule["enabled"] = merged_rule.get("enabled") is not False
                merged_rule["rank"] = _normalize_rank(merged_rule.get("rank"), default=index)
            merged_rules.append(merged_rule)

        for extra_rule in override_rules:
            skill_id = str(extra_rule.get("skillId") or "").strip()
            if not skill_id or skill_id in base_rule_map:
                continue
            merged_rules.append(
                {
                    "skillId": skill_id,
                    "enabled": extra_rule.get("enabled") is not False,
                    "rank": _normalize_rank(extra_rule.get("rank"), default=len(merged_rules) + 1),
                }
            )

        merged_modules.append(
            {
                "moduleCode": module_code,
                "skillRules": sorted(merged_rules, key=lambda item: (int(item.get("rank") or 0), str(item.get("skillId") or ""))),
            }
        )

    base_module_codes = {str(module.get("moduleCode") or "").strip() for module in base_modules if str(module.get("moduleCode") or "").strip()}
    for extra_module in override_modules:
        module_code = str(extra_module.get("moduleCode") or "").strip()
        if not module_code or module_code in base_module_codes:
            continue
        merged_modules.append(deepcopy(extra_module))

    return {"modules": merged_modules}


def apply_module_skill_governance_to_context(
    *,
    module_code: str,
    context_data: dict[str, Any] | None,
    capability_config: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_context = dict(context_data or {}) if isinstance(context_data, dict) else {}
    skill_packs = normalized_context.get("skillPacks")
    if not isinstance(skill_packs, list) or not skill_packs:
        return normalized_context

    governed_skill_packs = _govern_skill_packs(
        module_code=module_code,
        skill_packs=[item for item in skill_packs if isinstance(item, dict)],
        capability_config=capability_config,
    )
    normalized_context["skillPacks"] = governed_skill_packs

    capability_manifest = normalized_context.get("capabilityManifest") if isinstance(normalized_context.get("capabilityManifest"), dict) else None
    if capability_manifest is not None:
        next_manifest = deepcopy(capability_manifest)
        next_manifest["skillPacks"] = deepcopy(governed_skill_packs)
        next_manifest["skillCount"] = len(governed_skill_packs)
        next_manifest["availableSkillCount"] = sum(1 for item in governed_skill_packs if bool(item.get("available", True)))
        normalized_context["capabilityManifest"] = next_manifest

    return normalized_context


def apply_module_skill_governance_to_action(
    *,
    module_code: str,
    action: dict[str, Any] | None,
    context_data: dict[str, Any] | None,
    capability_config: dict[str, Any] | None,
    builtin_tool_ids: set[str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    normalized_action = normalize_assistant_action(action)
    if not normalized_action:
        return None, None

    tool_id = str(normalized_action.get("toolId") or "").strip()
    if not tool_id:
        return None, None

    allowed_builtin_tool_ids = {str(item).strip() for item in (builtin_tool_ids or set()) if str(item).strip()}
    if tool_id in allowed_builtin_tool_ids:
        return normalized_action, None

    normalized_context = dict(context_data or {}) if isinstance(context_data, dict) else {}
    raw_tool_catalog = normalized_context.get("toolCatalog")
    tool_catalog_declared = isinstance(raw_tool_catalog, list)
    available_tool_ids = {
        str(item.get("id") or "").strip()
        for item in (raw_tool_catalog if isinstance(raw_tool_catalog, list) else [])
        if isinstance(item, dict) and bool(item.get("available")) and str(item.get("id") or "").strip()
    }
    if tool_catalog_declared and tool_id not in available_tool_ids:
        return None, "当前动作不在本页可用工具范围内。"

    raw_skill_packs = [
        item
        for item in (normalized_context.get("skillPacks", []) if isinstance(normalized_context.get("skillPacks"), list) else [])
        if isinstance(item, dict)
    ]
    if not raw_skill_packs:
        return normalized_action, None

    governed_skill_packs = _govern_skill_packs(module_code=module_code, skill_packs=raw_skill_packs, capability_config=capability_config)
    raw_skill_map = {str(item.get("id") or "").strip(): item for item in raw_skill_packs if str(item.get("id") or "").strip()}
    visible_skill_map = {str(item.get("id") or "").strip(): item for item in governed_skill_packs if str(item.get("id") or "").strip()}

    raw_tool_skill_map: dict[str, list[dict[str, Any]]] = {}
    visible_tool_skill_map: dict[str, list[dict[str, Any]]] = {}
    for collection, mapping in ((raw_skill_packs, raw_tool_skill_map), (governed_skill_packs, visible_tool_skill_map)):
        for skill_pack in collection:
            for related_tool_id in _collect_skill_tool_ids(skill_pack):
                mapping.setdefault(related_tool_id, []).append(skill_pack)

    explicit_skill_id = str(normalized_action.get("skillId") or "").strip()
    if explicit_skill_id:
        visible_skill_pack = visible_skill_map.get(explicit_skill_id)
        if visible_skill_pack and tool_id in _collect_skill_tool_ids(visible_skill_pack):
            normalized_action["skillLabel"] = (
                str(visible_skill_pack.get("label") or normalized_action.get("skillLabel") or "").strip() or None
            )
            return normalized_action, None

    visible_matches = visible_tool_skill_map.get(tool_id, [])
    if visible_matches:
        chosen_skill_pack = None
        if explicit_skill_id:
            chosen_skill_pack = next((item for item in visible_matches if str(item.get("id") or "").strip() == explicit_skill_id), None)
        if chosen_skill_pack is None:
            chosen_skill_pack = visible_matches[0]
        chosen_skill_id = str(chosen_skill_pack.get("id") or "").strip()
        normalized_action["skillId"] = chosen_skill_id or None
        normalized_action["skillLabel"] = (
            str(chosen_skill_pack.get("label") or normalized_action.get("skillLabel") or "").strip() or None
        )
        return normalized_action, None

    raw_matches = raw_tool_skill_map.get(tool_id, [])
    if raw_matches:
        return None, "当前动作对应的助手技能已被租户禁用。"

    if explicit_skill_id and explicit_skill_id in raw_skill_map and explicit_skill_id not in visible_skill_map:
        return None, "当前动作对应的助手技能已被租户禁用。"

    return normalized_action, None
