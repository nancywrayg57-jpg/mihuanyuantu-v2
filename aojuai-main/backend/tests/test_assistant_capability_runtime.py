from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.assistant.capability_runtime import (
    build_assistant_capability_context,
    build_assistant_capability_context_text,
    execute_assistant_builtin_tool,
)
from app.domain.assistant.config_service import AssistantConfigService
from app.domain.assistant.service import AssistantService


@pytest.mark.asyncio
async def test_assistant_config_view_exposes_default_capabilities() -> None:
    service = AssistantConfigService(SimpleNamespace())
    service.get_config = AsyncMock(return_value=None)  # type: ignore[method-assign]

    payload = (await service.get_config_view(tenant_id=7)).model_dump(by_alias=True)

    assert payload["capabilities"]["policy"]["requireConfirmationForWrites"] is True
    assert payload["capabilities"]["policy"]["maxVisibleTools"] == 8
    assert payload["capabilities"]["toolBindings"][0]["id"] == "time.now"
    assert payload["capabilities"]["skillBindings"][0]["id"] == "core.context_reader"


def test_assistant_capability_context_compacts_runtime_and_module_capabilities() -> None:
    context = build_assistant_capability_context(
        capability_config={
            "toolBindings": [
                {"id": "time.now", "enabled": True},
                {"id": "time.range.resolve", "enabled": True},
                {"id": "session.scope.inspect", "enabled": True},
            ],
            "skillBindings": [
                {"id": "core.context_reader", "enabled": True},
                {"id": "core.permission_boundary", "enabled": True},
            ],
            "policy": {
                "maxVisibleTools": 4,
                "requireConfirmationForWrites": True,
                "exposeModuleCapabilityManifest": True,
            },
            "memory": {
                "workingSummary": "当前优先回答页面查询与导航问题。",
                "profile": {
                    "preferredStyle": "简洁直接",
                },
            },
        },
        module_code="workspace",
        route_path="/workspace/detail/12",
        context_data={
            "currentRoleProfile": {"id": "reviewer", "label": "审阅者", "actorKind": "reviewer"},
            "skillPacks": [
                {
                    "id": "workspace.page_orienter",
                    "label": "页面理解扩展",
                    "description": "围绕当前工作台页面的信息解读、下一步建议和动作入口说明提供支持。",
                    "available": True,
                    "availableToolIds": [
                        "workspace.page.read",
                        "workspace.page.confirm",
                    ],
                }
            ],
            "toolCatalog": [
                {
                    "id": "workspace.page.read",
                    "label": "读取页面摘要",
                    "available": True,
                    "mode": "query",
                    "resource": "page",
                },
                {
                    "id": "workspace.page.confirm",
                    "label": "确认页面动作",
                    "available": True,
                    "mode": "mutation",
                    "resource": "page",
                },
            ],
            "capabilityManifest": {
                "resourceSummary": [{"resource": "page", "count": 2}],
                "lifecycleSummary": [{"mode": "query", "count": 1}, {"mode": "mutation", "count": 1}],
                "recommendedToolIds": ["workspace.page.read"],
            },
            "operationPolicy": {
                "auth": "All actions must run on server-side current user identity.",
                "writeGuard": "Mutation requires explicit confirmation.",
            },
        },
        user_id=11,
        viewer_team_ids=[2, 3],
        read_team_ids=[3],
    )

    assert context["runtime"]["timeRanges"]["nextWeek"]["startDate"]
    assert context["moduleCapabilities"]["currentRoleProfile"]["label"] == "审阅者"
    assert context["moduleCapabilities"]["skillPacks"][0]["id"] == "workspace.page_orienter"
    assert context["moduleCapabilities"]["availableTools"][0]["id"] == "workspace.page.read"

    text = build_assistant_capability_context_text(context)
    assert "tool.time.range.resolve" in text
    assert "页面理解扩展" in text
    assert "workspace.page.read" in text
    assert "当前角色画像：审阅者" in text
    assert "working summary: 当前优先回答页面查询与导航问题。" in text


@pytest.mark.asyncio
async def test_execute_assistant_builtin_tool_supports_time_range_and_scope() -> None:
    range_result = await execute_assistant_builtin_tool(
        action_type="time.range.resolve",
        params={"text": "下周有哪些安排"},
        route_path="/workspace/detail/12",
        module_code="workspace",
        context_data={},
        user_id=18,
        viewer_team_ids=[1, 2],
        read_team_ids=[2],
    )

    assert range_result is not None
    assert range_result.success is True
    assert range_result.data["rangeId"] == "nextWeek"
    assert range_result.data["startDate"]
    assert range_result.data["endDate"]

    scope_result = await execute_assistant_builtin_tool(
        action_type="session.scope.inspect",
        params={},
        route_path="/workspace/detail/9",
        module_code="workspace",
        context_data={},
        user_id=18,
        viewer_team_ids=[1, 2],
        read_team_ids=[2],
    )

    assert scope_result is not None
    assert scope_result.success is True
    assert scope_result.data["routePath"] == "/workspace/detail/9"
    assert scope_result.data["readTeamIds"] == [2]


def test_assistant_system_prompt_includes_capability_block() -> None:
    prompt = AssistantService._build_system_prompt(
        system_prompt="系统提示",
        module_prompt="模块提示",
        write_guard_prompt="写入守卫",
        module_name="工作台助手",
        route_path="/workspace/detail/12",
        context_data={"hello": "world"},
        capability_context_text="- tool.time.now\n  当前时间：2026-03-28T12:00",
    )

    assert "【能力框架】" in prompt
    assert "tool.time.now" in prompt
    assert "【当前页面契约】" in prompt
