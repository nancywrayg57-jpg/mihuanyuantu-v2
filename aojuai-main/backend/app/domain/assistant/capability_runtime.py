"""AOJU Backend - Assistant Capability Runtime"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.assistant.adapters.base import ActionResult

_DEFAULT_TIMEZONE = "Asia/Shanghai"

_ASSISTANT_BUILTIN_SKILLS: list[dict[str, Any]] = [
    {
        "id": "core.context_reader",
        "label": "上下文理解",
        "description": "先根据当前页面、当前角色和当前数据作用域理解真实问题，不按固定角色模板硬猜。",
    },
    {
        "id": "core.permission_boundary",
        "label": "权限边界",
        "description": "所有查询和动作都要服从当前登录用户的真实权限与数据范围，禁止越权推断。",
    },
    {
        "id": "core.form_collection",
        "label": "表单收集",
        "description": "当诉求需要结构化参数时，先补齐缺失字段，再进入确认或执行。",
    },
    {
        "id": "core.write_confirmation",
        "label": "写入确认",
        "description": "新增、修改、删除、审核等写入动作在执行前必须复述摘要并等待明确确认。",
    },
]

_ASSISTANT_BUILTIN_TOOLS: list[dict[str, Any]] = [
    {
        "id": "time.now",
        "label": "当前时间",
        "description": "提供当前时区、本地时间和口语化时刻，帮助模型理解现在是什么时间点。",
        "methods": ["read_current_time"],
    },
    {
        "id": "time.range.resolve",
        "label": "相对时间范围解析",
        "description": "把下周、下月、本周、本月等相对时间表达归一化为日期范围。",
        "methods": ["resolve_relative_range"],
    },
    {
        "id": "session.scope.inspect",
        "label": "当前会话作用域",
        "description": "提供当前用户、路由和团队可见范围，用于避免越权回答。",
        "methods": ["read_session_scope"],
    },
    {
        "id": "page.context.refresh",
        "label": "页面上下文刷新",
        "description": "重新读取当前路由上下文，便于在对话中同步页面状态。",
        "methods": ["refresh_route_context"],
    },
]


def assistant_builtin_skill_catalog() -> list[dict[str, Any]]:
    return deepcopy(_ASSISTANT_BUILTIN_SKILLS)


def assistant_builtin_tool_catalog() -> list[dict[str, Any]]:
    return deepcopy(_ASSISTANT_BUILTIN_TOOLS)


def _resolve_timezone(timezone_name: str | None = None) -> str:
    candidate = str(timezone_name or "").strip() or _DEFAULT_TIMEZONE
    try:
        ZoneInfo(candidate)
    except Exception:
        return _DEFAULT_TIMEZONE
    return candidate


def _resolve_now(timezone_name: str | None = None) -> tuple[str, datetime]:
    effective_timezone = _resolve_timezone(timezone_name)
    return effective_timezone, datetime.now(ZoneInfo(effective_timezone))


def _spoken_now(now: datetime) -> str:
    hour = now.strftime("%H").lstrip("0") or "0"
    minute = now.strftime("%M")
    if minute == "00":
        return f"{hour} 点"
    return f"{hour} 点 {minute} 分"


def _resolve_week_range(current: date, *, offset_weeks: int = 0) -> tuple[date, date]:
    monday = current - timedelta(days=current.weekday()) + timedelta(weeks=offset_weeks)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _resolve_month_range(current: date, *, offset_months: int = 0) -> tuple[date, date]:
    year = current.year
    month = current.month + offset_months
    while month > 12:
        year += 1
        month -= 12
    while month < 1:
        year -= 1
        month += 12
    start = date(year, month, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    end = next_month - timedelta(days=1)
    return start, end


def _resolve_relative_ranges(current: date) -> dict[str, Any]:
    this_week_start, this_week_end = _resolve_week_range(current, offset_weeks=0)
    next_week_start, next_week_end = _resolve_week_range(current, offset_weeks=1)
    this_month_start, this_month_end = _resolve_month_range(current, offset_months=0)
    next_month_start, next_month_end = _resolve_month_range(current, offset_months=1)
    return {
        "today": current.isoformat(),
        "thisWeek": {"startDate": this_week_start.isoformat(), "endDate": this_week_end.isoformat()},
        "nextWeek": {"startDate": next_week_start.isoformat(), "endDate": next_week_end.isoformat()},
        "thisMonth": {"startDate": this_month_start.isoformat(), "endDate": this_month_end.isoformat()},
        "nextMonth": {"startDate": next_month_start.isoformat(), "endDate": next_month_end.isoformat()},
    }


def _normalize_enabled_binding_map(items: Any) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    if not isinstance(items, list):
        return normalized
    for item in items:
        if not isinstance(item, dict):
            continue
        binding_id = str(item.get("id") or "").strip()
        if not binding_id:
            continue
        if item.get("enabled") is False:
            continue
        normalized[binding_id] = item
    return normalized


def _extract_module_capability_context(
    context_data: dict[str, Any] | None,
    *,
    max_visible_tools: int,
    expose_manifest: bool,
) -> dict[str, Any]:
    source = context_data if isinstance(context_data, dict) else {}
    current_role_profile = source.get("currentRoleProfile") if isinstance(source.get("currentRoleProfile"), dict) else {}
    capability_manifest = source.get("capabilityManifest") if isinstance(source.get("capabilityManifest"), dict) else {}
    operation_policy = source.get("operationPolicy") if isinstance(source.get("operationPolicy"), dict) else {}
    tool_catalog = source.get("toolCatalog") if isinstance(source.get("toolCatalog"), list) else []
    skill_packs = source.get("skillPacks") if isinstance(source.get("skillPacks"), list) else []

    available_tools: list[dict[str, Any]] = []
    for item in tool_catalog:
        if not isinstance(item, dict):
            continue
        tool_id = str(item.get("id") or "").strip()
        if not tool_id:
            continue
        if item.get("available") is False:
            continue
        available_tools.append(
            {
                "id": tool_id,
                "label": str(item.get("label") or tool_id).strip(),
                "mode": str(item.get("mode") or "").strip(),
                "resource": str(item.get("resource") or "").strip(),
            }
        )
        if len(available_tools) >= max_visible_tools:
            break

    compact_manifest = {}
    if expose_manifest and capability_manifest:
        compact_manifest = {
            "skillCount": capability_manifest.get("skillCount"),
            "availableSkillCount": capability_manifest.get("availableSkillCount"),
            "resourceSummary": capability_manifest.get("resourceSummary"),
            "lifecycleSummary": capability_manifest.get("lifecycleSummary"),
            "recommendedToolIds": capability_manifest.get("recommendedToolIds"),
        }

    compact_skill_packs: list[dict[str, Any]] = []
    for item in skill_packs:
        if not isinstance(item, dict):
            continue
        compact_skill_packs.append(
            {
                "id": str(item.get("id") or "").strip(),
                "label": str(item.get("label") or item.get("id") or "").strip(),
                "description": str(item.get("description") or "").strip(),
                "triggerHint": str(item.get("triggerHint") or "").strip(),
                "available": bool(item.get("available", True)),
                "availableToolIds": [
                    str(tool_id).strip()
                    for tool_id in item.get("availableToolIds", [])
                    if str(tool_id).strip()
                ][: max_visible_tools],
            }
        )
        if len(compact_skill_packs) >= max_visible_tools:
            break

    return {
        "currentRoleProfile": {
            "id": str(current_role_profile.get("id") or "").strip(),
            "label": str(current_role_profile.get("label") or "").strip(),
            "actorKind": str(current_role_profile.get("actorKind") or "").strip(),
        },
        "skillPacks": compact_skill_packs,
        "availableTools": available_tools,
        "capabilityManifest": compact_manifest,
        "operationPolicy": deepcopy(operation_policy),
    }


def build_assistant_capability_context(
    *,
    capability_config: dict[str, Any] | None,
    module_code: str,
    route_path: str,
    context_data: dict[str, Any] | None,
    user_id: int,
    viewer_team_ids: list[int],
    read_team_ids: list[int] | None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    source = capability_config if isinstance(capability_config, dict) else {}
    policy = source.get("policy") if isinstance(source.get("policy"), dict) else {}
    max_visible_tools_raw = policy.get("maxVisibleTools")
    try:
        max_visible_tools = int(max_visible_tools_raw or 8)
    except (TypeError, ValueError):
        max_visible_tools = 8
    max_visible_tools = max(1, min(max_visible_tools, 20))

    enabled_skill_map = _normalize_enabled_binding_map(source.get("skillBindings"))
    enabled_tool_map = _normalize_enabled_binding_map(source.get("toolBindings"))

    skills = []
    for descriptor in assistant_builtin_skill_catalog():
        binding = enabled_skill_map.get(descriptor["id"])
        if not binding:
            continue
        item = deepcopy(descriptor)
        item["instruction"] = str(binding.get("instruction") or "").strip()
        skills.append(item)

    tools = []
    for descriptor in assistant_builtin_tool_catalog():
        binding = enabled_tool_map.get(descriptor["id"])
        if not binding:
            continue
        item = deepcopy(descriptor)
        item["instruction"] = str(binding.get("instruction") or "").strip()
        tools.append(item)

    memory = source.get("memory") if isinstance(source.get("memory"), dict) else {}
    profile = memory.get("profile") if isinstance(memory.get("profile"), dict) else {}

    effective_timezone, now = _resolve_now(timezone_name)
    module_capabilities = _extract_module_capability_context(
        context_data,
        max_visible_tools=max_visible_tools,
        expose_manifest=bool(policy.get("exposeModuleCapabilityManifest", True)),
    )

    imported_tools = []
    if bool(policy.get("allowImportedToolsInChat")):
        for item in source.get("importedTools", []) if isinstance(source.get("importedTools"), list) else []:
            if not isinstance(item, dict):
                continue
            imported_tools.append(
                {
                    "id": str(item.get("id") or "").strip(),
                    "label": str(item.get("label") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                }
            )
            if len(imported_tools) >= max_visible_tools:
                break

    return {
        "skills": skills,
        "tools": tools,
        "importedTools": imported_tools,
        "memory": {
            "workingSummary": str(memory.get("workingSummary") or "").strip(),
            "profile": {
                "preferredStyle": str(profile.get("preferredStyle") or "").strip(),
                "avoidedPhrases": [
                    str(item).strip()
                    for item in profile.get("avoidedPhrases", [])
                    if str(item).strip()
                ][:8],
                "preferredDomains": [
                    str(item).strip()
                    for item in profile.get("preferredDomains", [])
                    if str(item).strip()
                ][:8],
            },
        },
        "policy": {
            "requireConfirmationForWrites": bool(policy.get("requireConfirmationForWrites", True)),
            "exposeModuleCapabilityManifest": bool(policy.get("exposeModuleCapabilityManifest", True)),
            "allowImportedToolsInChat": bool(policy.get("allowImportedToolsInChat", False)),
            "maxVisibleTools": max_visible_tools,
        },
        "runtime": {
            "moduleCode": module_code,
            "routePath": route_path,
            "time": {
                "timezone": effective_timezone,
                "localizedNow": now.isoformat(timespec="minutes"),
                "spokenNow": _spoken_now(now),
            },
            "timeRanges": _resolve_relative_ranges(now.date()),
            "sessionScope": {
                "userId": int(user_id),
                "viewerTeamIds": list(viewer_team_ids or []),
                "readTeamIds": list(read_team_ids or []),
            },
        },
        "moduleCapabilities": module_capabilities,
    }


def build_assistant_capability_context_text(context: dict[str, Any] | None) -> str:
    source = context if isinstance(context, dict) else {}
    lines: list[str] = []

    runtime = source.get("runtime") if isinstance(source.get("runtime"), dict) else {}
    time_context = runtime.get("time") if isinstance(runtime.get("time"), dict) else {}
    if time_context:
        lines.append("- tool.time.now")
        lines.append(f"  当前时区：{str(time_context.get('timezone') or _DEFAULT_TIMEZONE).strip()}")
        localized_now = str(time_context.get("localizedNow") or "").strip()
        if localized_now:
            lines.append(f"  当前时间：{localized_now}")
        spoken_now = str(time_context.get("spokenNow") or "").strip()
        if spoken_now:
            lines.append(f"  当前口语时间：{spoken_now}")

    time_ranges = runtime.get("timeRanges") if isinstance(runtime.get("timeRanges"), dict) else {}
    if time_ranges:
        lines.append("- tool.time.range.resolve")
        for key in ("thisWeek", "nextWeek", "thisMonth", "nextMonth"):
            item = time_ranges.get(key) if isinstance(time_ranges.get(key), dict) else {}
            start_date = str(item.get("startDate") or "").strip()
            end_date = str(item.get("endDate") or "").strip()
            if start_date and end_date:
                lines.append(f"  {key}: {start_date} ~ {end_date}")

    session_scope = runtime.get("sessionScope") if isinstance(runtime.get("sessionScope"), dict) else {}
    if session_scope:
        lines.append("- tool.session.scope.inspect")
        lines.append(f"  当前用户：{int(session_scope.get('userId') or 0)}")
        lines.append(
            "  团队可见范围："
            + ", ".join(str(item) for item in session_scope.get("readTeamIds", []) if str(item).strip())
            if session_scope.get("readTeamIds")
            else "  团队可见范围：当前为全局读取或未限制"
        )

    policy = source.get("policy") if isinstance(source.get("policy"), dict) else {}
    if policy:
        lines.append("- policy")
        lines.append(f"  写入确认：{'必须确认' if bool(policy.get('requireConfirmationForWrites', True)) else '可直接执行'}")
        lines.append(f"  单轮最多暴露工具数：{int(policy.get('maxVisibleTools') or 8)}")
        lines.append(
            f"  imported tools 对话可见：{'是' if bool(policy.get('allowImportedToolsInChat')) else '否'}"
        )

    skills = source.get("skills") if isinstance(source.get("skills"), list) else []
    if skills:
        lines.append("- skills")
        for item in skills[:6]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("id") or "").strip()
            description = str(item.get("description") or "").strip()
            if label and description:
                lines.append(f"  - {label}: {description}")

    tools = source.get("tools") if isinstance(source.get("tools"), list) else []
    if tools:
        lines.append("- built-in tools")
        for item in tools[:8]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("id") or "").strip()
            description = str(item.get("description") or "").strip()
            if label and description:
                lines.append(f"  - {label}: {description}")

    module_capabilities = source.get("moduleCapabilities") if isinstance(source.get("moduleCapabilities"), dict) else {}
    current_role_profile = (
        module_capabilities.get("currentRoleProfile")
        if isinstance(module_capabilities.get("currentRoleProfile"), dict)
        else {}
    )
    role_label = str(current_role_profile.get("label") or current_role_profile.get("id") or "").strip()
    actor_kind = str(current_role_profile.get("actorKind") or "").strip()
    if role_label or actor_kind:
        lines.append("- module role")
        if role_label:
            lines.append(f"  当前角色画像：{role_label}")
        if actor_kind:
            lines.append(f"  actorKind: {actor_kind}")

    available_tools = (
        module_capabilities.get("availableTools")
        if isinstance(module_capabilities.get("availableTools"), list)
        else []
    )
    skill_packs = (
        module_capabilities.get("skillPacks")
        if isinstance(module_capabilities.get("skillPacks"), list)
        else []
    )
    if skill_packs:
        lines.append("- module skills")
        for item in skill_packs[:8]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("id") or "").strip()
            description = str(item.get("description") or "").strip()
            available = bool(item.get("available", True))
            available_tool_ids = [
                str(tool_id).strip()
                for tool_id in item.get("availableToolIds", [])
                if str(tool_id).strip()
            ]
            if label:
                summary_parts = []
                if description:
                    summary_parts.append(description)
                if available_tool_ids:
                    summary_parts.append("tools: " + " / ".join(available_tool_ids[:6]))
                if not available:
                    summary_parts.append("当前工具未就绪")
                lines.append(f"  - {label}: {'；'.join(summary_parts) if summary_parts else 'skill pack'}")

    if available_tools:
        lines.append("- module available tools")
        for item in available_tools[:8]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("id") or "").strip()
            tool_id = str(item.get("id") or "").strip()
            mode = str(item.get("mode") or "").strip()
            resource = str(item.get("resource") or "").strip()
            detail = " / ".join(part for part in [tool_id, mode, resource] if part)
            if detail:
                lines.append(f"  - {label}: {detail}")
            else:
                lines.append(f"  - {label}")

    operation_policy = (
        module_capabilities.get("operationPolicy")
        if isinstance(module_capabilities.get("operationPolicy"), dict)
        else {}
    )
    if operation_policy:
        lines.append("- module operation policy")
        for key in ("auth", "readScope", "writeGuard", "frontendTokenRule"):
            text = str(operation_policy.get(key) or "").strip()
            if text:
                lines.append(f"  - {key}: {text}")

    memory = source.get("memory") if isinstance(source.get("memory"), dict) else {}
    profile = memory.get("profile") if isinstance(memory.get("profile"), dict) else {}
    working_summary = str(memory.get("workingSummary") or "").strip()
    preferred_style = str(profile.get("preferredStyle") or "").strip()
    avoided_phrases = [str(item).strip() for item in profile.get("avoidedPhrases", []) if str(item).strip()]
    preferred_domains = [str(item).strip() for item in profile.get("preferredDomains", []) if str(item).strip()]
    if working_summary or preferred_style or avoided_phrases or preferred_domains:
        lines.append("- memory")
        if working_summary:
            lines.append(f"  working summary: {working_summary}")
        if preferred_style:
            lines.append(f"  preferred style: {preferred_style}")
        if avoided_phrases:
            lines.append("  avoided phrases: " + " / ".join(avoided_phrases[:8]))
        if preferred_domains:
            lines.append("  preferred domains: " + " / ".join(preferred_domains[:8]))

    imported_tools = source.get("importedTools") if isinstance(source.get("importedTools"), list) else []
    if imported_tools:
        lines.append("- imported tools")
        for item in imported_tools[:8]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("id") or "").strip()
            description = str(item.get("description") or "").strip()
            if label and description:
                lines.append(f"  - {label}: {description}")

    return "\n".join(lines).strip()


def _resolve_requested_range_id(params: dict[str, Any]) -> str:
    candidates = [params.get("range"), params.get("rangeId"), params.get("text"), params.get("query")]
    raw = " ".join(str(item).strip().lower() for item in candidates if str(item or "").strip())
    if "下周" in raw or "next week" in raw:
        return "nextWeek"
    if "下月" in raw or "next month" in raw:
        return "nextMonth"
    if "本周" in raw or "this week" in raw:
        return "thisWeek"
    if "本月" in raw or "this month" in raw:
        return "thisMonth"
    return "nextWeek"


async def execute_assistant_builtin_tool(
    *,
    action_type: str,
    params: dict[str, Any] | None,
    route_path: str,
    module_code: str,
    context_data: dict[str, Any] | None,
    user_id: int,
    viewer_team_ids: list[int],
    read_team_ids: list[int] | None,
    context_loader: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    timezone_name: str | None = None,
) -> ActionResult | None:
    normalized_action = str(action_type or "").strip()
    normalized_params = params if isinstance(params, dict) else {}

    if normalized_action == "time.now":
        effective_timezone, now = _resolve_now(timezone_name)
        return ActionResult(
            success=True,
            data={
                "timezone": effective_timezone,
                "localizedNow": now.isoformat(timespec="minutes"),
                "spokenNow": _spoken_now(now),
            },
            message="已读取当前时间。",
        )

    if normalized_action == "time.range.resolve":
        _, now = _resolve_now(timezone_name)
        range_id = _resolve_requested_range_id(normalized_params)
        ranges = _resolve_relative_ranges(now.date())
        resolved = ranges.get(range_id) if isinstance(ranges.get(range_id), dict) else {}
        return ActionResult(
            success=True,
            data={
                "rangeId": range_id,
                "today": ranges["today"],
                "startDate": resolved.get("startDate"),
                "endDate": resolved.get("endDate"),
            },
            message="已解析相对时间范围。",
        )

    if normalized_action == "session.scope.inspect":
        return ActionResult(
            success=True,
            data={
                "moduleCode": module_code,
                "routePath": route_path,
                "userId": int(user_id),
                "viewerTeamIds": list(viewer_team_ids or []),
                "readTeamIds": list(read_team_ids or []),
            },
            message="已读取当前会话作用域。",
        )

    if normalized_action == "page.context.refresh":
        if context_loader is None:
            return ActionResult(success=False, data={"routePath": route_path}, message="当前上下文不支持刷新。")
        refreshed_context = await context_loader()
        return ActionResult(
            success=True,
            data={
                "moduleCode": module_code,
                "routePath": route_path,
                "context": refreshed_context,
                "previousContext": deepcopy(context_data if isinstance(context_data, dict) else {}),
            },
            message="已刷新当前页面上下文。",
        )

    return None
