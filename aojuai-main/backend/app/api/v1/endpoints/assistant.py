"""AOJU Backend - Assistant Foundation Endpoints"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentTenantAdmin, CurrentUser, DataScopeCtx, DBSession, TenantCtx
from app.core.logger import get_logger
from app.core.response import ErrorResponse, SuccessResponse
from app.core.schemas import ResponseBase
from app.domain.assistant.action_protocol import sanitize_streaming_assistant_text
from app.domain.assistant.adapters import AdapterRegistry
from app.domain.assistant.capability_runtime import (
    build_assistant_capability_context,
    build_assistant_capability_context_text,
)
from app.domain.assistant.config_schemas import AssistantConfigUpsertRequest, AssistantConfigView
from app.domain.assistant.config_service import AssistantConfigService
from app.domain.assistant.openai_client import OpenAIClient
from app.domain.assistant.schemas import (
    ActionRequest,
    ActionResponse,
    ChatReplyRequest,
    ChatReplyResponse,
    ContextResponse,
    MessageResponse,
    PresetsResponse,
    SessionCreate,
    SessionResponse,
)
from app.domain.assistant.service import AssistantService
from app.domain.assistant_bridge import (
    normalize_assistant_stored_config,
    resolve_assistant_prompt_stack,
    resolve_assistant_provider_runtime,
)
from app.domain.auth.service import TenantService
from app.domain.users.models import UserTeam

router = APIRouter()
logger = get_logger(__name__)


class AssistantChatRequest(BaseModel):
    """兼容 old/new assistant chat payload."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("session_id", "sessionId"),
    )
    message: str = Field(..., min_length=1, max_length=8000)
    route_path: str | None = Field(
        default="/",
        validation_alias=AliasChoices("route_path", "routePath"),
    )
    context_params: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("context_params", "contextParams"),
    )


def _serialize_assistant_config_view(data: AssistantConfigView) -> dict[str, Any]:
    return data.model_dump(by_alias=True)


def _normalize_route_path(value: str | None) -> str:
    route = str(value or "").strip()
    if not route:
        return "/"
    if not route.startswith("/"):
        return f"/{route}"
    return route


def _resolve_team_ids(data_scope: DataScopeCtx) -> list[int] | None:
    if data_scope.has_all_read_access:
        return None
    return [int(item) for item in data_scope.read_team_ids if isinstance(item, int)]


def _parse_context_query(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _encode_sse(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


async def _get_user_team_ids(db: DBSession, *, tenant_id: int, user_id: int) -> list[int]:
    result = await db.execute(
        select(UserTeam.team_id).where(
            UserTeam.tenant_id == tenant_id,
            UserTeam.user_id == user_id,
        )
    )
    return [int(item) for item in result.scalars().all()]


def _extract_capability_config(assistant_config: Any) -> dict[str, Any]:
    if isinstance(assistant_config, dict):
        normalized = normalize_assistant_stored_config(assistant_config)
        capabilities = normalized.get("capabilities")
        return capabilities if isinstance(capabilities, dict) else {}

    config_payload = (
        assistant_config.config
        if assistant_config and isinstance(getattr(assistant_config, "config", None), dict)
        else {}
    )
    capabilities = config_payload.get("capabilities")
    return capabilities if isinstance(capabilities, dict) else {}


def _is_assistant_enabled(assistant_config: Any) -> bool:
    if isinstance(assistant_config, dict):
        normalized = normalize_assistant_stored_config(assistant_config)
        return bool(normalized.get("enabled"))
    return bool(assistant_config and getattr(assistant_config, "enabled", False))


async def _resolve_effective_assistant_config(
    *,
    db: DBSession,
    tenant_id: int,
    tenant_config: dict[str, Any] | None = None,
) -> Any:
    config_service = AssistantConfigService(db)
    config = await config_service.get_config(tenant_id)
    if config is not None:
        return config
    if isinstance(tenant_config, dict):
        payload = tenant_config.get("assistant")
        if isinstance(payload, dict):
            return payload
    return None


def _resolve_adapter(route_path: str):
    adapter = AdapterRegistry.resolve_by_route(route_path)
    if adapter:
        return adapter
    fallback = AdapterRegistry.get("default")
    if fallback:
        return fallback
    raise RuntimeError("Assistant default adapter not registered")


async def _load_adapter_context_data(
    *,
    adapter: Any,
    route_path: str,
    context_params: dict[str, Any],
    db: DBSession,
    tenant_id: int,
    user_id: int,
    viewer_team_ids: list[int],
    read_team_ids: list[int] | None,
    capability_config: dict[str, Any] | None,
) -> dict[str, Any]:
    from app.domain.assistant.module_skill_governance import apply_module_skill_governance_to_context

    context_data = await adapter.get_context(
        route_path,
        context_params,
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        viewer_team_ids=viewer_team_ids,
        read_team_ids=read_team_ids,
    )
    normalized_context = dict(context_data or {}) if isinstance(context_data, dict) else {}
    capability_source = await adapter.get_capability_source(
        route_path,
        context_params,
        context_data=normalized_context,
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        viewer_team_ids=viewer_team_ids,
        read_team_ids=read_team_ids,
    )
    if isinstance(capability_source, dict) and capability_source:
        merged_context = {**normalized_context, **capability_source}
        return apply_module_skill_governance_to_context(
            module_code=str(getattr(adapter, "module_code", "") or "").strip(),
            context_data=merged_context,
            capability_config=capability_config,
        )
    return normalized_context


def _default_suggestions(route_path: str) -> list[str]:
    if route_path.startswith("/system/tenant-settings"):
        return [
            "请帮我检查当前 AI 助手配置是否完整。",
            "请说明当前配置项分别有什么作用。",
            "请列出启用统一助手前需要确认的风险点。",
        ]

    return [
        "请总结当前页面的重点信息，并告诉我最重要的三件事。",
        "请结合当前页面上下文，给我三个务实的下一步建议。",
        "请基于当前页面内容，列出需要优先检查的风险点。",
    ]


def _suggestions_from_presets(presets: list[Any], route_path: str) -> list[str]:
    prompts = [str(item.prompt).strip() for item in presets if str(getattr(item, "prompt", "")).strip()]
    return prompts[:3] or _default_suggestions(route_path)


def _build_user_context(
    current_user: Any,
    tenant_ctx: TenantCtx,
    *,
    viewer_team_ids: list[int],
    read_team_ids: list[int] | None,
) -> dict[str, Any]:
    return {
        "id": getattr(current_user, "id", None),
        "username": getattr(current_user, "username", None),
        "nickname": getattr(current_user, "nickname", None),
        "tenantId": tenant_ctx.tenant_id,
        "isSuperuser": bool(getattr(current_user, "is_superuser", False)),
        "viewerTeamIds": list(viewer_team_ids or []),
        "readTeamIds": list(read_team_ids or []),
    }


def _build_system_prompt(
    *,
    route_path: str,
    prompt_stack: dict[str, str],
    user_context: dict[str, Any],
    module_name: str,
    context_data: dict[str, Any],
    capability_context_text: str,
) -> str:
    return (
        f"{prompt_stack['system']}\n\n"
        "你当前运行在 AOJUAI nextjs-base 的统一助手底座中。\n"
        "你必须严格服从当前登录用户、当前租户、当前路由和当前数据范围，不要假设跨模块数据已经读到，也不要虚构任何写入已完成。\n"
        "当前底座允许的只有：页面上下文理解、模块 skill/tool 清单理解、基础时间工具和权限边界提示。\n"
        "业务模块若没有显式暴露动作能力，就只能做导航、解释、查询建议和表单草案。\n\n"
        f"【当前模块】{module_name}\n"
        f"【当前路由】{route_path}\n"
        f"【当前用户】{json.dumps(user_context, ensure_ascii=False)}\n"
        f"【页面上下文】{json.dumps(context_data or {}, ensure_ascii=False)}\n\n"
        f"【模块策略】{prompt_stack['moduleChat']}\n"
        f"【写入守卫】{prompt_stack['writeGuard']}\n"
        f"【能力框架】\n{capability_context_text}\n\n"
        "输出时优先使用简洁的 Markdown；若要给建议，请优先给最稳妥、最收敛的下一步。"
    ).strip()


def _build_local_fallback_reply(
    *,
    module_name: str,
    route_path: str,
    message: str,
    reason: str,
    suggestions: list[str],
) -> str:
    lines = [
        f"当前已切换到「{module_name}」的基座降级模式。",
        "",
        f"- 当前路由：`{route_path}`",
        f"- 当前问题：{message}",
        f"- 原因：{reason}",
    ]
    if suggestions:
        lines.extend(
            [
                "",
                "你可以先这样继续：",
                *[f"{index}. {item}" for index, item in enumerate(suggestions[:3], start=1)],
            ]
        )
    return "\n".join(lines)


async def _legacy_chat_stream(
    *,
    data: AssistantChatRequest,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
) -> Any:
    tenant = await TenantService(db).get_by_id(tenant_ctx.tenant_id)
    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    route_path = _normalize_route_path(data.route_path)
    context_params = data.context_params if isinstance(data.context_params, dict) else {}
    message = str(data.message or "").strip()
    if not message:
        return ErrorResponse(message="Message is required", code="VALIDATION_ERROR")

    config_service = AssistantConfigService(db)
    assistant_config = await _resolve_effective_assistant_config(
        db=db,
        tenant_id=tenant_ctx.tenant_id,
        tenant_config=tenant.config if isinstance(tenant.config, dict) else None,
    )
    adapter = _resolve_adapter(route_path)
    viewer_team_ids = await _get_user_team_ids(db, tenant_id=tenant_ctx.tenant_id, user_id=current_user.id)
    read_team_ids = _resolve_team_ids(data_scope)
    capability_config = _extract_capability_config(assistant_config)
    context_data = await _load_adapter_context_data(
        adapter=adapter,
        route_path=route_path,
        context_params=context_params,
        db=db,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        viewer_team_ids=viewer_team_ids,
        read_team_ids=read_team_ids,
        capability_config=capability_config,
    )
    presets = await adapter.get_presets(
        route_path,
        context_params,
        db=db,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        viewer_team_ids=viewer_team_ids,
        read_team_ids=read_team_ids,
    )
    suggestions = _suggestions_from_presets(presets, route_path)
    user_context = _build_user_context(
        current_user,
        tenant_ctx,
        viewer_team_ids=viewer_team_ids,
        read_team_ids=read_team_ids,
    )
    if isinstance(assistant_config, dict):
        prompt_stack = resolve_assistant_prompt_stack(
            assistant_config,
            assistant_key="default",
            module_code=adapter.module_code,
        )
    else:
        prompt_stack = await config_service.get_prompt_stack(
            tenant_id=tenant_ctx.tenant_id,
            module_code=adapter.module_code,
            module_name=adapter.module_name,
            default_module_chat_prompt=getattr(adapter, "default_chat_prompt", None),
        )
    capability_context = build_assistant_capability_context(
        capability_config=capability_config,
        module_code=adapter.module_code,
        route_path=route_path,
        context_data=context_data,
        user_id=current_user.id,
        viewer_team_ids=viewer_team_ids,
        read_team_ids=read_team_ids,
    )
    capability_context_text = build_assistant_capability_context_text(capability_context)

    async def event_stream():
        provider_settings = (
            resolve_assistant_provider_runtime(assistant_config)
            if isinstance(assistant_config, dict)
            else await config_service.get_provider_settings(tenant_ctx.tenant_id)
        )
        assistant_enabled = _is_assistant_enabled(assistant_config)
        if not assistant_enabled or not provider_settings:
            reply = _build_local_fallback_reply(
                module_name=adapter.module_name,
                route_path=route_path,
                message=message,
                reason="当前租户尚未启用或尚未完整配置统一助手模型。",
                suggestions=suggestions,
            )
            yield _encode_sse({"type": "content", "content": reply})
            yield _encode_sse(
                {
                    "type": "done",
                    "reply": reply,
                    "usedAi": False,
                    "moduleCode": adapter.module_code,
                    "moduleName": adapter.module_name,
                    "routePath": route_path,
                    "context": {
                        "routePath": route_path,
                        "contextParams": context_params,
                        "user": user_context,
                        "contextData": context_data,
                        "capabilityContext": capability_context,
                    },
                    "suggestions": suggestions,
                    "action": None,
                }
            )
            return

        client = OpenAIClient(
            base_url=provider_settings["base_url"],
            api_key=provider_settings["api_key"],
            model=provider_settings["model"],
            temperature=provider_settings["temperature"],
            max_tokens=provider_settings["max_tokens"],
            timeout_seconds=float(provider_settings.get("timeout_seconds") or 120),
        )
        messages = [
            {
                "role": "system",
                "content": _build_system_prompt(
                    route_path=route_path,
                    prompt_stack=prompt_stack,
                    user_context=user_context,
                    module_name=adapter.module_name,
                    context_data=context_data,
                    capability_context_text=capability_context_text,
                ),
            },
            {"role": "user", "content": message},
        ]

        full_response = ""
        visible_response = ""
        used_ai = False

        try:
            if bool(provider_settings.get("stream", True)):
                async for chunk in client.chat_stream(messages):
                    if not chunk:
                        continue
                    used_ai = True
                    full_response += chunk
                    next_visible_response = sanitize_streaming_assistant_text(full_response)
                    if not next_visible_response:
                        continue
                    if next_visible_response.startswith(visible_response):
                        delta = next_visible_response[len(visible_response) :]
                    else:
                        delta = next_visible_response
                    visible_response = next_visible_response
                    if delta:
                        yield _encode_sse({"type": "content", "content": delta})
            else:
                full_reply = await client.chat(messages)
                if full_reply:
                    used_ai = True
                    full_response = full_reply
                    visible_response = sanitize_streaming_assistant_text(full_response)
                    if visible_response:
                        yield _encode_sse({"type": "content", "content": visible_response})
        except Exception:
            logger.exception(
                "assistant_chat_failed",
                extra={
                    "tenant_id": tenant_ctx.tenant_id,
                    "user_id": current_user.id,
                    "route_path": route_path,
                    "module_code": adapter.module_code,
                },
            )
            if not visible_response:
                visible_response = _build_local_fallback_reply(
                    module_name=adapter.module_name,
                    route_path=route_path,
                    message=message,
                    reason="模型服务暂时不可用，未能返回有效内容。",
                    suggestions=suggestions,
                )
                used_ai = False
                yield _encode_sse({"type": "content", "content": visible_response})
            else:
                visible_response = f"{visible_response}\n\n> 模型连接中断，以上为当前已收到的内容。"
                yield _encode_sse({"type": "content", "content": "\n\n> 模型连接中断，以上为当前已收到的内容。"})

        reply = visible_response.strip() or "助手暂无回复。"
        yield _encode_sse(
            {
                "type": "done",
                "reply": reply,
                "usedAi": used_ai,
                "moduleCode": adapter.module_code,
                "moduleName": adapter.module_name,
                "routePath": route_path,
                "context": {
                    "routePath": route_path,
                    "contextParams": context_params,
                    "user": user_context,
                    "contextData": context_data,
                    "capabilityContext": capability_context,
                },
                "suggestions": suggestions,
                "action": None,
            }
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/config", response_model=ResponseBase[AssistantConfigView])
async def get_config(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    _ = current_user
    service = AssistantConfigService(db)
    config_view = await service.get_config_view(tenant_ctx.tenant_id)
    return SuccessResponse(data=_serialize_assistant_config_view(config_view))


@router.put("/config", response_model=ResponseBase[AssistantConfigView])
async def update_config(
    data: AssistantConfigUpsertRequest,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    _ = current_user
    service = AssistantConfigService(db)
    await service.upsert_config(tenant_ctx.tenant_id, data)
    config_view = await service.get_config_view(tenant_ctx.tenant_id)
    return SuccessResponse(data=_serialize_assistant_config_view(config_view))


@router.post("/sessions", response_model=ResponseBase[SessionResponse])
async def create_session(
    data: SessionCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    service = AssistantService(db)
    session = await service.create_session(
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        module_code=data.module_code,
        route_path=data.route_path,
        context_params=data.context_params,
    )
    return SuccessResponse(data=session)


@router.get("/sessions", response_model=ResponseBase[list[SessionResponse]])
async def list_sessions(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    service = AssistantService(db)
    sessions = await service.list_sessions(
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        limit=limit,
    )
    return SuccessResponse(data=sessions)


@router.get("/sessions/{session_id}", response_model=ResponseBase[SessionResponse])
async def get_session(
    session_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    service = AssistantService(db)
    session = await service.get_session(
        session_id=session_id,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
    )
    return SuccessResponse(data=service.to_session_response(session))


@router.get("/sessions/{session_id}/messages", response_model=ResponseBase[list[MessageResponse]])
async def list_session_messages(
    session_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    limit: int = Query(100, ge=1, le=200),
) -> dict[str, Any]:
    service = AssistantService(db)
    messages = await service.list_session_messages(
        session_id=session_id,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        limit=limit,
    )
    return SuccessResponse(data=messages)


@router.delete("/sessions/{session_id}", response_model=ResponseBase[None])
async def delete_session(
    session_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    service = AssistantService(db)
    await service.delete_session(
        session_id=session_id,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
    )
    return SuccessResponse(data=None, message="会话已删除")


@router.get("/context", response_model=ResponseBase[ContextResponse])
async def get_context(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    route: str = Query(..., description="当前路由"),
    context: str | None = Query(None, description="上下文参数(JSON)"),
) -> dict[str, Any]:
    route_path = _normalize_route_path(route)
    context_params = _parse_context_query(context)
    tenant = await TenantService(db).get_by_id(tenant_ctx.tenant_id)
    assistant_config = await _resolve_effective_assistant_config(
        db=db,
        tenant_id=tenant_ctx.tenant_id,
        tenant_config=tenant.config if tenant and isinstance(tenant.config, dict) else None,
    )

    viewer_team_ids = await _get_user_team_ids(db, tenant_id=tenant_ctx.tenant_id, user_id=current_user.id)
    read_team_ids = _resolve_team_ids(data_scope)
    adapter = _resolve_adapter(route_path)
    capability_config = _extract_capability_config(assistant_config)
    context_data = await _load_adapter_context_data(
        adapter=adapter,
        route_path=route_path,
        context_params=context_params,
        db=db,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        viewer_team_ids=viewer_team_ids,
        read_team_ids=read_team_ids,
        capability_config=capability_config,
    )
    payload = ContextResponse(
        module_code=adapter.module_code,
        module_name=adapter.module_name,
        route_path=route_path,
        data=context_data,
    )
    return SuccessResponse(data=payload.model_dump(by_alias=True))


@router.get("/presets", response_model=ResponseBase[PresetsResponse])
async def get_presets(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
    route: str = Query(..., description="当前路由"),
    context: str | None = Query(None, description="上下文参数(JSON)"),
) -> dict[str, Any]:
    route_path = _normalize_route_path(route)
    context_params = _parse_context_query(context)
    adapter = _resolve_adapter(route_path)
    viewer_team_ids = await _get_user_team_ids(db, tenant_id=tenant_ctx.tenant_id, user_id=current_user.id)
    read_team_ids = _resolve_team_ids(data_scope)
    presets = await adapter.get_presets(
        route_path,
        context_params,
        db=db,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        viewer_team_ids=viewer_team_ids,
        read_team_ids=read_team_ids,
    )
    payload = PresetsResponse(
        module_code=adapter.module_code,
        module_name=adapter.module_name,
        route_path=route_path,
        presets=presets,
    )
    return SuccessResponse(data=payload.model_dump(by_alias=True))


@router.post("/chat/reply", response_model=ResponseBase[ChatReplyResponse])
async def chat_reply(
    data: ChatReplyRequest,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
) -> dict[str, Any]:
    service = AssistantService(db)
    result = await service.chat_reply(
        session_id=data.session_id,
        message=data.message,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        team_ids=_resolve_team_ids(data_scope),
        route_path=data.route_path,
        context_params=data.context_params,
    )
    return SuccessResponse(data=result)


@router.post("/actions/execute", response_model=ResponseBase[ActionResponse])
async def execute_action(
    data: ActionRequest,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
) -> dict[str, Any]:
    service = AssistantService(db)
    result = await service.execute_action(
        session_id=data.session_id,
        action_type=data.action_type,
        params=data.params,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        team_ids=_resolve_team_ids(data_scope),
    )
    return SuccessResponse(data=result)


@router.post("/chat", response_model=None)
async def chat_stream(
    data: AssistantChatRequest,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,
    db: DBSession,
) -> Any:
    if data.session_id is not None:
        service = AssistantService(db)

        async def generate():
            async for chunk in service.chat_stream(
                session_id=data.session_id,
                message=data.message,
                tenant_id=tenant_ctx.tenant_id,
                user_id=current_user.id,
                team_ids=_resolve_team_ids(data_scope),
                route_path=data.route_path,
                context_params=data.context_params,
            ):
                yield f"data: {chunk}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    return await _legacy_chat_stream(
        data=data,
        current_user=current_user,
        tenant_ctx=tenant_ctx,
        data_scope=data_scope,
        db=db,
    )
