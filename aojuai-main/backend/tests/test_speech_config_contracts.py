from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import orjson
import pytest
from sqlalchemy.dialects import postgresql
from starlette.datastructures import Headers, UploadFile

from app.api.v1.endpoints import speech as speech_endpoints
from app.core.exceptions import BusinessError, NotFoundError
from app.domain.speech.billing import calc_speech_text_credits, count_speech_billing_characters
from app.domain.speech.models import SpeechTenantConfig
from app.domain.speech.providers.common import bytes_to_stream
from app.domain.speech.schemas import SpeechTenantConfigUpsertRequest, SpeechTenantConfigView
from app.domain.speech.service import SpeechConfigService
from app.domain.speech.voice_clone_schemas import (
    SpeechVoiceCloneAssetView,
    SpeechVoiceCloneSupportView,
    SpeechVoiceCloneView,
    SpeechVoiceCloneWorkspaceItemView,
    SpeechVoiceCloneWorkspacePayload,
)
from app.domain.speech.voice_clone_service import SpeechVoiceCloneService


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


def test_speech_config_indexes_match_singleton_soft_delete_contract() -> None:
    indexes = _index_map(SpeechTenantConfig)

    tenant_lookup = indexes["ix_speech_tenant_configs_tenant_id"]
    assert [str(expr) for expr in tenant_lookup.expressions] == ["speech_tenant_configs.tenant_id"]

    active_unique = indexes["uq_speech_tenant_configs_tenant"]
    assert active_unique.unique is True
    assert [str(expr) for expr in active_unique.expressions] == ["speech_tenant_configs.tenant_id"]
    assert str(active_unique.dialect_options["postgresql"]["where"]) == "deleted_at IS NULL"


@pytest.mark.asyncio
async def test_speech_get_by_tenant_id_query_stays_tenant_scoped_and_active_only() -> None:
    session = _RecordingSession([_DummyResult(scalar_value=None)])
    service = SpeechConfigService(session)  # type: ignore[arg-type]

    with pytest.raises(NotFoundError, match="语音配置不存在"):
        await service.get_by_tenant_id(tenant_id=7)

    sql = _compiled_sql(session.statements[0])
    assert "speech_tenant_configs.tenant_id = 7" in sql
    assert "speech_tenant_configs.deleted_at IS NULL" in sql


def test_speech_upsert_schema_accepts_enabled_and_legacy_is_active_alias() -> None:
    canonical = SpeechTenantConfigUpsertRequest.model_validate({"enabled": True})
    legacy = SpeechTenantConfigUpsertRequest.model_validate({"isActive": False})

    assert canonical.enabled is True
    assert legacy.enabled is False


def test_speech_view_resolves_disabled_status_as_unavailable_even_if_legacy_flag_drifted() -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(
        config={"tts": {"providerId": "edge_tts", "settings": {}}},
        secrets={"tts": {}},
        status="disabled",
        is_active=True,
    )

    view = service.to_view(cfg)  # type: ignore[arg-type]

    assert view.enabled is False
    assert view.status == "disabled"
    assert view.tts is not None
    assert view.tts.provider_id == "edge_tts"
    payload = view.model_dump(by_alias=True)
    assert payload["enabled"] is False
    assert payload["isActive"] is False


def test_speech_view_prefers_canonical_non_disabled_status_over_legacy_inactive_mirror() -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(
        config={"tts": {"providerId": "edge_tts", "settings": {}}},
        secrets={"tts": {}},
        status="degraded",
        is_active=False,
    )

    view = service.to_view(cfg)  # type: ignore[arg-type]

    assert view.enabled is True
    assert view.status == "degraded"
    payload = view.model_dump(by_alias=True)
    assert payload["enabled"] is True
    assert payload["isActive"] is True


def test_speech_view_exposes_tts_profiles_and_default_profile_aliases() -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(
        config={
            "ttsProfiles": [
                {
                    "id": "host-main",
                    "label": "默认主持人",
                    "providerId": "edge_tts",
                    "settings": {"voice": "zh-CN-XiaoxiaoNeural"},
                    "allowVoiceClone": True,
                }
            ],
            "defaultTtsProfileId": "host-main",
            "tts": {"providerId": "edge_tts", "settings": {"voice": "zh-CN-XiaoxiaoNeural"}},
        },
        secrets={"tts": {}, "ttsProfiles": {"host-main": {}}},
        status="active",
        is_active=True,
    )

    view = service.to_view(cfg)  # type: ignore[arg-type]
    payload = view.model_dump(by_alias=True)

    assert payload["defaultTtsProfileId"] == "host-main"
    assert payload["ttsProfiles"][0]["id"] == "host-main"
    assert payload["ttsProfiles"][0]["allowVoiceClone"] is True
    assert payload["ttsProfiles"][0]["isDefault"] is True


def test_speech_view_normalizes_legacy_mimo_alias_to_canonical_provider_id() -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(
        config={
            "tts": {"providerId": "mimo_tts", "settings": {"model": "mimo-v2-tts"}},
            "ttsProfiles": [
                {
                    "id": "default-tts",
                    "label": "默认模型",
                    "providerId": "xiaomi_mimo_tts",
                    "settings": {"model": "mimo-v2-tts"},
                    "allowVoiceClone": False,
                }
            ],
            "defaultTtsProfileId": "default-tts",
        },
        secrets={"tts": {"apiKey": "masked"}, "ttsProfiles": {"default-tts": {"apiKey": "masked"}}},
        status="active",
        is_active=True,
    )

    view = service.to_view(cfg)  # type: ignore[arg-type]
    payload = view.model_dump(by_alias=True)

    assert payload["tts"]["providerId"] == "xiaomi_mimo"
    assert payload["ttsProfiles"][0]["providerId"] == "xiaomi_mimo"
    assert payload["ttsProfiles"][0]["secretsSet"]["apiKey"] is True


def test_speech_legacy_view_accepts_provider_alias_ids() -> None:
    payload = SpeechConfigService.to_legacy_view(
        {
            "tts": {"providerId": "xiaomi_mimo", "settings": {"model": "mimo-v2-tts"}},
            "ttsProfiles": [
                {
                    "id": "default-voice",
                    "label": "默认音色",
                    "providerId": "mimo_tts",
                    "settings": {"model": "mimo-v2-tts"},
                }
            ],
            "defaultTtsProfileId": "default-voice",
        }
    )

    assert payload["tts"]["providerId"] == "xiaomi_mimo"
    assert payload["ttsProfiles"][0]["providerId"] == "xiaomi_mimo"
    assert payload["defaultTtsProfileId"] == "default-voice"


@pytest.mark.asyncio
async def test_speech_upsert_enabled_false_forces_disabled_status(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(config={}, secrets={}, status="active", is_active=True)
    captured: dict[str, object] = {}

    monkeypatch.setattr(service, "get_or_create", AsyncMock(return_value=cfg))

    async def _fake_update(obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(service, "update", _fake_update)

    result = await service.upsert(
        tenant_id=1,
        data=SpeechTenantConfigUpsertRequest(enabled=False),
    )

    assert result is cfg
    assert captured["is_active"] is False
    assert captured["status"] == "disabled"


@pytest.mark.asyncio
async def test_speech_upsert_status_degraded_keeps_enabled_true(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(config={}, secrets={}, status="active", is_active=True)
    captured: dict[str, object] = {}

    monkeypatch.setattr(service, "get_or_create", AsyncMock(return_value=cfg))

    async def _fake_update(obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(service, "update", _fake_update)

    await service.upsert(
        tenant_id=1,
        data=SpeechTenantConfigUpsertRequest(status="degraded"),
    )

    assert captured["is_active"] is True
    assert captured["status"] == "degraded"


@pytest.mark.asyncio
async def test_speech_upsert_repairs_legacy_inactive_mirror_from_canonical_status(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(config={}, secrets={}, status="degraded", is_active=False)
    captured: dict[str, object] = {}

    monkeypatch.setattr(service, "get_or_create", AsyncMock(return_value=cfg))

    async def _fake_update(obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(service, "update", _fake_update)

    await service.upsert(
        tenant_id=1,
        data=SpeechTenantConfigUpsertRequest(),
    )

    assert captured["status"] == "degraded"
    assert captured["is_active"] is True


@pytest.mark.asyncio
async def test_speech_upsert_rejects_unknown_status(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(config={}, secrets={}, status="active", is_active=True)

    monkeypatch.setattr(service, "get_or_create", AsyncMock(return_value=cfg))

    with pytest.raises(BusinessError, match="不支持的语音配置状态"):
        await service.upsert(
            tenant_id=1,
            data=SpeechTenantConfigUpsertRequest(status="mystery"),
        )


@pytest.mark.asyncio
async def test_speech_upsert_tts_profiles_syncs_default_tts_section(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(config={}, secrets={}, status="active", is_active=True)
    captured: dict[str, object] = {}

    monkeypatch.setattr(service, "get_or_create", AsyncMock(return_value=cfg))

    async def _fake_update(obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(service, "update", _fake_update)

    await service.upsert(
        tenant_id=1,
        data=SpeechTenantConfigUpsertRequest.model_validate(
            {
                "ttsProfiles": [
                    {
                        "id": "host-main",
                        "label": "默认主持人",
                        "providerId": "edge_tts",
                        "settings": {"voice": "zh-CN-XiaoxiaoNeural"},
                        "isDefault": True,
                    }
                ]
            }
        ),
    )

    next_config = captured["config"]
    next_secrets = captured["secrets"]

    assert isinstance(next_config, dict)
    assert next_config["defaultTtsProfileId"] == "host-main"
    assert next_config["tts"]["providerId"] == "edge_tts"
    assert next_config["ttsProfiles"][0]["id"] == "host-main"

    assert isinstance(next_secrets, dict)
    assert next_secrets["ttsProfiles"] == {"host-main": {}}
    assert next_secrets["tts"] == {}


@pytest.mark.asyncio
async def test_speech_upsert_tts_profiles_keep_multiple_models_and_reuse_provider_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(
        config={
            "ttsProfiles": [
                {
                    "id": "mimo-standard",
                    "label": "MiMo 标准",
                    "providerId": "xiaomi_mimo",
                    "settings": {"model": "mimo-v2.5-tts"},
                    "isDefault": True,
                }
            ],
            "defaultTtsProfileId": "mimo-standard",
            "tts": {"providerId": "xiaomi_mimo", "settings": {"model": "mimo-v2.5-tts"}},
        },
        secrets={
            "tts": {"apiKey": "mimo-secret"},
            "ttsProfiles": {"mimo-standard": {"apiKey": "mimo-secret"}},
        },
        status="active",
        is_active=True,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(service, "get_or_create", AsyncMock(return_value=cfg))

    async def _fake_update(obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(service, "update", _fake_update)

    await service.upsert(
        tenant_id=1,
        data=SpeechTenantConfigUpsertRequest.model_validate(
            {
                "ttsProfiles": [
                    {
                        "id": "mimo-standard",
                        "label": "MiMo 标准",
                        "providerId": "xiaomi_mimo",
                        "settings": {"model": "mimo-v2.5-tts"},
                        "isDefault": True,
                    },
                    {
                        "id": "mimo-voice-design",
                        "label": "MiMo 音色设计",
                        "providerId": "xiaomi_mimo",
                        "settings": {"model": "mimo-v2.5-tts-voicedesign"},
                    },
                    {
                        "id": "mimo-voice-clone",
                        "label": "MiMo 声音复刻",
                        "providerId": "xiaomi_mimo",
                        "settings": {"model": "mimo-v2.5-tts-voiceclone"},
                        "allowVoiceClone": True,
                    },
                ],
                "defaultTtsProfileId": "mimo-standard",
            }
        ),
    )

    next_config = captured["config"]
    next_secrets = captured["secrets"]

    assert isinstance(next_config, dict)
    assert [item["id"] for item in next_config["ttsProfiles"]] == [
        "mimo-standard",
        "mimo-voice-design",
        "mimo-voice-clone",
    ]
    assert next_config["defaultTtsProfileId"] == "mimo-standard"
    assert next_config["tts"]["settings"]["model"] == "mimo-v2.5-tts"

    assert isinstance(next_secrets, dict)
    assert next_secrets["ttsProfiles"]["mimo-standard"]["apiKey"] == "mimo-secret"
    assert next_secrets["ttsProfiles"]["mimo-voice-design"]["apiKey"] == "mimo-secret"
    assert next_secrets["ttsProfiles"]["mimo-voice-clone"]["apiKey"] == "mimo-secret"
    assert next_secrets["tts"]["apiKey"] == "mimo-secret"


@pytest.mark.asyncio
async def test_speech_upsert_tts_profiles_preserves_profile_secrets_when_provider_shape_is_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SpeechConfigService(SimpleNamespace())  # type: ignore[arg-type]
    cfg = SimpleNamespace(
        config={
            "ttsProfiles": [
                {
                    "id": "default-tts",
                    "label": "默认模型",
                    "providerId": "xiaomi_mimo",
                    "settings": {"model": "mimo-v2-tts"},
                    "isDefault": True,
                }
            ],
            "defaultTtsProfileId": "default-tts",
            "tts": {"providerId": "xiaomi_mimo", "settings": {"model": "mimo-v2-tts"}},
        },
        secrets={"tts": {"apiKey": "secret-key"}, "ttsProfiles": {"default-tts": {"apiKey": "secret-key"}}},
        status="active",
        is_active=True,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(service, "get_or_create", AsyncMock(return_value=cfg))

    async def _fake_update(obj, payload, exclude_unset=False):  # noqa: ANN001, ARG001
        captured.update(payload)
        for key, value in payload.items():
            setattr(obj, key, value)
        return obj

    monkeypatch.setattr(service, "update", _fake_update)

    await service.upsert(
        tenant_id=1,
        data=SpeechTenantConfigUpsertRequest.model_validate(
            {
                "ttsProfiles": [
                    {
                        "id": "default-tts",
                        "label": "默认模型",
                        "providerId": "xiaomi_mimo",
                        "settings": {"model": "mimo-v2-tts", "voice": "default_zh"},
                        "isDefault": True,
                    }
                ],
                "defaultTtsProfileId": "default-tts",
            }
        ),
    )

    next_secrets = captured["secrets"]
    assert isinstance(next_secrets, dict)
    assert next_secrets["ttsProfiles"]["default-tts"]["apiKey"] == "secret-key"
    assert next_secrets["tts"]["apiKey"] == "secret-key"


def test_speech_config_endpoint_serializer_emits_alias_fields() -> None:
    payload = speech_endpoints._serialize_speech_config_view(
        SpeechTenantConfigView(
            enabled=False,
            status="disabled",
            tts=None,
            stt=None,
            barge_in=None,
            secrets_set={"tts": True},
        )
    )

    assert payload["enabled"] is False
    assert payload["isActive"] is False
    assert payload["status"] == "disabled"
    assert payload["secretsSet"] == {"tts": True}
    assert "barge_in" not in payload
    assert "secrets_set" not in payload


@pytest.mark.asyncio
async def test_get_speech_config_endpoint_returns_serialized_alias_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeService:
        def __init__(self, db):  # noqa: ANN001
            self.db = db

        async def get_view(self, *, tenant_id: int) -> SpeechTenantConfigView:  # noqa: ARG002
            return SpeechTenantConfigView(
                enabled=True,
                status="active",
                tts=None,
                stt=None,
                barge_in=None,
                secrets_set={"tts": True, "stt": False},
            )

    monkeypatch.setattr(speech_endpoints, "SpeechConfigService", _FakeService)

    response = await speech_endpoints.get_speech_config(
        current_user=SimpleNamespace(id=5),
        tenant_ctx=SimpleNamespace(tenant_id=7),
        db=SimpleNamespace(),
    )

    payload = orjson.loads(response.body)
    assert payload["success"] is True
    assert payload["data"]["enabled"] is True
    assert payload["data"]["isActive"] is True
    assert payload["data"]["secretsSet"] == {"tts": True, "stt": False}
    assert "secrets_set" not in payload["data"]




def test_voice_clone_support_uses_non_default_allowed_qwen_realtime_candidate() -> None:
    cfg = SimpleNamespace(
        config={
            "tts": {"providerId": "xiaomi_mimo", "settings": {"model": "mimo-v2-tts"}},
            "defaultTtsProfileId": "mimo-default",
            "ttsProfiles": [
                {
                    "id": "mimo-default",
                    "label": "Mimo",
                    "providerId": "xiaomi_mimo",
                    "settings": {"model": "mimo-v2-tts"},
                    "isDefault": True,
                    "allowVoiceClone": True,
                },
                {
                    "id": "qwen-realtime",
                    "label": "Qwen3",
                    "providerId": "aliyun_qwen_tts_realtime_sdk",
                    "settings": {"model": "qwen3-tts-instruct-flash-realtime", "voice": "Serena"},
                    "allowVoiceClone": True,
                },
            ],
        },
        secrets={
            "tts": {"apiKey": "mimo-key"},
            "ttsProviders": {"aliyun_qwen_tts_realtime_sdk": {"apiKey": "qwen-key"}},
        },
    )

    provider = SpeechVoiceCloneService._resolve_qwen_clone_provider_from_cfg(cfg=cfg)

    assert provider.provider_id == "aliyun_qwen_tts_realtime_sdk"
    assert provider.clone_mode == "remote_voice"
    assert provider.api_key == "qwen-key"
    assert provider.synthesis_model == "qwen3-tts-vc-2026-01-22"
    assert provider.source_profile_id == "qwen-realtime"
    assert provider.source_profile_label == "Qwen3"


def test_voice_clone_support_accepts_mimo_voiceclone_candidate() -> None:
    cfg = SimpleNamespace(
        config={
            "tts": {"providerId": "edge_tts", "settings": {}},
            "defaultTtsProfileId": "edge",
            "ttsProfiles": [
                {"id": "edge", "providerId": "edge_tts", "settings": {}, "isDefault": True},
                {
                    "id": "mimo-clone",
                    "label": "MiMo Clone",
                    "providerId": "xiaomi_mimo",
                    "settings": {"model": "mimo-v2.5-tts-voiceclone"},
                    "allowVoiceClone": True,
                },
            ],
        },
        secrets={"ttsProviders": {"xiaomi_mimo": {"apiKey": "mimo-key"}}},
    )

    provider = SpeechVoiceCloneService._resolve_qwen_clone_provider_from_cfg(cfg=cfg)

    assert provider.provider_id == "xiaomi_mimo"
    assert provider.clone_mode == "sample_data_uri"
    assert provider.synthesis_model == "mimo-v2.5-tts-voiceclone"
    assert provider.source_profile_id == "mimo-clone"
    assert provider.source_profile_label == "MiMo Clone"


def test_voice_clone_private_storage_path_includes_user_directory() -> None:
    path = SpeechVoiceCloneService._build_private_storage_path(tenant_id=7, user_id=5, suffix=".wav")

    assert "speech-voice-clones/7/5/" in path.as_posix()
    assert path.suffix == ".wav"


def test_voice_clone_asset_view_hides_original_branded_filename() -> None:
    view = SpeechVoiceCloneService._serialize_asset(
        SimpleNamespace(
            id=11,
            display_name="我的声音",
            source_file_name="aoju_qwen_tts.wav",
            source_content_type="audio/wav",
            source_file_size_bytes=1234,
            source_duration_ms=3200,
            transcript_text=None,
            language_type="zh",
            status="uploaded",
            last_error=None,
            created_at="2026-04-24T10:00:00Z",
            updated_at=None,
            created_by_user_id=5,
        )
    )

    assert view.display_name == "我的声音"
    assert view.source_file_name == "音频样本.wav"


@pytest.mark.asyncio
async def test_get_speech_voice_clone_workspace_endpoint_returns_alias_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeService:
        def __init__(self, db):  # noqa: ANN001
            self.db = db

        async def list_workspace(self, *, tenant_id: int, user_id: int | None = None) -> SpeechVoiceCloneWorkspacePayload:
            assert tenant_id == 7
            assert user_id == 5
            return SpeechVoiceCloneWorkspacePayload(
                support=SpeechVoiceCloneSupportView(
                    enabled=True,
                    providerId="aliyun_qwen_tts",
                    enrollmentModel="qwen-voice-enrollment",
                    synthesisModel="qwen3-tts-vc-2026-01-22",
                    maxUploadBytes=10 * 1024 * 1024,
                    maxDurationSeconds=60,
                    allowedContentTypes=["audio/mpeg", "audio/wav"],
                    note="ready",
                ),
                items=[
                    SpeechVoiceCloneWorkspaceItemView(
                        asset=SpeechVoiceCloneAssetView(
                            id=11,
                            displayName="主持人样本",
                            sourceFileName="demo.mp3",
                            sourceContentType="audio/mpeg",
                            sourceFileSizeBytes=1234,
                            sourceDurationMs=3200,
                            transcriptText="大家晚上好",
                            languageType="zh",
                            status="uploaded",
                            lastError=None,
                            createdAt="2026-04-24T10:00:00Z",
                            updatedAt=None,
                            createdByUserId=5,
                            sourceStreamUrl="/api/v1/speech/voice-clones/assets/11/source",
                        ),
                        clone=SpeechVoiceCloneView(
                            id=21,
                            assetId=11,
                            displayName="主持人音色",
                            providerId="aliyun_qwen_tts",
                            enrollmentModel="qwen-voice-enrollment",
                            synthesisModel="qwen3-tts-vc-2026-01-22",
                            remoteVoiceId="voice_clone_001",
                            languageType="zh",
                            status="ready",
                            errorMessage=None,
                            createdAt="2026-04-24T10:01:00Z",
                            updatedAt=None,
                            createdByUserId=5,
                        ),
                    )
                ],
            )

    monkeypatch.setattr(speech_endpoints, "SpeechVoiceCloneService", _FakeService)

    response = await speech_endpoints.get_speech_voice_clone_workspace(
        current_user=SimpleNamespace(id=5),
        tenant_ctx=SimpleNamespace(tenant_id=7),
        db=SimpleNamespace(),
    )

    payload = orjson.loads(response.body)
    assert payload["success"] is True
    assert payload["data"]["support"]["providerId"] == "aliyun_qwen_tts"
    assert payload["data"]["items"][0]["asset"]["displayName"] == "主持人样本"
    assert payload["data"]["items"][0]["clone"]["remoteVoiceId"] == "voice_clone_001"


@pytest.mark.asyncio
async def test_create_speech_voice_clone_endpoint_reads_upload_and_returns_item(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeService:
        def __init__(self, db):  # noqa: ANN001
            self.db = db

        async def create_voice_clone(self, **kwargs) -> SpeechVoiceCloneWorkspaceItemView:  # noqa: ANN003
            captured.update(kwargs)
            return SpeechVoiceCloneWorkspaceItemView(
                asset=SpeechVoiceCloneAssetView(
                    id=11,
                    displayName="主持人样本",
                    sourceFileName=str(kwargs["file_name"]),
                    sourceContentType=str(kwargs["content_type"]),
                    sourceFileSizeBytes=len(kwargs["audio_bytes"]),
                    sourceDurationMs=3200,
                    transcriptText="大家晚上好",
                    languageType="zh",
                    status="uploaded",
                    lastError=None,
                    createdAt="2026-04-24T10:00:00Z",
                    updatedAt=None,
                    createdByUserId=5,
                    sourceStreamUrl="/api/v1/speech/voice-clones/assets/11/source",
                ),
                clone=SpeechVoiceCloneView(
                    id=21,
                    assetId=11,
                    displayName="主持人音色",
                    providerId="aliyun_qwen_tts",
                    enrollmentModel="qwen-voice-enrollment",
                    synthesisModel="qwen3-tts-vc-2026-01-22",
                    remoteVoiceId="voice_clone_001",
                    languageType="zh",
                    status="ready",
                    errorMessage=None,
                    createdAt="2026-04-24T10:01:00Z",
                    updatedAt=None,
                    createdByUserId=5,
                ),
            )

    monkeypatch.setattr(speech_endpoints, "SpeechVoiceCloneService", _FakeService)

    upload = UploadFile(
        file=BytesIO(b"demo-audio"),
        size=len(b"demo-audio"),
        filename="host.mp3",
        headers=Headers({"content-type": "audio/mpeg"}),
    )

    response = await speech_endpoints.create_speech_voice_clone(
        current_user=SimpleNamespace(id=5),
        tenant_ctx=SimpleNamespace(tenant_id=7),
        db=SimpleNamespace(),
        file=upload,
        display_name="主持人样本",
        transcript_text="大家晚上好",
        language_type="zh",
        source_duration_ms=3200,
    )

    payload = orjson.loads(response.body)
    assert captured["tenant_id"] == 7
    assert captured["created_by_user_id"] == 5
    assert captured["file_name"] == "host.mp3"
    assert captured["content_type"] == "audio/mpeg"
    assert captured["audio_bytes"] == b"demo-audio"
    assert payload["message"] == "声音已加入复刻音色库"
    assert payload["data"]["clone"]["remoteVoiceId"] == "voice_clone_001"


@pytest.mark.asyncio
async def test_speech_text_billing_counts_input_characters() -> None:
    assert count_speech_billing_characters("偏爱") == 2
    assert str(calc_speech_text_credits("偏爱")) == "0.02"




def test_resolve_tts_provider_secrets_prefers_provider_level_secret_for_non_default_profile() -> None:
    secrets = {
        "tts": {"apiKey": "mimo-default"},
        "ttsProviders": {"aliyun_qwen_tts_realtime_sdk": {"apiKey": "qwen-key"}},
    }

    resolved = SpeechConfigService.resolve_tts_provider_secrets(
        secrets=secrets,
        provider_id="aliyun_qwen_tts_realtime_sdk",
        default_provider_id="xiaomi_mimo",
    )

    assert resolved == {"apiKey": "qwen-key"}


@pytest.mark.asyncio
async def test_demo_tts_bills_by_input_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeSpeechConfigService:
        def __init__(self, db):  # noqa: ANN001
            self.db = db

        async def get_or_create(self, *, tenant_id: int):
            assert tenant_id == 7
            return SimpleNamespace(
                config={
                    "tts": {
                        "providerId": "edge_tts",
                        "settings": {"voice": "zh-CN-XiaoxiaoNeural"},
                    }
                },
                secrets={},
            )

        def _pick_settings(self, section, *, provider_id):  # noqa: ANN001
            return dict(section.get("settings") or {})

        def _pick_secrets(self, section_secrets_raw, *, provider_id, selected_provider_id):  # noqa: ANN001
            return {}

        def _merge_secret_values(self, existing, incoming):  # noqa: ANN001
            return {**(existing or {}), **(incoming or {})}

        def resolve_tts_provider_secrets(self, *, secrets, provider_id, default_provider_id=None):  # noqa: ANN001
            return {}

    async def _fake_edge_tts_synthesize_stream(**kwargs):  # noqa: ANN003
        captured["tts"] = kwargs
        return bytes_to_stream(data=b"tts-audio", media_type="audio/mpeg", ext="mp3")

    async def _fake_bill(**kwargs):  # noqa: ANN003
        captured["billing"] = kwargs

    monkeypatch.setattr(speech_endpoints, "SpeechConfigService", _FakeSpeechConfigService)
    monkeypatch.setattr(speech_endpoints, "edge_tts_synthesize_stream", _fake_edge_tts_synthesize_stream)
    monkeypatch.setattr(speech_endpoints, "_bill_speech_tts_text", _fake_bill)

    response = await speech_endpoints.demo_tts(
        data=SimpleNamespace(text="偏爱", provider_id=None, settings={}, secrets={}, output_format=None),
        current_user=SimpleNamespace(id=5),
        tenant_ctx=SimpleNamespace(tenant_id=7),
        db=SimpleNamespace(),
    )
    chunks = [chunk async for chunk in response.body_iterator]

    assert b"".join(chunks) == b"tts-audio"
    assert captured["tts"]["text"] == "偏爱"
    assert captured["billing"]["text"] == "偏爱"
    assert captured["billing"]["reference_type"] == "speech_tts"
    assert captured["billing"]["provider_id"] == "edge_tts"
    assert captured["billing"]["voice"] == "zh-CN-XiaoxiaoNeural"


@pytest.mark.asyncio
async def test_preview_speech_voice_clone_endpoint_returns_audio_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeService:
        def __init__(self, db):  # noqa: ANN001
            self.db = db

        async def synthesize_clone_preview(self, *, tenant_id: int, clone_id: int, text: str, user_id: int | None = None):  # noqa: ANN001
            assert tenant_id == 7
            assert clone_id == 21
            assert text == "试听文案"
            assert user_id == 5
            return bytes_to_stream(data=b"preview-audio", media_type="audio/mpeg", ext="mp3")

    captured: dict[str, object] = {}

    async def _fake_bill(**kwargs):  # noqa: ANN003
        captured.update(kwargs)

    monkeypatch.setattr(speech_endpoints, "SpeechVoiceCloneService", _FakeService)
    monkeypatch.setattr(speech_endpoints, "_bill_speech_tts_text", _fake_bill)

    response = await speech_endpoints.preview_speech_voice_clone(
        clone_id=21,
        data=SimpleNamespace(text="试听文案"),
        current_user=SimpleNamespace(id=5),
        tenant_ctx=SimpleNamespace(tenant_id=7),
        db=SimpleNamespace(),
    )

    assert response.body == b"preview-audio"
    assert response.media_type == "audio/mpeg"
    assert captured["text"] == "试听文案"
    assert captured["reference_type"] == "speech_voice_clone_preview"
    assert captured["reference_id"] == 21


@pytest.mark.asyncio
async def test_stream_speech_voice_clone_asset_source_returns_file_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    sample_path = tmp_path / "sample.mp3"
    sample_path.write_bytes(b"demo-audio")

    class _FakeService:
        def __init__(self, db):  # noqa: ANN001
            self.db = db

        async def read_asset_audio(self, *, tenant_id: int, asset_id: int, user_id: int | None = None):  # noqa: ANN001
            assert tenant_id == 7
            assert asset_id == 11
            assert user_id == 5
            return sample_path, SimpleNamespace(
                id=11,
                source_content_type="audio/mpeg",
                source_file_name="sample.mp3",
            )

    monkeypatch.setattr(speech_endpoints, "SpeechVoiceCloneService", _FakeService)

    response = await speech_endpoints.stream_speech_voice_clone_asset_source(
        asset_id=11,
        current_user=SimpleNamespace(id=5),
        tenant_ctx=SimpleNamespace(tenant_id=7),
        db=SimpleNamespace(),
    )

    assert response.path == sample_path
    assert response.media_type == "audio/mpeg"
