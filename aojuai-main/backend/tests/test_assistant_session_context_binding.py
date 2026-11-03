from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.assistant.adapters.default import DefaultAdapter
from app.domain.assistant.service import AssistantService


@pytest.mark.asyncio
async def test_assistant_service_chat_reply_uses_latest_route_context_for_existing_session(
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
        id=88,
        module_code="default",
        route_path="/dashboard",
        context_data={"tab": "overview"},
    )
    latest_route_path = "/projects/detail/2"
    latest_context_params = {"projectId": 2}
    get_context = AsyncMock(
        return_value=SimpleNamespace(
            module_code="default",
            module_name="通用助手",
            route_path=latest_route_path,
            data={"project": {"id": 2}},
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
        session_id=88,
        message="继续查看当前项目",
        tenant_id=1,
        user_id=9,
        team_ids=None,
        route_path=latest_route_path,
        context_params=latest_context_params,
    )

    assert get_context.await_args.kwargs["route_path"] == latest_route_path
    assert get_context.await_args.kwargs["context_params"] == latest_context_params
    assert get_presets.await_args.kwargs["route_path"] == latest_route_path
    assert get_presets.await_args.kwargs["context_params"] == latest_context_params
    assert response.route_path == latest_route_path
    assert session.route_path == latest_route_path
    assert session.context_data["projectId"] == latest_context_params["projectId"]
    assert session.context_data["_assistantMemory"]["activeRoutePath"] == latest_route_path


@pytest.mark.asyncio
async def test_assistant_service_chat_stream_uses_latest_route_context_for_existing_session(
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
        id=89,
        module_code="default",
        route_path="/dashboard",
        context_data={"tab": "overview"},
    )
    latest_route_path = "/projects/detail/3"
    latest_context_params = {"projectId": 3}
    get_context = AsyncMock(
        return_value=SimpleNamespace(
            module_code="default",
            module_name="通用助手",
            route_path=latest_route_path,
            data={"project": {"id": 3}},
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

    chunks = [
        json.loads(chunk)
        async for chunk in service.chat_stream(
            session_id=89,
            message="继续查看当前项目",
            tenant_id=1,
            user_id=9,
            team_ids=None,
            route_path=latest_route_path,
            context_params=latest_context_params,
        )
    ]

    assert get_context.await_args.kwargs["route_path"] == latest_route_path
    assert get_context.await_args.kwargs["context_params"] == latest_context_params
    assert get_presets.await_args.kwargs["route_path"] == latest_route_path
    assert get_presets.await_args.kwargs["context_params"] == latest_context_params
    assert [item["type"] for item in chunks] == ["content", "done"]
    assert chunks[-1]["routePath"] == latest_route_path
    assert session.route_path == latest_route_path
    assert session.context_data["projectId"] == latest_context_params["projectId"]
    assert session.context_data["_assistantMemory"]["activeRoutePath"] == latest_route_path
