from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.assistant import capability_registry as capability_registry_mod
from app.domain.assistant import toolset_registry as toolset_registry_mod
from app.domain.assistant.adapters import AdapterRegistry
from app.domain.assistant.adapters.base import ActionResult
from app.domain.assistant.adapters.default import DefaultAdapter
from app.domain.assistant.capability_registry import (
    AssistantCapabilityProviderSpec,
    build_provider_capability_source,
    register_assistant_capability_provider,
)
from app.domain.assistant.execution_planner import AssistantExecutionPlanner
from app.domain.assistant.models import MessageRole
from app.domain.assistant.route_directory_service import AssistantScopeDirectoryService
from app.domain.assistant.router_service import AssistantRouteDecision, AssistantRouterService, routing_state_key
from app.domain.assistant.service import AssistantService
from app.domain.assistant.tool_schema import assistant_tool, assistant_tool_execution_binding
from app.domain.assistant.toolset_registry import AssistantModuleToolsetSpec, register_assistant_module_toolset
from app.domain.notifications.gateway_service import (
    MESSAGE_CHANNEL_ASSISTANT_ROUTE,
    _message_channel_assistant_session_matches,
)


@pytest.mark.asyncio
async def test_assistant_router_routes_message_channel_text_to_catalog_module() -> None:
    decision = await AssistantRouterService(db=None).route_turn(
        message="打开语音能力",
        current_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params={"source": "message_channel"},
        session_context={},
        tenant_id=1,
        user_id=9,
    )

    assert decision is not None
    assert decision.module_code == "speech"
    assert decision.route_path == "/speech"


@pytest.mark.asyncio
async def test_assistant_router_skips_scope_directory_for_message_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_scope_directory(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("message channel routing must not load page scope directory")

    monkeypatch.setattr(AssistantScopeDirectoryService, "build_scope_directory", fail_scope_directory)

    decision = await AssistantRouterService(db=None).route_turn(
        message="打开语音能力",
        current_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params={"source": "message_channel"},
        session_context={},
        tenant_id=1,
        user_id=9,
    )

    assert decision is not None
    assert decision.module_code == "speech"
    assert decision.source == "catalog"


@pytest.mark.asyncio
async def test_execution_planner_routes_text_entry_to_module_tool_intent() -> None:
    credits_plan = await AssistantExecutionPlanner(db=None).plan_turn(
        message="查询下我的积分",
        current_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params={"source": "message_channel"},
        session_context={},
        tenant_id=1,
        user_id=9,
    )
    users_plan = await AssistantExecutionPlanner(db=None).plan_turn(
        message="当前有多少用户",
        current_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params={"source": "message_channel"},
        session_context={},
        tenant_id=1,
        user_id=9,
    )

    assert credits_plan is not None
    assert credits_plan.module_code == "credits"
    assert credits_plan.route_path == "/personal/credits"
    assert credits_plan.tool_id == "credits.my_account.get"
    assert credits_plan.auto_execute is True
    assert users_plan is not None
    assert users_plan.module_code == "users"
    assert users_plan.route_path == "/system/user"
    assert users_plan.tool_id == "users.count"
    assert users_plan.auto_execute is True


@pytest.mark.asyncio
async def test_execution_planner_self_discovers_registered_provider_toolset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(toolset_registry_mod, "_ASSISTANT_MODULE_TOOLSETS", {})
    monkeypatch.setattr(capability_registry_mod, "_ASSISTANT_CAPABILITY_PROVIDERS", {})

    register_assistant_module_toolset(
        AssistantModuleToolsetSpec(
            module_code="example",
            tool_schemas=(
                assistant_tool(
                    "example.points.balance",
                    "查询我的积分余额",
                    "读取当前登录用户自己的积分余额。",
                    scope_ids=["example-user"],
                    examples=["查询我的积分", "我还有多少积分"],
                    tool_type="query",
                    resource="points",
                    access_mode="read",
                ),
            ),
        )
    )
    register_assistant_capability_provider(
        AssistantCapabilityProviderSpec(
            module_code="example",
            scope_rules=[("/example/points", {"id": "example-user", "label": "示例用户"})],
            toolset_module_code="example",
            role_profiles=[
                {
                    "id": "example-user",
                    "label": "示例用户",
                    "preferredToolIds": ["example.points.balance"],
                }
            ],
        )
    )

    class ExampleAdapter(DefaultAdapter):
        module_code = "example"
        module_name = "示例模块"
        supported_routes = ["/example*"]

    monkeypatch.setattr(AdapterRegistry, "list_all", classmethod(lambda _cls: [ExampleAdapter()]))

    plan = await AssistantExecutionPlanner(db=None).plan_turn(
        message="查询我的积分",
        current_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params={"source": "message_channel"},
        session_context={},
        tenant_id=1,
        user_id=9,
    )

    assert plan is not None
    assert plan.module_code == "example"
    assert plan.route_path == "/example/points"
    assert plan.tool_id == "example.points.balance"
    assert plan.auto_execute is True


def test_provider_capability_source_filters_registered_tools_by_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(toolset_registry_mod, "_ASSISTANT_MODULE_TOOLSETS", {})
    monkeypatch.setattr(capability_registry_mod, "_ASSISTANT_CAPABILITY_PROVIDERS", {})
    register_assistant_module_toolset(
        AssistantModuleToolsetSpec(
            module_code="example",
            tool_schemas=(
                assistant_tool(
                    "example.user.count",
                    "统计用户数量",
                    "按当前账号权限统计用户数量。",
                    scope_ids=["example-admin"],
                    required_permissions=["user:list"],
                    tool_type="query",
                    resource="users",
                    access_mode="read",
                ),
            ),
        )
    )
    provider = register_assistant_capability_provider(
        AssistantCapabilityProviderSpec(
            module_code="example",
            scope_rules=[("/example/users", {"id": "example-admin", "label": "示例管理员"})],
            toolset_module_code="example",
            role_profiles=[
                {
                    "id": "example-admin",
                    "label": "示例管理员",
                    "preferredToolIds": ["example.user.count"],
                }
            ],
        )
    )

    denied = build_provider_capability_source(provider, set(), "/example/users")
    allowed = build_provider_capability_source(provider, {"user:list"}, "/example/users")

    assert denied["toolCatalog"][0]["available"] is False
    assert denied["toolCatalog"][0]["availabilityReason"] == "当前账号缺少所需权限"
    assert allowed["toolCatalog"][0]["available"] is True
    assert allowed["currentRoleProfile"]["availableToolIds"] == ["example.user.count"]


@pytest.mark.asyncio
async def test_message_channel_chat_reply_uses_effective_route_but_keeps_channel_session_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.ensure_enabled",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_config",
        AsyncMock(return_value=SimpleNamespace(config={}, deduct_credits=False, credits_per_call=0)),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_provider_settings",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        AssistantRouterService,
        "route_turn",
        AsyncMock(
            return_value=AssistantRouteDecision(
                route_path="/speech",
                module_code="speech",
                module_name="语音能力",
                confidence=260,
                source="catalog",
                reason="测试路由",
            )
        ),
    )

    class FakeDB:
        def __init__(self) -> None:
            self.items: list[object] = []

        def add(self, item: object) -> None:
            self.items.append(item)

        async def commit(self) -> None:
            return None

    session = SimpleNamespace(
        id=101,
        module_code="default",
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data={
            "source": "message_channel",
            "channelType": "wechat",
            "channelId": 18,
            "externalUserId": "wx-user",
            "conversationId": "wx-session",
            "boundUserId": 7,
            "boundTenantId": 3,
        },
    )
    context_params = dict(session.context_data)
    get_context = AsyncMock(
        return_value=SimpleNamespace(
            module_code="speech",
            module_name="语音能力",
            route_path="/speech",
            data={"toolCatalog": []},
        )
    )
    get_presets = AsyncMock(return_value=SimpleNamespace(presets=[]))

    service = AssistantService(FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))
    monkeypatch.setattr(service, "get_context", get_context)
    monkeypatch.setattr(service, "get_presets", get_presets)
    monkeypatch.setattr(service, "_get_user_team_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_get_last_assistant_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_build_chat_messages", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_infer_best_adapter_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_select_canonical_assistant_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_resolve_adapter", lambda route: DefaultAdapter())

    response = await service.chat_reply(
        session_id=101,
        message="打开语音能力",
        tenant_id=3,
        user_id=7,
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params=context_params,
    )

    assert get_context.await_args.kwargs["route_path"] == "/speech"
    assert get_context.await_args.kwargs["context_params"][routing_state_key()]["activeRoutePath"] == "/speech"
    assert response.route_path == "/speech"
    assert session.module_code == "speech"
    assert session.route_path == MESSAGE_CHANNEL_ASSISTANT_ROUTE
    assert session.context_data[routing_state_key()]["activeRoutePath"] == "/speech"
    assert session.context_data["_assistantMemory"]["activeRoutePath"] == "/speech"
    assert _message_channel_assistant_session_matches(
        route_path=session.route_path,
        context_data=session.context_data,
        channel=SimpleNamespace(id=18, user_id=7),
        channel_type="wechat",
        external_user_id="wx-user",
        conversation_id="wx-session",
        tenant_id=3,
    )


@pytest.mark.asyncio
async def test_chat_reply_auto_executes_planned_read_action_without_page_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.ensure_enabled",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_config",
        AsyncMock(return_value=SimpleNamespace(config={}, deduct_credits=False, credits_per_call=0)),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_provider_settings",
        AsyncMock(return_value=None),
    )

    class FakeDB:
        def __init__(self) -> None:
            self.items: list[object] = []

        def add(self, item: object) -> None:
            self.items.append(item)

        async def commit(self) -> None:
            return None

    class FakeCreditsAdapter:
        module_code = "credits"
        module_name = "积分"
        default_chat_prompt = None
        prefer_inferred_action_on_conflict = False

        async def execute_action(self, action: str, params: dict, **_: object) -> ActionResult:
            assert action == "credits.my_account.get"
            assert params["routePath"] == "/personal/credits"
            return ActionResult(
                success=True,
                data={"account": {"balance": "42"}},
                message="你的当前积分余额为 42。",
            )

    action = {
        "toolId": "credits.my_account.get",
        "toolLabel": "查询我的积分",
        "mode": "ready",
        "summary": "准备查询当前登录用户自己的积分余额。",
        "confirmationRequired": False,
        "canExecute": True,
        "autoExecute": True,
        "collectedParams": {},
        "missingFields": [],
    }
    action_context = {
        "toolCatalog": [
            {
                "id": "credits.my_account.get",
                "available": True,
                "accessMode": "read",
                "toolType": "query",
                "mode": "query",
                "confirmationRequired": False,
            }
        ]
    }
    session = SimpleNamespace(
        id=202,
        module_code="default",
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data={"source": "message_channel", "channelId": 18},
    )
    context_params = dict(session.context_data)
    fake_db = FakeDB()
    service = AssistantService(fake_db)  # type: ignore[arg-type]
    fake_adapter = FakeCreditsAdapter()

    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))
    monkeypatch.setattr(service, "_resolve_effective_turn_route", AsyncMock(return_value=("/personal/credits", context_params)))
    monkeypatch.setattr(
        service,
        "get_context",
        AsyncMock(
            return_value=SimpleNamespace(
                module_code="credits",
                module_name="积分",
                route_path="/personal/credits",
                data=action_context,
            )
        ),
    )
    monkeypatch.setattr(service, "get_presets", AsyncMock(return_value=SimpleNamespace(presets=[])))
    monkeypatch.setattr(service, "_get_user_team_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_get_last_assistant_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_resolve_prompt_stack", AsyncMock(return_value={"system": "", "moduleChat": "", "writeGuard": ""}))
    monkeypatch.setattr(service, "_build_chat_messages", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_infer_best_adapter_action", AsyncMock(return_value=action))
    monkeypatch.setattr(service, "_load_action_guard_context", AsyncMock(return_value=action_context))
    monkeypatch.setattr(service, "_resolve_adapter", lambda _route: fake_adapter)

    response = await service.chat_reply(
        session_id=202,
        message="查询下我的积分",
        tenant_id=1,
        user_id=7,
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params=context_params,
    )

    assert response.reply == "你的当前积分余额为 42。"
    assistant_messages = [item for item in fake_db.items if getattr(item, "role", None) == MessageRole.ASSISTANT.value]
    assert assistant_messages
    action_result = assistant_messages[-1].action_result
    assert action_result["assistantAction"]["toolId"] == "credits.my_account.get"
    assert action_result["actionExecution"]["result"]["account"]["balance"] == "42"


@pytest.mark.asyncio
async def test_chat_reply_preserves_preplanned_tool_action_after_model_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.ensure_enabled",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_config",
        AsyncMock(return_value=SimpleNamespace(config={}, deduct_credits=False, credits_per_call=0)),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_provider_settings",
        AsyncMock(return_value={"base_url": "https://example.com/v1", "api_key": "sk-test", "model": "test", "temperature": 0, "max_tokens": 32}),
    )

    class FakeDB:
        def __init__(self) -> None:
            self.items: list[object] = []

        def add(self, item: object) -> None:
            self.items.append(item)

        async def commit(self) -> None:
            return None

    class FakeCreditsAdapter:
        module_code = "credits"
        module_name = "积分"
        default_chat_prompt = None
        prefer_inferred_action_on_conflict = False

        async def execute_action(self, action: str, params: dict, **_: object) -> ActionResult:
            assert action == "credits.my_account.get"
            return ActionResult(
                success=True,
                data={"account": {"balance": "42"}},
                message="你的当前积分余额为 42。",
            )

    action_context = {
        "toolCatalog": [
            {
                "id": "credits.my_account.get",
                "available": True,
                "accessMode": "read",
                "toolType": "query",
                "mode": "query",
                "confirmationRequired": False,
            }
        ]
    }
    session = SimpleNamespace(
        id=212,
        module_code="default",
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data={"source": "message_channel", "channelId": 18},
    )
    context_params = dict(session.context_data)
    context_params[routing_state_key()] = {
        "activeRoutePath": "/personal/credits",
        "activeModuleCode": "credits",
        "activeModuleName": "积分",
        "activeToolId": "credits.my_account.get",
        "autoExecute": True,
        "source": "ai_planner",
        "reason": "AI planner 选择积分查询工具。",
    }
    service = AssistantService(FakeDB())  # type: ignore[arg-type]
    fake_adapter = FakeCreditsAdapter()

    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))
    monkeypatch.setattr(service, "_resolve_effective_turn_route", AsyncMock(return_value=("/personal/credits", context_params)))
    monkeypatch.setattr(
        service,
        "get_context",
        AsyncMock(
            return_value=SimpleNamespace(
                module_code="credits",
                module_name="积分",
                route_path="/personal/credits",
                data=action_context,
            )
        ),
    )
    monkeypatch.setattr(service, "get_presets", AsyncMock(return_value=SimpleNamespace(presets=[])))
    monkeypatch.setattr(service, "_get_user_team_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_get_last_assistant_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_resolve_prompt_stack", AsyncMock(return_value={"system": "", "moduleChat": "", "writeGuard": ""}))
    monkeypatch.setattr(service, "_build_chat_messages", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_infer_best_adapter_action", AsyncMock(side_effect=AssertionError("local inference must not run")))
    monkeypatch.setattr(service, "_load_action_guard_context", AsyncMock(return_value=action_context))
    monkeypatch.setattr(service, "_call_ai_reply", AsyncMock(return_value=("我先查询一下。", True, {"total_tokens": 4})))
    monkeypatch.setattr(service, "_resolve_adapter", lambda _route: fake_adapter)

    response = await service.chat_reply(
        session_id=212,
        message="查询下我的积分",
        tenant_id=1,
        user_id=7,
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params=context_params,
    )

    assert response.reply == "你的当前积分余额为 42。"
    assert response.action is None
    assistant_messages = [item for item in service.db.items if getattr(item, "role", None) == MessageRole.ASSISTANT.value]
    assert assistant_messages[-1].action_result["assistantAction"]["toolId"] == "credits.my_account.get"


@pytest.mark.asyncio
async def test_chat_reply_rejects_unregistered_text_entry_without_ai_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.ensure_enabled",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_config",
        AsyncMock(return_value=SimpleNamespace(config={}, deduct_credits=False, credits_per_call=0)),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_provider_settings",
        AsyncMock(return_value=None),
    )

    class FakeDB:
        def __init__(self) -> None:
            self.items: list[object] = []

        def add(self, item: object) -> None:
            self.items.append(item)

        async def commit(self) -> None:
            return None

    session = SimpleNamespace(
        id=222,
        module_code="default",
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data={"source": "message_channel", "channelId": 18},
    )
    context_params = dict(session.context_data)
    fake_db = FakeDB()
    service = AssistantService(fake_db)  # type: ignore[arg-type]

    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))
    monkeypatch.setattr(service, "_resolve_effective_turn_route", AsyncMock(return_value=(MESSAGE_CHANNEL_ASSISTANT_ROUTE, context_params)))
    monkeypatch.setattr(
        service,
        "get_context",
        AsyncMock(
            return_value=SimpleNamespace(
                module_code="default",
                module_name="通用助手",
                route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
                data={"toolCatalog": []},
            )
        ),
    )
    monkeypatch.setattr(service, "get_presets", AsyncMock(return_value=SimpleNamespace(presets=[])))
    monkeypatch.setattr(service, "_get_user_team_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_get_last_assistant_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_infer_best_adapter_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_resolve_adapter", lambda _route: DefaultAdapter())

    response = await service.chat_reply(
        session_id=222,
        message="明天外部实时信息是什么",
        tenant_id=1,
        user_id=7,
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params=context_params,
    )

    assert response.used_ai is False
    assert response.context == {}
    assert "当前没有匹配到可调用的 AOJUAI 能力" in response.reply
    assistant_messages = [item for item in fake_db.items if getattr(item, "role", None) == MessageRole.ASSISTANT.value]
    assert assistant_messages[-1].action_result["boundary"] == "unmatched_text_entry"


@pytest.mark.asyncio
async def test_chat_stream_preserves_preplanned_tool_action_after_model_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.ensure_enabled",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_config",
        AsyncMock(return_value=SimpleNamespace(config={}, deduct_credits=False, credits_per_call=0)),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_provider_settings",
        AsyncMock(return_value={"base_url": "https://example.com/v1", "api_key": "sk-test", "model": "test", "temperature": 0, "max_tokens": 32, "stream": False}),
    )

    class FakeDB:
        def __init__(self) -> None:
            self.items: list[object] = []

        def add(self, item: object) -> None:
            self.items.append(item)

        async def commit(self) -> None:
            return None

    class FakeCreditsAdapter:
        module_code = "credits"
        module_name = "积分"
        default_chat_prompt = None
        prefer_inferred_action_on_conflict = False

        async def execute_action(self, action: str, params: dict, **_: object) -> ActionResult:
            assert action == "credits.my_account.get"
            return ActionResult(
                success=True,
                data={"account": {"balance": "42"}},
                message="你的当前积分余额为 42。",
            )

    action_context = {
        "toolCatalog": [
            {
                "id": "credits.my_account.get",
                "available": True,
                "accessMode": "read",
                "toolType": "query",
                "mode": "query",
                "confirmationRequired": False,
            }
        ]
    }
    session = SimpleNamespace(
        id=232,
        module_code="default",
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data={"source": "message_channel", "channelId": 18},
    )
    context_params = dict(session.context_data)
    context_params[routing_state_key()] = {
        "activeRoutePath": "/personal/credits",
        "activeModuleCode": "credits",
        "activeModuleName": "积分",
        "activeToolId": "credits.my_account.get",
        "autoExecute": True,
        "source": "ai_planner",
        "reason": "AI planner 选择积分查询工具。",
    }
    service = AssistantService(FakeDB())  # type: ignore[arg-type]
    fake_adapter = FakeCreditsAdapter()

    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))
    monkeypatch.setattr(service, "_resolve_effective_turn_route", AsyncMock(return_value=("/personal/credits", context_params)))
    monkeypatch.setattr(
        service,
        "get_context",
        AsyncMock(
            return_value=SimpleNamespace(
                module_code="credits",
                module_name="积分",
                route_path="/personal/credits",
                data=action_context,
            )
        ),
    )
    monkeypatch.setattr(service, "get_presets", AsyncMock(return_value=SimpleNamespace(presets=[])))
    monkeypatch.setattr(service, "_get_user_team_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_get_last_assistant_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_resolve_prompt_stack", AsyncMock(return_value={"system": "", "moduleChat": "", "writeGuard": ""}))
    monkeypatch.setattr(service, "_build_chat_messages", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_infer_best_adapter_action", AsyncMock(side_effect=AssertionError("local inference must not run")))
    monkeypatch.setattr(service, "_load_action_guard_context", AsyncMock(return_value=action_context))
    monkeypatch.setattr(service, "_call_ai_reply", AsyncMock(return_value=("我先查询一下。", True, {"total_tokens": 4})))
    monkeypatch.setattr(service, "_resolve_adapter", lambda _route: fake_adapter)

    payloads = [
        json.loads(chunk)
        async for chunk in service.chat_stream(
            session_id=232,
            message="查询下我的积分",
            tenant_id=1,
            user_id=7,
            route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
            context_params=context_params,
        )
    ]

    assert payloads[-1]["type"] == "done"
    assert payloads[-1]["reply"] == "你的当前积分余额为 42。"
    assert payloads[-1]["context"] == {}
    assert payloads[-1]["action"] is None


def test_select_assistant_action_does_not_hardcode_business_modules() -> None:
    extracted = {"toolId": "example.old", "summary": "模型抽取动作", "canExecute": True}
    inferred = {"toolId": "example.new", "summary": "运行时推断动作", "canExecute": True}

    default_selected = AssistantService._select_assistant_action(
        module_code="training",
        prefer_inferred_action_on_conflict=None,
        extracted_action=extracted,
        inferred_action=inferred,
    )
    explicit_selected = AssistantService._select_assistant_action(
        module_code="training",
        prefer_inferred_action_on_conflict=True,
        extracted_action=extracted,
        inferred_action=inferred,
    )

    assert default_selected is not None
    assert default_selected["toolId"] == "example.old"
    assert explicit_selected is not None
    assert explicit_selected["toolId"] == "example.new"


@pytest.mark.asyncio
async def test_execute_action_uses_active_scope_for_text_entry_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.ensure_enabled",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_config",
        AsyncMock(return_value=SimpleNamespace(config={})),
    )

    class FakeDB:
        def __init__(self) -> None:
            self.items: list[object] = []

        def add(self, item: object) -> None:
            self.items.append(item)

        async def commit(self) -> None:
            return None

    captured: dict[str, object] = {}

    class FakeCreditsAdapter:
        module_code = "credits"
        module_name = "积分"

        async def execute_action(self, action: str, params: dict, **_: object) -> ActionResult:
            captured["action"] = action
            captured["params"] = dict(params)
            return ActionResult(success=True, data={"ok": True}, message="已按积分模块执行。")

    action_context = {
        "toolCatalog": [
            {
                "id": "credits.my_account.get",
                "available": True,
                "accessMode": "read",
                "toolType": "query",
                "mode": "query",
                "confirmationRequired": False,
            }
        ]
    }
    session = SimpleNamespace(
        id=303,
        module_code="credits",
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data={
            "source": "message_channel",
            routing_state_key(): {
                "activeRoutePath": "/personal/credits",
                "activeModuleCode": "credits",
                "activeModuleName": "积分",
            },
        },
    )
    service = AssistantService(FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))
    monkeypatch.setattr(service, "_get_user_team_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_load_action_guard_context", AsyncMock(return_value=action_context))
    monkeypatch.setattr(service, "_resolve_adapter", lambda route: captured.setdefault("route", route) and FakeCreditsAdapter())

    response = await service.execute_action(
        session_id=303,
        action_type="credits.my_account.get",
        params={},
        tenant_id=1,
        user_id=7,
        team_ids=None,
    )

    assert response.success is True
    assert captured["route"] == "/personal/credits"
    assert captured["action"] == "credits.my_account.get"
    assert captured["params"]["routePath"] == "/personal/credits"
    assert captured["params"]["entryRoutePath"] == MESSAGE_CHANNEL_ASSISTANT_ROUTE


@pytest.mark.asyncio
async def test_execute_action_runtime_uses_registered_tool_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(toolset_registry_mod, "_ASSISTANT_MODULE_TOOLSETS", {})

    async def executor(**kwargs: object) -> ActionResult:
        params = kwargs["params"]
        assert isinstance(params, dict)
        assert params["routePath"] == "/example/points"
        return ActionResult(success=True, data={"balance": 88}, message="当前余额为 88。")

    register_assistant_module_toolset(
        AssistantModuleToolsetSpec(
            module_code="example",
            execution_bindings=(
                assistant_tool_execution_binding("example.points.balance", executor),
            ),
        )
    )

    class ExampleAdapter(DefaultAdapter):
        module_code = "example"
        module_name = "示例模块"
        supported_routes = ["/example*"]

        async def execute_action(self, action: str, params: dict, **_: object) -> ActionResult:
            return ActionResult(success=False, data={"fallback": True}, message="不应走 adapter fallback")

    result = await AssistantService(db=None)._execute_action_runtime(  # type: ignore[arg-type]
        adapter=ExampleAdapter(),
        action_type="example.points.balance",
        params={},
        route_path="/example/points",
        context_params={},
        action_context_data={
            "toolCatalog": [
                {
                    "id": "example.points.balance",
                    "available": True,
                    "accessMode": "read",
                    "toolType": "query",
                }
            ]
        },
        capability_config=None,
        tenant_id=1,
        user_id=7,
        viewer_team_ids=[],
        read_team_ids=None,
    )

    assert result.success is True
    assert result.data == {"balance": 88}
    assert result.message == "当前余额为 88。"


@pytest.mark.asyncio
async def test_delete_session_clears_session_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.ensure_enabled",
        AsyncMock(return_value=None),
    )

    class ScalarResult:
        def __init__(self, items: list[SimpleNamespace]) -> None:
            self.items = items

        def all(self) -> list[SimpleNamespace]:
            return self.items

    class ExecuteResult:
        def __init__(self, items: list[SimpleNamespace]) -> None:
            self.items = items

        def scalars(self) -> ScalarResult:
            return ScalarResult(self.items)

    class FakeDB:
        def __init__(self, items: list[SimpleNamespace]) -> None:
            self.items = items
            self.committed = False

        async def execute(self, _stmt: object) -> ExecuteResult:
            return ExecuteResult(self.items)

        async def commit(self) -> None:
            self.committed = True

    session = SimpleNamespace(id=303, deleted_at=None)
    messages = [SimpleNamespace(deleted_at=None), SimpleNamespace(deleted_at=None)]
    fake_db = FakeDB(messages)
    service = AssistantService(fake_db)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))

    await service.delete_session(session_id=303, tenant_id=1, user_id=7)

    assert session.deleted_at is not None
    assert all(item.deleted_at == session.deleted_at for item in messages)
    assert fake_db.committed is True


@pytest.mark.asyncio
async def test_build_chat_messages_uses_memory_and_recent_window() -> None:
    class ScalarResult:
        def __init__(self, items: list[SimpleNamespace]) -> None:
            self.items = items

        def all(self) -> list[SimpleNamespace]:
            return self.items

    class ExecuteResult:
        def __init__(self, items: list[SimpleNamespace]) -> None:
            self.items = items

        def scalars(self) -> ScalarResult:
            return ScalarResult(self.items)

    class FakeDB:
        def __init__(self, items: list[SimpleNamespace]) -> None:
            self.items = items

        async def execute(self, _stmt: object) -> ExecuteResult:
            return ExecuteResult(self.items)

    messages = [
        SimpleNamespace(
            id=index,
            role=MessageRole.USER.value,
            content=f"历史问题 {index}",
            action_result={"moduleCode": "training" if index <= 10 else "speech", "routePath": "/training" if index <= 10 else "/speech"},
        )
        for index in range(1, 23)
    ]
    service = AssistantService(FakeDB(list(reversed(messages))))  # type: ignore[arg-type]

    built_messages = await service._build_chat_messages(
        session_id=1,
        session_context={
            "_assistantMemory": {
                "workingSummary": "之前讨论过培训项目；后来切换到语音能力。",
                "recentModules": ["speech", "training"],
            }
        },
        active_module_code="speech",
        active_route_path="/speech",
    )

    assert built_messages[0]["role"] == "system"
    assert "压缩会话记忆" in built_messages[0]["content"]
    assert "已舍弃明细轮次：6" in built_messages[0]["content"]
    assert "之前讨论过培训项目" in built_messages[0]["content"]
    assert len(built_messages) == 17
    assert built_messages[1]["content"] == "历史问题 7"
    assert built_messages[-1]["content"] == "历史问题 22"


def test_last_assistant_action_scope_filter_rejects_other_module_action() -> None:
    action = {"toolId": "training.project.list", "summary": "准备查询培训项目"}
    assert AssistantService._assistant_action_matches_scope(
        action=action,
        action_result={"moduleCode": "training", "routePath": "/training/projects"},
        module_code="training",
        route_path="/training/projects",
    )
    assert not AssistantService._assistant_action_matches_scope(
        action=action,
        action_result={"moduleCode": "training", "routePath": "/training/projects"},
        module_code="speech",
        route_path="/speech",
    )


@pytest.mark.asyncio
async def test_text_entry_route_resets_stale_routing_when_no_module_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AssistantRouterService, "route_turn", AsyncMock(return_value=None))
    service = AssistantService(db=None)  # type: ignore[arg-type]
    session = SimpleNamespace(
        context_data={
            "source": "message_channel",
            routing_state_key(): {
                "activeRoutePath": "/assistant",
                "activeModuleCode": "assistant",
                "activeModuleName": "AI 助手",
            },
        }
    )

    effective_route, context_params = await service._resolve_effective_turn_route(
        session=session,  # type: ignore[arg-type]
        message="随便帮我安排一个项目日程",
        bound_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        bound_context_params={"source": "message_channel"},
        tenant_id=1,
        user_id=1,
    )

    assert effective_route == MESSAGE_CHANNEL_ASSISTANT_ROUTE
    assert context_params[routing_state_key()]["activeRoutePath"] == MESSAGE_CHANNEL_ASSISTANT_ROUTE
    assert context_params[routing_state_key()]["activeModuleCode"] is None
    assert context_params[routing_state_key()]["source"] == "text_entry"


@pytest.mark.asyncio
async def test_text_entry_route_does_not_reuse_business_scope_for_unmatched_new_topic() -> None:
    service = AssistantService(db=None)  # type: ignore[arg-type]
    session = SimpleNamespace(
        context_data={
            "source": "message_channel",
            routing_state_key(): {
                "activeRoutePath": "/personal/credits",
                "activeModuleCode": "credits",
                "activeModuleName": "积分",
                "source": "tool_intent",
            },
        }
    )

    effective_route, context_params = await service._resolve_effective_turn_route(
        session=session,  # type: ignore[arg-type]
        message="随便帮我安排一个项目日程",
        bound_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        bound_context_params={"source": "message_channel"},
        tenant_id=1,
        user_id=1,
    )

    assert effective_route == MESSAGE_CHANNEL_ASSISTANT_ROUTE
    assert context_params[routing_state_key()]["activeRoutePath"] == MESSAGE_CHANNEL_ASSISTANT_ROUTE
    assert context_params[routing_state_key()]["activeModuleCode"] is None
    assert context_params[routing_state_key()]["source"] == "text_entry"


@pytest.mark.asyncio
async def test_text_entry_route_reuses_business_scope_for_short_followup() -> None:
    service = AssistantService(db=None)  # type: ignore[arg-type]
    session = SimpleNamespace(
        context_data={
            "source": "message_channel",
            routing_state_key(): {
                "activeRoutePath": "/personal/credits",
                "activeModuleCode": "credits",
                "activeModuleName": "积分",
                "source": "tool_intent",
            },
        }
    )

    effective_route, context_params = await service._resolve_effective_turn_route(
        session=session,  # type: ignore[arg-type]
        message="明细呢",
        bound_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        bound_context_params={"source": "message_channel"},
        tenant_id=1,
        user_id=1,
    )

    assert effective_route == "/personal/credits"
    assert context_params[routing_state_key()]["activeRoutePath"] == "/personal/credits"
    assert context_params[routing_state_key()]["activeModuleCode"] == "credits"
    assert context_params[routing_state_key()]["source"] == "session_memory"


def test_session_memory_prefers_routed_business_module_over_default_adapter() -> None:
    memory = AssistantService._build_next_session_memory(
        existing_context={
            routing_state_key(): {
                "activeRoutePath": "/system/speech-settings",
                "activeModuleCode": "speech",
                "activeModuleName": "语音能力",
            }
        },
        module_code="default",
        module_name="通用助手",
        route_path="/system/speech-settings",
        user_message="打开语音能力",
        assistant_reply="已定位到语音能力。",
        assistant_action=None,
    )

    assert memory["activeModuleCode"] == "speech"
    assert memory["activeModuleName"] == "语音能力"
    assert memory["recentModules"] == ["speech"]


def test_navigation_action_aligns_with_router_effective_route() -> None:
    action = AssistantService._align_navigation_action_with_effective_route(
        {
            "toolId": "page.router.navigate",
            "targetRoutePath": "/system",
            "summary": "已为你定位到系统管理。",
            "canExecute": True,
        },
        entry_route_path="/assistant",
        effective_route_path="/system/user",
        context_params={
            routing_state_key(): {
                "activeRoutePath": "/system/user",
                "activeModuleCode": "system",
            }
        },
    )

    assert action is not None
    assert action["targetRoutePath"] == "/system/user"
    assert action["targetModuleCode"] == "system"


def test_planned_read_tool_action_preserves_routing_collected_params() -> None:
    action = AssistantService._planned_action_from_routing_state(
        context_params={
            routing_state_key(): {
                "activeRoutePath": "/training",
                "activeModuleCode": "training",
                "activeToolId": "training.teacher.list",
                "autoExecute": True,
                "reason": "查询内部讲师。",
                "collectedParams": {"sourceType": "internal"},
            }
        },
        context_data={
            "toolCatalog": [
                {
                    "id": "training.teacher.list",
                    "label": "查询讲师列表",
                    "available": True,
                    "accessMode": "read",
                }
            ]
        },
    )

    assert action is not None
    assert action["toolId"] == "training.teacher.list"
    assert action["collectedParams"] == {"sourceType": "internal"}


def test_foundation_context_overrides_stale_memory_active_scope_with_current_routing() -> None:
    context_data = AssistantService._attach_foundation_context(
        context_data={},
        entry_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        effective_route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_params={
            routing_state_key(): {
                "activeRoutePath": MESSAGE_CHANNEL_ASSISTANT_ROUTE,
                "activeModuleCode": None,
                "activeModuleName": None,
            },
            "_assistantMemory": {
                "activeRoutePath": "/assistant",
                "activeModuleCode": "assistant",
                "activeModuleName": "AI 助手",
                "workingSummary": "上一轮在 AI 助手模块。",
            },
        },
    )

    assert context_data["_assistantMemory"]["activeRoutePath"] == MESSAGE_CHANNEL_ASSISTANT_ROUTE
    assert "activeModuleCode" not in context_data["_assistantMemory"]
    assert "activeModuleName" not in context_data["_assistantMemory"]
    assert context_data["_assistantMemory"]["workingSummary"] == "上一轮在 AI 助手模块。"
