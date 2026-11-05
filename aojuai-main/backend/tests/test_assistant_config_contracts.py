from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from unittest.mock import AsyncMock

import orjson
import pytest
from sqlalchemy.dialects import postgresql

from app.api.v1.endpoints import assistant as assistant_endpoints
from app.core.provider_secrets import decrypt_provider_secret, encrypt_provider_secret
from app.domain.assistant.config_models import AssistantTenantConfig
from app.domain.assistant.config_schemas import AssistantConfigUpsertRequest, AssistantConfigView
from app.domain.assistant.config_service import DEFAULT_ASSISTANT_PROMPTS, AssistantConfigService


class _DummyResult:
    def __init__(self, *, scalar_value: object | None = None) -> None:
        self._scalar_value = scalar_value

    def scalar_one_or_none(self) -> object | None:
        return self._scalar_value


class _RecordingSession:
    def __init__(self, results: Sequence[_DummyResult]) -> None:
        self._results = list(results)
        self.statements: list[object] = []

    async def execute(self, statement):  # noqa: ANN001
        self.statements.append(statement)
        if not self._results:
            raise AssertionError("unexpected execute() call without prepared result")
        return self._results.pop(0)


def _compiled_sql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def _index_map(model: object) -> dict[str, object]:
    table = model.__table__  # type: ignore[attr-defined]
    return {index.name: index for index in table.indexes}


def test_assistant_config_indexes_match_singleton_soft_delete_contract() -> None:
    indexes = _index_map(AssistantTenantConfig)

    tenant_lookup = indexes["ix_assistant_tenant_configs_tenant_id"]
    assert [str(expr) for expr in tenant_lookup.expressions] == ["assistant_tenant_configs.tenant_id"]

    active_unique = indexes["uq_assistant_tenant_configs_tenant"]
    assert active_unique.unique is True
    assert [str(expr) for expr in active_unique.expressions] == ["assistant_tenant_configs.tenant_id"]
    assert str(active_unique.dialect_options["postgresql"]["where"]) == "deleted_at IS NULL"


@pytest.mark.asyncio
async def test_assistant_config_get_config_checks_canonical_then_legacy_payload() -> None:
    session = _RecordingSession(
        [
            _DummyResult(scalar_value=None),
            _DummyResult(scalar_value={"assistant": {"enabled": True, "baseUrl": "https://example.com/v1", "model": "gpt-test", "apiKey": "sk-legacy"}}),
        ]
    )
    service = AssistantConfigService(session)  # type: ignore[arg-type]

    result = await service.get_config(tenant_id=7)

    assert result is not None
    assert result.enabled is True
    assert result.config["base_url"] == "https://example.com/v1"
    assert result.config["model"] == "gpt-test"
    assert result.secrets["api_key"] == "sk-legacy"

    canonical_sql = _compiled_sql(session.statements[0])
    assert "assistant_tenant_configs.tenant_id = 7" in canonical_sql
    assert "assistant_tenant_configs.deleted_at IS NULL" in canonical_sql

    legacy_sql = _compiled_sql(session.statements[1])
    assert "FROM tenants" in legacy_sql
    assert "tenants.id = 7" in legacy_sql
    assert "tenants.deleted_at IS NULL" in legacy_sql


@pytest.mark.asyncio
async def test_assistant_config_view_masks_api_key_and_exposes_presence_metadata() -> None:
    service = AssistantConfigService(SimpleNamespace())
    service.get_config = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            enabled=True,
            deduct_credits=True,
            credits_per_call=3,
            config={
                "points_token_ratio": 1500,
                "base_url": "https://example.com/v1",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 4096,
                "stream": True,
            },
            secrets={"api_key": "sk-test-12345678"},
        )
    )

    payload = (await service.get_config_view(tenant_id=7)).model_dump(by_alias=True)

    assert payload["enabled"] is True
    assert payload["isEnabled"] is True
    assert payload["apiKeySet"] is True
    assert payload["apiKeyMasked"] == "sk-t********5678"
    assert "apiKey" not in payload


@pytest.mark.asyncio
async def test_assistant_config_view_without_row_returns_virtual_default_contract() -> None:
    service = AssistantConfigService(SimpleNamespace())
    service.get_config = AsyncMock(return_value=None)  # type: ignore[method-assign]

    payload = (await service.get_config_view(tenant_id=7)).model_dump(by_alias=True)

    assert payload["enabled"] is False
    assert payload["isEnabled"] is False
    assert payload["baseUrl"] is None
    assert payload["model"] == "gpt-3.5-turbo"
    assert payload["temperature"] == 0.7
    assert payload["maxTokens"] is None  # 空=跟随模型默认（不下发 max_tokens）
    assert payload["stream"] is True
    assert payload["apiKeySet"] is False
    assert payload["prompts"]["assistant"]["system"] == DEFAULT_ASSISTANT_PROMPTS["assistant"]["system"]
    assert payload["prompts"]["assistant"]["writeGuard"] == DEFAULT_ASSISTANT_PROMPTS["assistant"]["writeGuard"]


def test_assistant_config_upsert_accepts_enabled_and_legacy_is_enabled_alias() -> None:
    canonical = AssistantConfigUpsertRequest.model_validate({"enabled": True})
    legacy = AssistantConfigUpsertRequest.model_validate({"isEnabled": False})

    assert canonical.enabled is True
    assert legacy.enabled is False


def test_assistant_config_upsert_omits_blank_api_key_after_normalization() -> None:
    payload = AssistantConfigUpsertRequest.model_validate(
        {
            "apiKey": "   ",
            "baseUrl": "https://example.com/v1",
        }
    ).model_dump(exclude_unset=True, exclude_none=True, by_alias=False)

    assert payload["base_url"] == "https://example.com/v1"
    assert "api_key" not in payload


@pytest.mark.asyncio
async def test_assistant_config_upsert_encrypts_api_key_before_storage() -> None:
    db = SimpleNamespace(add=lambda *_args, **_kwargs: None, commit=AsyncMock(), refresh=AsyncMock())
    service = AssistantConfigService(db)  # type: ignore[arg-type]
    config = SimpleNamespace(
        enabled=False,
        deduct_credits=False,
        credits_per_call=1,
        config={},
        secrets={},
    )
    service._get_db_config = AsyncMock(return_value=config)  # type: ignore[method-assign]
    service._get_legacy_payload = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = await service.upsert_config(
        tenant_id=7,
        request=AssistantConfigUpsertRequest.model_validate({"apiKey": "sk-test-1234"}),
    )

    assert result is config
    stored_value = config.secrets["api_key"]
    assert stored_value != "sk-test-1234"
    assert decrypt_provider_secret(stored_value) == "sk-test-1234"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(config)


@pytest.mark.asyncio
async def test_assistant_provider_settings_decrypts_stored_secret_before_runtime_use() -> None:
    encrypted_secret = encrypt_provider_secret("sk-runtime-1234")
    service = AssistantConfigService(SimpleNamespace())
    service.get_config = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            config={
                "base_url": "https://example.com/v1",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 4096,
                "stream": True,
            },
            secrets={"api_key": encrypted_secret},
        )
    )

    provider_settings = await service.get_provider_settings(tenant_id=7)

    assert provider_settings is not None
    assert provider_settings["api_key"] == "sk-runtime-1234"


@pytest.mark.asyncio
async def test_assistant_provider_settings_returns_none_without_required_runtime_fields() -> None:
    service_missing_secret = AssistantConfigService(SimpleNamespace())
    service_missing_secret.get_config = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            config={
                "base_url": "https://example.com/v1",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 2048,
                "stream": True,
            },
            secrets={},
        )
    )
    assert await service_missing_secret.get_provider_settings(tenant_id=7) is None

    service_missing_base_url = AssistantConfigService(SimpleNamespace())
    service_missing_base_url.get_config = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            config={
                "base_url": "   ",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 2048,
                "stream": True,
            },
            secrets={"api_key": encrypt_provider_secret("sk-runtime-1234")},
        )
    )
    assert await service_missing_base_url.get_provider_settings(tenant_id=7) is None


def test_assistant_config_service_projects_jsonb_record_into_provider_view_contract() -> None:
    service = AssistantConfigService(SimpleNamespace())
    config = SimpleNamespace(
        config={
            "base_url": " https://example.com/v1/ ",
            "model": " gpt-4o-mini ",
            "temperature": "0.2",
            "max_tokens": "4096",
            "stream": False,
        },
        secrets={"api_key": " plain-secret-1234 "},
    )

    provider_view = service.get_provider_view(config)  # type: ignore[arg-type]

    assert provider_view["base_url"] == "https://example.com/v1"
    assert provider_view["model"] == "gpt-4o-mini"
    assert provider_view["temperature"] == 0.2
    assert provider_view["max_tokens"] == 4096
    assert provider_view["stream"] is False
    assert provider_view["api_key_masked"] == "plai*********1234"
    assert provider_view["api_key_set"] is True


def test_assistant_config_endpoint_serializer_emits_alias_fields() -> None:
    payload = assistant_endpoints._serialize_assistant_config_view(
        AssistantConfigView(
            enabled=True,
            deduct_credits=True,
            credits_per_call=2,
            points_token_ratio=1200,
            base_url="https://example.com/v1",
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=4096,
            stream=True,
            api_key_masked="sk-t********5678",
            api_key_set=True,
        )
    )

    assert payload["enabled"] is True
    assert payload["isEnabled"] is True
    assert payload["deductCredits"] is True
    assert payload["creditsPerCall"] == 2
    assert payload["pointsTokenRatio"] == 1200
    assert payload["baseUrl"] == "https://example.com/v1"
    assert payload["apiKeyMasked"] == "sk-t********5678"
    assert payload["apiKeySet"] is True
    assert "deduct_credits" not in payload
    assert "base_url" not in payload


@pytest.mark.asyncio
async def test_assistant_get_config_endpoint_returns_serialized_alias_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeService:
        def __init__(self, db):  # noqa: ANN001
            self.db = db

        async def get_config_view(self, tenant_id: int) -> AssistantConfigView:  # noqa: ARG002
            return AssistantConfigView(
                enabled=True,
                deduct_credits=False,
                credits_per_call=1,
                points_token_ratio=1000,
                base_url="https://example.com/v1",
                model="gpt-4o-mini",
                temperature=0.2,
                max_tokens=2048,
                stream=True,
                api_key_masked="sk-t********5678",
                api_key_set=True,
            )

    monkeypatch.setattr(assistant_endpoints, "AssistantConfigService", _FakeService)

    response = await assistant_endpoints.get_config(
        current_user=SimpleNamespace(),
        tenant_ctx=SimpleNamespace(tenant_id=7),
        db=SimpleNamespace(),
    )

    payload = orjson.loads(response.body)
    assert payload["success"] is True
    assert payload["data"]["enabled"] is True
    assert payload["data"]["isEnabled"] is True
    assert payload["data"]["baseUrl"] == "https://example.com/v1"
    assert "base_url" not in payload["data"]
