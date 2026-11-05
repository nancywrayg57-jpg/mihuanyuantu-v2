from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.assistant.service import AssistantService


@pytest.mark.asyncio
async def test_assistant_chat_reply_uses_user_message_id_for_credit_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.ensure_enabled",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_config",
        AsyncMock(return_value=SimpleNamespace(config={}, deduct_credits=True, credits_per_call=1)),
    )
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.get_provider_settings",
        AsyncMock(
            return_value={
                "base_url": "https://example.com",
                "api_key": "test-key",
                "model": "gpt-test",
                "temperature": 0,
                "max_tokens": 1024,
            }
        ),
    )
    monkeypatch.setattr(
        "app.domain.assistant.service.ensure_credit_precheck",
        AsyncMock(return_value=None),
    )

    captured: dict[str, object] = {}

    async def fake_charge_credits_by_usage(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return SimpleNamespace(
            charged=True,
            amount=Decimal("1.00"),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            transaction_id=66,
        )

    monkeypatch.setattr(
        "app.domain.assistant.service.charge_credits_by_usage",
        AsyncMock(side_effect=fake_charge_credits_by_usage),
    )

    class FakeDB:
        def __init__(self) -> None:
            self.items: list[object] = []
            self._next_id = 1

        def add(self, item: object) -> None:
            if getattr(item, "id", None) is None:
                item.id = self._next_id
                self._next_id += 1
            self.items.append(item)

        async def commit(self) -> None:
            return None

    class FakeAdapter:
        module_name = "通用助手"
        default_chat_prompt = None

        async def infer_action_from_reply(self, reply: str, route: str, params: dict[str, object], **kwargs):
            return None

        async def canonicalize_action(self, action: dict[str, object], route: str, params: dict[str, object], **kwargs):
            return action

    service = AssistantService(FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(
        service,
        "get_session",
        AsyncMock(
            return_value=SimpleNamespace(
                id=55,
                module_code="default",
                route_path="/dashboard",
                context_data={},
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "get_context",
        AsyncMock(
            return_value=SimpleNamespace(
                module_code="default",
                module_name="通用助手",
                route_path="/dashboard",
                data={},
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "get_presets",
        AsyncMock(return_value=SimpleNamespace(presets=[])),
    )
    monkeypatch.setattr(
        service,
        "_resolve_prompt_stack",
        AsyncMock(return_value={"system": "system", "moduleChat": "module", "writeGuard": "guard"}),
    )
    monkeypatch.setattr(service, "_build_chat_messages", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_get_user_team_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_resolve_adapter", lambda route: FakeAdapter())
    monkeypatch.setattr(
        service,
        "_call_ai_reply",
        AsyncMock(return_value=("这是一次真实回复", True, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})),
    )
    monkeypatch.setattr(service, "_get_last_assistant_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_infer_best_adapter_action", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_select_canonical_assistant_action", AsyncMock(return_value=None))

    response = await service.chat_reply(
        session_id=55,
        message="帮我总结一下当前页面",
        tenant_id=1,
        user_id=9,
        team_ids=None,
    )

    assert response.used_ai is True
    assert captured["reference_id"] == 55
    assert captured["idempotency_key"] == "assistant_chat:1"
