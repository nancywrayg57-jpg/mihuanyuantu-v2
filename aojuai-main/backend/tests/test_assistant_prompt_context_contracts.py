from __future__ import annotations

from typing import Any

import pytest

from app.domain.assistant.action_protocol import (
    build_action_execution_history_suffix,
    normalize_assistant_action,
    sanitize_streaming_assistant_text,
)
from app.domain.assistant.adapters.base import ActionResult, ModuleAdapterBase
from app.domain.assistant.adapters.default import DefaultAdapter
from app.domain.assistant.route_directory_service import AssistantScopeDirectoryService
from app.domain.assistant.service import AssistantService
from app.infrastructure.cache.runtime_cache import delete_prefix


def test_action_execution_history_suffix_summarizes_query_context() -> None:
    suffix = build_action_execution_history_suffix(
        {
            "actionType": "training.project.list",
            "success": True,
            "message": "查询成功",
            "result": {
                "items": [{"id": index, "name": f"项目{index}"} for index in range(1, 21)],
                "queryContext": {
                    "toolId": "training.project.list",
                    "appliedParams": {"keyword": "AI", "page": 1, "pageSize": 20},
                    "filterParams": {"keyword": "AI"},
                    "success": True,
                    "returnedCount": 20,
                    "totalCount": 31,
                    "emptyResult": False,
                    "remainingCount": 11,
                },
            },
        }
    )

    assert '"remainingCount": 11' in suffix
    assert '"items"' not in suffix


def test_assistant_service_build_system_prompt_includes_prior_query_state_blocks() -> None:
    prompt = AssistantService._build_system_prompt(
        system_prompt="系统提示",
        module_prompt="模块提示",
        write_guard_prompt="写入守卫",
        module_name="培训助手",
        route_path="/training/project/index",
        prompt_context={"hello": "world"},
        prior_action={
            "toolId": "training.project.list",
            "mode": "ready",
            "summary": "准备查询培训项目列表",
            "confirmationRequired": False,
            "canExecute": True,
            "collectedParams": {
                "keyword": "AI",
                "_assistantLastActionExecution": {
                    "actionType": "training.project.list",
                    "success": True,
                    "result": {
                        "queryContext": {
                            "toolId": "training.project.list",
                            "appliedParams": {"keyword": "AI", "page": 1, "pageSize": 20},
                            "filterParams": {"keyword": "AI"},
                            "success": True,
                            "returnedCount": 20,
                            "totalCount": 31,
                            "emptyResult": False,
                            "remainingCount": 11,
                        },
                    },
                },
            },
        },
    )

    assert "【上一轮动作摘要】" in prompt
    assert "【上一轮真实执行摘要】" in prompt
    assert '"remainingCount": 11' in prompt
    assert "不要擅自扩大查询范围" in prompt
    assert "不要输出 assistantAction" in prompt


def test_assistant_action_protocol_keeps_navigation_fields_structured() -> None:
    action = normalize_assistant_action(
        {
            "assistantAction": {
                "toolId": "page.router.navigate",
                "summary": "已为你定位到系统用户页面。",
                "targetRoutePath": "/system/user",
                "targetModuleCode": "system",
                "canExecute": True,
                "confirmationRequired": False,
            }
        }
    )

    assert action is not None
    assert action["toolId"] == "page.router.navigate"
    assert action["toolLabel"] == "前往目标页面"
    assert action["targetRoutePath"] == "/system/user"
    assert action["confirmText"] == "前往页面"


def test_streaming_sanitizer_hides_action_protocol_tail() -> None:
    visible = sanitize_streaming_assistant_text(
        '已为你定位到系统用户页面。\n{"assistantAction":{"toolId":"page.router.navigate","targetRoutePath":"/system/user"}}'
    )

    assert visible == "已为你定位到系统用户页面。"


def test_scope_directory_resolves_real_module_when_adapter_is_default() -> None:
    directory = AssistantScopeDirectoryService(db=None)
    payload = directory._build_scope_directory_from_snapshot(
        current_route_path="/speech",
        current_module_code="default",
        current_module_name="通用助手",
        navigation_snapshot={
            "accessibleRoutes": [
                {
                    "routePath": "/speech",
                    "title": "语音设置",
                    "isVisible": True,
                    "canNavigate": True,
                }
            ]
        },
    )

    assert payload["currentScope"]["moduleCode"] == "speech"
    assert payload["currentScope"]["moduleName"] == "语音能力"


@pytest.mark.asyncio
async def test_scope_directory_reuses_cached_navigation_snapshot() -> None:
    await delete_prefix("assistant_scope_directory:")

    class CountingDirectory(AssistantScopeDirectoryService):
        calls = 0

        async def _load_navigation_snapshot(self, *, tenant_id: int, user_id: int) -> dict[str, Any]:
            self.__class__.calls += 1
            return {
                "accessibleRoutes": [
                    {
                        "routePath": "/system/user",
                        "title": "用户管理",
                        "isVisible": True,
                        "canNavigate": True,
                    }
                ]
            }

    directory = CountingDirectory(db=object())
    first = await directory.build_scope_directory(tenant_id=1, user_id=99, current_route_path="/system/user")
    second = await directory.build_scope_directory(tenant_id=1, user_id=99, current_route_path="/system/role")

    assert CountingDirectory.calls == 1
    assert first["currentScope"]["item"]["routePath"] == "/system/user"
    assert second["globalScope"]["count"] == 1


def test_assistant_service_build_prompt_context_payload_surfaces_compact_prior_query_state() -> None:
    payload = AssistantService._build_prompt_context_payload(
        adapter=DefaultAdapter(),
        module_code="training",
        module_name="培训助手",
        route_path="/training/project/index",
        context_data={
            "scope": {"id": "training-admin", "label": "培训后台"},
            "toolCatalog": [
                {
                    "id": "training.project.list",
                    "label": "查询项目",
                    "summary": "查询项目。",
                    "status": "active",
                    "toolType": "query",
                    "available": True,
                    "confirmationRequired": False,
                    "params": [],
                }
            ],
        },
        prior_action={
            "version": 1,
            "toolId": "training.project.list",
            "mode": "ready",
            "summary": "准备查询培训项目列表",
            "confirmationRequired": False,
            "canExecute": True,
            "collectedParams": {
                "keyword": "AI",
                "_assistantLastActionExecution": {
                    "actionType": "training.project.list",
                    "success": True,
                    "result": {
                        "items": [{"id": index, "name": f"项目{index}"} for index in range(1, 21)],
                        "queryContext": {
                            "toolId": "training.project.list",
                            "appliedParams": {"keyword": "AI", "page": 1, "pageSize": 20},
                            "filterParams": {"keyword": "AI"},
                            "success": True,
                            "returnedCount": 20,
                            "totalCount": 31,
                            "emptyResult": False,
                            "remainingCount": 11,
                        },
                    },
                },
            },
            "missingFields": [],
        },
    )

    assert payload["priorAction"] == {
        "toolId": "training.project.list",
        "mode": "ready",
        "summary": "准备查询培训项目列表",
        "confirmationRequired": False,
        "canExecute": True,
        "collectedParams": {"keyword": "AI"},
    }
    assert payload["priorExecution"]["result"]["queryContext"]["filterParams"] == {"keyword": "AI"}
    assert payload["priorExecution"]["result"]["queryContext"]["remainingCount"] == 11
    assert "items" not in payload["priorExecution"]["result"]


def test_module_adapter_base_build_prompt_context_uses_lightweight_tool_catalog() -> None:
    class FakeAdapter(ModuleAdapterBase):
        module_code = "fake"
        module_name = "Fake"
        supported_routes = ["/fake*"]

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
            return {}

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
        ) -> list[Any]:
            return []

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
            return ActionResult(success=True)

    adapter = FakeAdapter()
    context_data = adapter.build_prompt_context(
        module_code="fake",
        module_name="Fake",
        route="/fake/index",
        context_data={
            "currentRoleProfile": {
                "id": "fake-admin",
                "availableToolIds": ["fake.project.list"],
            },
            "capabilityManifest": {
                "recommendedToolIds": ["fake.user.list"],
            },
            "toolCatalog": [
                {
                    "id": "fake.user.list",
                    "label": "查询用户",
                    "summary": "查询用户列表。",
                    "status": "active",
                    "toolType": "query",
                    "available": True,
                    "confirmationRequired": False,
                    "params": [
                        {
                            "key": "keyword",
                            "label": "关键词",
                            "type": "string",
                            "required": False,
                            "description": "按名称筛选。",
                            "examples": ["张三"],
                        }
                    ],
                },
                {
                    "id": "fake.project.list",
                    "label": "查询项目",
                    "summary": "查询项目列表。",
                    "status": "active",
                    "toolType": "query",
                    "available": True,
                    "confirmationRequired": False,
                    "params": [
                        {
                            "key": "status",
                            "label": "状态",
                            "type": "number",
                            "required": False,
                            "description": "项目状态。",
                            "examples": ["1"],
                        }
                    ],
                },
            ],
        },
    )

    assert context_data["toolCatalog"] == [
        {
            "id": "fake.user.list",
            "label": "查询用户",
            "summary": "查询用户列表。",
            "toolType": "query",
            "resource": "",
            "confirmationRequired": False,
        },
        {
            "id": "fake.project.list",
            "label": "查询项目",
            "summary": "查询项目列表。",
            "toolType": "query",
            "resource": "",
            "confirmationRequired": False,
        },
    ]
