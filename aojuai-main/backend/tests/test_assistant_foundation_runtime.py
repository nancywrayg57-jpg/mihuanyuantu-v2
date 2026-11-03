from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.api.v1.endpoints import assistant


def _build_tenant(*, tenant_id: int = 1, config: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=tenant_id,
        name="Demo Tenant",
        code="demo",
        domain=None,
        description=None,
        is_active=True,
        expires_at=None,
        config=config or {},
        quota={},
        contact_name=None,
        contact_phone=None,
        contact_email=None,
        created_at=None,
    )


def _build_test_app(*, target_tenant_id: int = 1) -> FastAPI:
    app = FastAPI()
    app.include_router(assistant.router, prefix="/api/v1/assistant")

    async def override_current_user():
        return SimpleNamespace(
            id=7,
            tenant_id=1,
            username="demo",
            nickname="Demo",
            is_superuser=True,
        )

    async def override_tenant_admin():
        return SimpleNamespace(id=1, tenant_id=1, is_superuser=True)

    async def override_db():
        yield SimpleNamespace()

    async def override_tenant_ctx():
        return SimpleNamespace(tenant_id=target_tenant_id, is_superuser=True, user_tenant_id=1)

    async def override_data_scope():
        return SimpleNamespace(has_all_read_access=False, read_team_ids=[101, 102])

    app.dependency_overrides[deps.get_current_user] = override_current_user
    app.dependency_overrides[deps.get_current_tenant_admin] = override_tenant_admin
    app.dependency_overrides[deps.get_db] = override_db
    app.dependency_overrides[deps.get_tenant_context] = override_tenant_ctx
    app.dependency_overrides[deps.get_data_scope] = override_data_scope
    return app


def _parse_sse_payloads(raw_text: str) -> list[dict]:
    payloads: list[dict] = []
    for line in raw_text.splitlines():
        if not line.startswith("data: "):
            continue
        payloads.append(json.loads(line[6:]))
    return payloads


@pytest.mark.asyncio
async def test_assistant_context_endpoint_applies_module_skill_governance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(
        tenant_id=42,
        config={
            "assistant": {
                "capabilities": {
                    "moduleSkillGovernance": {
                        "modules": [
                            {
                                "moduleCode": "default",
                                "skillRules": [
                                    {
                                        "skillId": "default.page_orienter",
                                        "enabled": False,
                                        "rank": 1,
                                    }
                                ],
                            }
                        ]
                    }
                }
            }
        },
    )

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        assert tenant_id == 42
        return tenant

    async def fake_get_user_team_ids(db, *, tenant_id: int, user_id: int):  # noqa: ANN001
        assert tenant_id == 42
        assert user_id == 7
        return [301, 302]

    monkeypatch.setattr(assistant.TenantService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(assistant, "_get_user_team_ids", fake_get_user_team_ids)

    app = _build_test_app(target_tenant_id=42)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/assistant/context", params={"route": "/dashboard", "context": "{}"})

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["moduleCode"] == "default"
    assert payload["moduleName"] == "通用助手"
    assert payload["data"]["capabilityManifest"]["skillCount"] == 0
    assert payload["data"]["skillPacks"] == []
    assert payload["data"]["currentRoleProfile"]["label"] == "当前登录用户"


@pytest.mark.asyncio
async def test_assistant_presets_endpoint_returns_default_adapter_presets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        return _build_tenant(tenant_id=tenant_id, config={})

    async def fake_get_user_team_ids(db, *, tenant_id: int, user_id: int):  # noqa: ANN001
        assert tenant_id == 8
        assert user_id == 7
        return [301]

    monkeypatch.setattr(assistant.TenantService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(assistant, "_get_user_team_ids", fake_get_user_team_ids)

    app = _build_test_app(target_tenant_id=8)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/assistant/presets", params={"route": "/dashboard", "context": "{}"})

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["moduleCode"] == "default"
    assert [item["label"] for item in payload["presets"]] == ["我能做什么", "下一步建议"]


@pytest.mark.asyncio
async def test_assistant_chat_uses_module_runtime_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = _build_tenant(
        tenant_id=9,
        config={
            "assistant": {
                "enabled": True,
                "baseUrl": "https://example.com/v1",
                "model": "gpt-test",
                "apiKey": "sk-live-12345678",
            }
        },
    )

    async def fake_get_by_id(self, tenant_id: int):  # noqa: ANN001
        assert tenant_id == 9
        return tenant

    async def fake_get_user_team_ids(db, *, tenant_id: int, user_id: int):  # noqa: ANN001
        assert tenant_id == 9
        assert user_id == 7
        return [401, 402]

    async def fake_chat_stream(self, messages):  # noqa: ANN001
        system_prompt = messages[0]["content"]
        assert "【当前模块】通用助手" in system_prompt
        assert "【能力框架】" in system_prompt
        assert "tool.time.now" in system_prompt
        yield "第一段"
        yield "第二段"

    monkeypatch.setattr(assistant.TenantService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(assistant, "_get_user_team_ids", fake_get_user_team_ids)
    monkeypatch.setattr(assistant.OpenAIClient, "chat_stream", fake_chat_stream)

    app = _build_test_app(target_tenant_id=9)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assistant/chat",
            json={
                "message": "请告诉我下一步",
                "routePath": "/dashboard",
                "contextParams": {"tab": "overview"},
            },
        )

    assert response.status_code == 200, response.text
    payloads = _parse_sse_payloads(response.text)
    assert payloads[0]["type"] == "content"
    assert payloads[-1]["type"] == "done"
    assert payloads[-1]["usedAi"] is True
    assert payloads[-1]["moduleCode"] == "default"
    assert payloads[-1]["moduleName"] == "通用助手"
    assert payloads[-1]["suggestions"][0] == "你现在能帮我做什么？"
    assert payloads[-1]["context"]["capabilityContext"]["runtime"]["sessionScope"]["readTeamIds"] == [101, 102]


@pytest.mark.asyncio
async def test_assistant_create_session_endpoint_returns_foundation_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create_session(self, tenant_id: int, user_id: int, module_code, route_path: str, context_params: dict):  # noqa: ANN001
        assert tenant_id == 16
        assert user_id == 7
        assert module_code is None
        assert route_path == "/dashboard"
        assert context_params == {"tab": "overview"}
        return assistant.SessionResponse(
            id=88,
            module_code="default",
            module_name="通用助手",
            route_path="/dashboard",
            context_data={"tab": "overview"},
            created_at=datetime(2026, 3, 31, 8, 0, tzinfo=UTC),
        )

    monkeypatch.setattr(assistant.AssistantService, "create_session", fake_create_session)

    app = _build_test_app(target_tenant_id=16)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assistant/sessions",
            json={
                "routePath": "/dashboard",
                "contextParams": {"tab": "overview"},
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["id"] == 88
    assert payload["module_code"] == "default"
    assert payload["module_name"] == "通用助手"
    assert payload["route_path"] == "/dashboard"


@pytest.mark.asyncio
async def test_assistant_session_messages_endpoint_returns_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_session_messages(self, *, session_id: int, tenant_id: int, user_id: int, limit: int):  # noqa: ANN001
        assert session_id == 88
        assert tenant_id == 17
        assert user_id == 7
        assert limit == 50
        return [
            assistant.MessageResponse(
                id=1,
                role="user",
                content="你好",
                action_type=None,
                action_result=None,
                created_at="2026-04-15T09:00:00+08:00",
            ),
            assistant.MessageResponse(
                id=2,
                role="assistant",
                content="你好，有什么我可以帮你？",
                action_type="chat_stream",
                action_result={"assistantAction": {"toolId": "default.page_orienter", "summary": "准备说明当前页", "mode": "ready"}},
                created_at="2026-04-15T09:00:01+08:00",
            ),
        ]

    monkeypatch.setattr(assistant.AssistantService, "list_session_messages", fake_list_session_messages)

    app = _build_test_app(target_tenant_id=17)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/assistant/sessions/88/messages", params={"limit": 50})

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload[0]["role"] == "user"
    assert payload[1]["action_type"] == "chat_stream"
    assert payload[1]["action_result"]["assistantAction"]["toolId"] == "default.page_orienter"


@pytest.mark.asyncio
async def test_assistant_chat_session_stream_uses_runtime_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_chat_stream(
        self,
        session_id: int,
        message: str,
        tenant_id: int,
        user_id: int,
        team_ids,
        route_path: str | None = None,
        context_params: dict | None = None,
    ):  # noqa: ANN001
        assert session_id == 123
        assert message == "查询当前页面"
        assert tenant_id == 18
        assert user_id == 7
        assert team_ids == [101, 102]
        assert route_path == "/dashboard"
        assert context_params == {"tab": "overview"}
        yield json.dumps({"type": "content", "content": "第一段"})
        yield json.dumps({"type": "done", "reply": "第一段", "usedAi": False, "moduleCode": "default"})

    monkeypatch.setattr(assistant.AssistantService, "chat_stream", fake_chat_stream)

    app = _build_test_app(target_tenant_id=18)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assistant/chat",
            json={
                "sessionId": 123,
                "message": "查询当前页面",
                "routePath": "/dashboard",
                "contextParams": {"tab": "overview"},
            },
        )

    assert response.status_code == 200, response.text
    payloads = _parse_sse_payloads(response.text)
    assert payloads == [
        {"type": "content", "content": "第一段"},
        {"type": "done", "reply": "第一段", "usedAi": False, "moduleCode": "default"},
    ]


@pytest.mark.asyncio
async def test_assistant_chat_reply_session_uses_runtime_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_chat_reply(
        self,
        *,
        session_id: int,
        message: str,
        tenant_id: int,
        user_id: int,
        team_ids,
        route_path: str | None = None,
        context_params: dict | None = None,
    ):  # noqa: ANN001
        assert session_id == 321
        assert message == "继续查看当前项目"
        assert tenant_id == 19
        assert user_id == 7
        assert team_ids == [101, 102]
        assert route_path == "/projects/detail/9"
        assert context_params == {"projectId": 9}
        return assistant.ChatReplyResponse(
            session_id=321,
            module_code="default",
            module_name="通用助手",
            route_path="/projects/detail/9",
            reply="已切换到当前项目上下文。",
            used_ai=False,
            context={"project": {"id": 9}},
            suggestions=[],
            action=None,
        )

    monkeypatch.setattr(assistant.AssistantService, "chat_reply", fake_chat_reply)

    app = _build_test_app(target_tenant_id=19)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/assistant/chat/reply",
            json={
                "sessionId": 321,
                "message": "继续查看当前项目",
                "routePath": "/projects/detail/9",
                "contextParams": {"projectId": 9},
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["session_id"] == 321
    assert payload["route_path"] == "/projects/detail/9"
    assert payload["reply"] == "已切换到当前项目上下文。"
