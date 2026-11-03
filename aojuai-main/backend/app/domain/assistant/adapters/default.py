"""AOJU Backend - Assistant Default Adapter"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.domain.assistant.adapters.base import ActionResult, ModuleAdapterBase
from app.domain.assistant.capability_catalog import build_generic_capability_manifest
from app.domain.assistant.route_directory_service import AssistantScopeDirectoryService
from app.domain.assistant.schemas import PresetPrompt

_PAGE_NAVIGATION_TOOL_ID = "page.router.navigate"

_DEFAULT_ROLE_PROFILE = {
    "id": "default-viewer",
    "label": "当前登录用户",
    "actorKind": "authenticated_user",
    "preferredToolIds": [_PAGE_NAVIGATION_TOOL_ID],
    "availableToolIds": [_PAGE_NAVIGATION_TOOL_ID],
}

_DEFAULT_TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "id": _PAGE_NAVIGATION_TOOL_ID,
        "label": "前往目标页面",
        "summary": "当当前页面无法直接处理问题，但 scopeDirectory 已提供明确目标页时，给出前端页面跳转动作。",
        "description": "只声明页面导航目标，不执行服务端业务写入。优先补充 targetRoutePath；如已知模块则补充 targetModuleCode。",
        "mode": "query",
        "modeLabel": "页面导航",
        "toolType": "query",
        "accessMode": "read",
        "resource": "navigation",
        "resourceLabel": "页面导航",
        "available": True,
        "status": "active",
    }
]

_DEFAULT_SKILL_PACKS: list[dict[str, Any]] = [
    {
        "id": "default.page_orienter",
        "label": "通用导航助手",
        "description": "优先识别当前问题应该去哪个真实页面处理，并直接给出可跳转的目标入口。",
        "triggerHint": "去哪里看、打开哪个页面、带我去对应模块、系统用户在哪里、语音设置在哪里",
        "available": True,
        "availableToolIds": [_PAGE_NAVIGATION_TOOL_ID],
    }
]
_DEFAULT_NAVIGATION_FILLERS = (
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
    "引导",
    "带我",
    "跳转",
    "导航",
    "前往",
    "进入",
    "打开",
    "页面",
    "模块",
    "系统",
    "后台",
    "首页",
    "有多少",
    "有哪些",
    "多少",
    "在哪",
    "哪里",
)


def _is_channel_context(route: str, params: dict[str, Any]) -> bool:
    source = str((params or {}).get("source") or "").strip()
    return source == "message_channel" or route == "/message-channel"


def _compact_ids(values: list[int] | None) -> list[int]:
    return [int(item) for item in (values or []) if isinstance(item, int)]


def _read_scope_label(read_team_ids: list[int] | None) -> str:
    if read_team_ids is None:
        return "全部数据"
    if read_team_ids:
        return f"限定团队 {len(read_team_ids)} 个"
    return "无团队数据范围"


async def _load_user_identity(
    *,
    db: Any,
    tenant_id: int,
    user_id: int,
    viewer_team_ids: list[int],
    read_team_ids: list[int] | None,
    channel_context: bool,
) -> dict[str, Any]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.role_semantics import has_tenant_admin_role
    from app.domain.users.models import User

    role_codes: list[str] = []
    role_names: list[str] = []
    username = ""
    nickname = ""
    is_superuser = False
    if callable(getattr(db, "execute", None)):
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if user:
            username = str(getattr(user, "username", "") or "").strip()
            nickname = str(getattr(user, "nickname", "") or "").strip()
            is_superuser = bool(getattr(user, "is_superuser", False))
            for role in getattr(user, "roles", []) or []:
                if int(getattr(role, "tenant_id", tenant_id) or tenant_id) != int(tenant_id):
                    continue
                if not bool(getattr(role, "is_active", False)) or getattr(role, "deleted_at", None) is not None:
                    continue
                role_code = str(getattr(role, "code", "") or "").strip()
                role_name = str(getattr(role, "name", "") or "").strip()
                if role_code:
                    role_codes.append(role_code)
                if role_name:
                    role_names.append(role_name)

    is_tenant_admin = has_tenant_admin_role(role_codes)
    if is_superuser:
        role_label = "超级管理员"
        actor_kind = "superuser"
    elif is_tenant_admin:
        role_label = "租户管理员"
        actor_kind = "tenant_admin"
    elif role_names:
        role_label = "、".join(role_names[:3])
        actor_kind = "authenticated_user"
    else:
        role_label = "当前登录用户"
        actor_kind = "authenticated_user"
    if channel_context:
        role_label = f"{role_label}（个人 Channel）"

    display_name = nickname or username or f"用户 {user_id}"
    has_all_read_access = read_team_ids is None
    role_profile = {
        "id": f"user:{int(user_id)}",
        "label": role_label,
        "actorKind": actor_kind,
        "preferredToolIds": [],
        "availableToolIds": [],
        "userId": int(user_id),
        "tenantId": int(tenant_id),
        "displayName": display_name,
        "roleCodes": role_codes,
        "roleNames": role_names,
        "isSuperuser": is_superuser,
        "isTenantAdmin": is_tenant_admin,
        "hasAllReadAccess": has_all_read_access,
    }
    return {
        "roleProfile": role_profile,
        "systemIdentity": {
            "userId": int(user_id),
            "tenantId": int(tenant_id),
            "displayName": display_name,
            "username": username,
            "nickname": nickname,
            "roleCodes": role_codes,
            "roleNames": role_names,
            "isSuperuser": is_superuser,
            "isTenantAdmin": is_tenant_admin,
        },
        "dataScope": {
            "viewerTeamIds": _compact_ids(viewer_team_ids),
            "readTeamIds": [] if has_all_read_access else _compact_ids(read_team_ids),
            "hasAllReadAccess": has_all_read_access,
            "readScopeLabel": _read_scope_label(read_team_ids),
        },
    }


def _role_profile_from_context(context_data: dict[str, Any] | None) -> dict[str, Any] | None:
    source = context_data if isinstance(context_data, dict) else {}
    role_profile = source.get("currentRoleProfile")
    return dict(role_profile) if isinstance(role_profile, dict) else None


def _normalize_lookup_text(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
    for filler in _DEFAULT_NAVIGATION_FILLERS:
        text = text.replace(filler, " ")
    return re.sub(r"\s+", " ", text).strip()


def _compact_lookup_text(value: Any) -> str:
    return _normalize_lookup_text(str(value or "")).replace(" ", "")


def _collect_compact_fragments(value: str | None, *, min_len: int = 2, max_len: int = 4, limit: int = 24) -> list[str]:
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
                    return fragments[:limit]
    return fragments[:limit]


def _score_shared_fragments(query_text: str, candidate_text: Any, *, weight: int) -> int:
    compact_candidate = _compact_lookup_text(candidate_text)
    if not compact_candidate:
        return 0
    score = 0
    matched_count = 0
    for fragment in _collect_compact_fragments(query_text):
        if fragment not in compact_candidate:
            continue
        score += len(fragment) * weight
        matched_count += 1
        if matched_count >= 4:
            break
    return score


def _iter_scope_directory_items(scope_directory: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(scope_directory, dict):
        return []
    items: list[dict[str, Any]] = []
    current_scope = scope_directory.get("currentScope")
    if isinstance(current_scope, dict) and isinstance(current_scope.get("item"), dict):
        items.append(dict(current_scope["item"]))
    for scope_key in ("moduleScope", "globalScope"):
        scope = scope_directory.get(scope_key)
        if not isinstance(scope, dict):
            continue
        for item in scope.get("items") or []:
            if isinstance(item, dict):
                items.append(dict(item))
    return items


def _score_navigation_candidate(*, query_text: str, item: dict[str, Any], current_route_path: str) -> int:
    route_path = str(item.get("routePath") or "").strip()
    if not route_path or route_path == current_route_path or item.get("canNavigate") is False:
        return 0

    compact_query = _compact_lookup_text(query_text)
    if not compact_query:
        return 0

    title = _compact_lookup_text(item.get("title"))
    module_name = _compact_lookup_text(item.get("moduleName"))
    page_summary = _compact_lookup_text(item.get("pageSummary"))
    query_hints = [_compact_lookup_text(hint) for hint in (item.get("queryHints") or []) if _compact_lookup_text(hint)]

    score = 0
    if title:
        if compact_query == title:
            score += 360 + len(title) * 6
        elif title in compact_query:
            score += 260 + len(title) * 5
        elif compact_query in title:
            score += 220 + len(compact_query) * 4
    if module_name and (module_name in compact_query or compact_query in module_name):
        score += 120
    if page_summary:
        if compact_query in page_summary:
            score += 180 + len(compact_query) * 3
        score += _score_shared_fragments(query_text, item.get("pageSummary"), weight=18)
    score += _score_shared_fragments(query_text, item.get("title"), weight=38)
    for hint in query_hints:
        if compact_query == hint:
            score += 320 + len(hint) * 5
        elif hint in compact_query:
            score += 210 + len(hint) * 4
        elif compact_query in hint:
            score += 170 + len(compact_query) * 3
        score += _score_shared_fragments(query_text, hint, weight=28)
    return score


def _resolve_best_navigation_target(
    *,
    query_text: str,
    scope_directory: dict[str, Any] | None,
    current_route_path: str,
) -> dict[str, Any] | None:
    candidates = []
    for item in _iter_scope_directory_items(scope_directory):
        score = _score_navigation_candidate(query_text=query_text, item=item, current_route_path=current_route_path)
        if score > 0:
            candidates.append((score, item))
    if not candidates:
        return None
    candidates.sort(
        key=lambda pair: (
            pair[0],
            len(_compact_lookup_text(pair[1].get("title"))),
            str(pair[1].get("routePath") or ""),
        ),
        reverse=True,
    )
    best_score, best_item = candidates[0]
    if best_score < 150:
        return None
    return best_item


class DefaultAdapter(ModuleAdapterBase):
    """Fallback adapter for routes without a dedicated module."""

    module_code = "default"
    module_name = "通用助手"
    supported_routes = ["/*"]
    default_chat_prompt = (
        "当当前页面无法直接完成用户诉求、但 scopeDirectory 已经给出明确目标页时，"
        "直接输出页面导航动作，不要先解释一大段，也不要反问“要不要去这个模块”。"
        "正文只保留一句简短导航说明，例如“已为你定位到系统用户页面”。"
    )

    async def get_context(
        self,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        channel_context = _is_channel_context(route, params)
        identity = await _load_user_identity(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
            channel_context=channel_context,
        )
        if channel_context:
            channel_role_profile = dict(identity["roleProfile"])
            channel_role_profile["preferredToolIds"] = []
            channel_role_profile["availableToolIds"] = []
            return {
                "today": date.today().isoformat(),
                "route": route,
                "source": "message_channel",
                "channelType": str((params or {}).get("channelType") or "").strip() or None,
                "currentRoleProfile": channel_role_profile,
                "systemIdentity": identity["systemIdentity"],
                "dataScope": identity["dataScope"],
                "pageContextAvailable": False,
                "businessModule": None,
                "message": "当前会话来自个人消息 Channel，没有打开任何业务页面，也没有绑定具体业务模块。",
                "emptyContextRules": [
                    "不要臆造项目、日程、任务、客户、表单或其他业务对象。",
                    "只有当用户明确提供业务对象信息时，才围绕用户提供的信息回答。",
                    "如果用户要求查看或操作某个模块，请提示其打开对应模块页面，或先说明你当前只能进行通用问答。",
                ],
                "moduleMapGuidance": [
                    {"routePrefix": "/message-channel", "module": None, "rule": "个人 Channel 会话，无页面上下文。"},
                    {"routePrefix": "/speech", "module": "speech", "rule": "仅语音演示与语音配置相关。"},
                    {"routePrefix": "/system/tenant-settings?tab=speech", "module": "speech", "rule": "仅租户语音设置相关。"},
                ],
            }
        scope_directory: dict[str, Any] = {}
        if callable(getattr(db, "execute", None)):
            try:
                scope_directory = await AssistantScopeDirectoryService(db).build_scope_directory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    current_route_path=route,
                    current_module_code=self.module_code,
                    current_module_name=self.module_name,
                )
            except Exception:
                scope_directory = {}
        return {
            "today": date.today().isoformat(),
            "route": route,
            "params": params,
            "currentRoleProfile": identity["roleProfile"],
            "systemIdentity": identity["systemIdentity"],
            "dataScope": identity["dataScope"],
            "pageContextAvailable": route not in {"", "/"},
            "businessModule": None,
            "message": "当前页面未接入专属 Assistant 模块，使用通用对话能力。",
            "emptyContextRules": [
                "没有专属模块上下文时，不要臆造项目、日程、任务、客户、表单或其他业务对象。",
                "若用户没有给出具体业务对象，只做通用解释、澄清问题或引导用户打开对应模块。",
            ],
            "scopeDirectory": scope_directory,
            "moduleMapGuidance": [
                {"routePrefix": "/speech", "module": "speech", "rule": "只回答语音配置、TTS、STT、音色复刻相关内容。"},
                {"routePrefix": "/schedule", "module": "schedule", "rule": "只有当前路由明确为日程页面时，才可提到日程。"},
            ],
        }

    async def get_presets(
        self,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> list[PresetPrompt]:
        if _is_channel_context(route, params):
            return [
                PresetPrompt(id="channel-help", label="Channel 能做什么", prompt="这个 Channel 现在能帮我做什么？", icon="question"),
                PresetPrompt(
                    id="channel-context",
                    label="说明上下文",
                    prompt="请说明你当前能看到哪些上下文，以及哪些业务内容需要我先提供。",
                    icon="info",
                ),
            ]
        return [
            PresetPrompt(id="help", label="我能做什么", prompt="你现在能帮我做什么？", icon="question"),
            PresetPrompt(
                id="next-step",
                label="下一步建议",
                prompt="请结合当前页面上下文，给我 3 条优先可执行动作。",
                icon="list",
            ),
        ]

    async def get_capability_source(
        self,
        route: str,
        params: dict[str, Any],
        *,
        context_data: dict[str, Any] | None,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> dict[str, Any] | None:
        tool_catalog: list[dict[str, Any]] = [] if _is_channel_context(route, params) else [dict(item) for item in _DEFAULT_TOOL_CATALOG]
        role_profile = _role_profile_from_context(context_data) or dict(_DEFAULT_ROLE_PROFILE)
        skill_packs = [dict(item) for item in _DEFAULT_SKILL_PACKS]
        if _is_channel_context(route, params):
            role_profile["actorKind"] = str(role_profile.get("actorKind") or "authenticated_user")
            role_profile["preferredToolIds"] = []
            role_profile["availableToolIds"] = []
            skill_packs = [
                {
                    **item,
                    "availableToolIds": [],
                }
                for item in skill_packs
            ]
        return {
            "currentRoleProfile": role_profile,
            "skillPacks": skill_packs,
            "toolCatalog": tool_catalog,
            "capabilityManifest": build_generic_capability_manifest(
                scope_id="default",
                role_profile=role_profile,
                tool_catalog=tool_catalog,
                skill_packs=skill_packs,
            ),
            "operationPolicy": {
                "auth": "Use the current logged-in user and current route context only.",
                "readScope": "Only explain the page context already visible to the current user.",
                "writeGuard": "Default module does not expose server-side write actions.",
                "frontendTokenRule": "Do not ask the browser to expose provider secrets or tokens to the model.",
                "toolAvailabilityRule": "Only toolCatalog items with available=true may be emitted as assistantAction.",
                "moduleMapRule": "Do not infer a business module from generic words. Only use a module when the route prefix or explicit channel context maps to it.",
                "emptyContextRule": "When pageContextAvailable is false, do not mention project schedules, tasks, forms, customers, or other business records unless the user supplied them.",
                "navigationRule": "For web UI routes, page.router.navigate is a frontend-only action. Do not execute server writes for it.",
            },
        }

    def get_governance_skill_catalog(self) -> list[dict[str, Any]]:
        return [dict(item) for item in _DEFAULT_SKILL_PACKS]

    async def infer_action_from_reply(
        self,
        reply: str,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        del viewer_team_ids, read_team_ids, prior_action
        if _is_channel_context(route, params):
            return None
        normalized_query = _normalize_lookup_text(reply)
        if not normalized_query:
            return None
        if not callable(getattr(db, "execute", None)):
            return None
        try:
            scope_directory = await AssistantScopeDirectoryService(db).build_scope_directory(
                tenant_id=tenant_id,
                user_id=user_id,
                current_route_path=route,
                current_module_code=self.module_code,
                current_module_name=self.module_name,
            )
        except Exception:
            return None
        target_item = _resolve_best_navigation_target(
            query_text=normalized_query,
            scope_directory=scope_directory,
            current_route_path=route,
        )
        if not isinstance(target_item, dict):
            return None
        title = str(target_item.get("title") or "").strip() or "目标页面"
        return {
            "toolId": _PAGE_NAVIGATION_TOOL_ID,
            "toolLabel": "前往目标页面",
            "mode": "ready",
            "summary": f"已为你定位到“{title}”。",
            "targetRoutePath": str(target_item.get("routePath") or "").strip(),
            "targetModuleCode": str(target_item.get("moduleCode") or "").strip() or None,
            "confirmationRequired": False,
            "canExecute": True,
            "autoExecute": False,
            "confirmText": "前往页面",
            "collectedParams": {},
            "missingFields": [],
        }

    async def execute_action(
        self,
        action: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> ActionResult:
        return ActionResult(success=False, message="默认适配器不支持此操作")
