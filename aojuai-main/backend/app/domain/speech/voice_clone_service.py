"""Tenant-level speech voice clone workspace service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any
from uuid import uuid4
import wave

try:
    from mutagen import File as MutagenFile
except Exception:  # pragma: no cover - optional dependency
    MutagenFile = None
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError
from app.domain.speech.models import SpeechTenantConfig
from app.domain.speech.providers.aliyun_qwen_tts import (
    DEFAULT_ALIYUN_QWEN_TTS_BASE_URL,
    DEFAULT_ALIYUN_QWEN_TTS_VOICE,
    aliyun_qwen_tts_synthesize_stream,
)
from app.domain.speech.providers.aliyun_qwen_voice_clone import (
    DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL,
    DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL,
    aliyun_qwen_create_voice_clone,
    aliyun_qwen_delete_voice_clone,
)
from app.domain.speech.providers.xiaomi_mimo import (
    DEFAULT_XIAOMI_MIMO_MODEL,
    build_xiaomi_mimo_voice_clone_data_uri,
    xiaomi_mimo_tts_synthesize_stream,
)
from app.domain.speech.registry import get_provider_by_id, normalize_provider_id
from app.domain.speech.service import SpeechConfigService
from app.domain.speech.voice_clone_models import SpeechVoiceCloneAsset, SpeechVoiceCloneProfile
from app.domain.speech.voice_clone_schemas import (
    SpeechVoiceCloneAssetView,
    SpeechVoiceCloneSupportView,
    SpeechVoiceCloneView,
    SpeechVoiceCloneWorkspaceItemView,
    SpeechVoiceCloneWorkspacePayload,
)
from app.infrastructure.repository import RepositoryBase

SPEECH_VOICE_CLONE_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SPEECH_VOICE_CLONE_MAX_DURATION_SECONDS = 60
SPEECH_VOICE_CLONE_ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "audio/webm",
}
SPEECH_VOICE_CLONE_CONTENT_TYPE_ALIASES = {
    "video/mp4": "audio/mp4",
}
SPEECH_VOICE_CLONE_INFERRED_CONTENT_TYPE_BY_EXTENSION = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".webm": "audio/webm",
}
SPEECH_VOICE_CLONE_FALLBACK_CONTENT_TYPES = {
    "",
    "application/octet-stream",
    "binary/octet-stream",
}
SPEECH_VOICE_CLONE_ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".webm",
}
PRIVATE_SPEECH_VOICE_CLONE_ROOT = Path(__file__).resolve().parents[3] / "private_uploads" / "speech-voice-clones"


@dataclass(slots=True)
class ResolvedSpeechVoiceCloneProvider:
    provider_id: str
    base_url: str | None
    api_key: str
    enrollment_model: str
    synthesis_model: str
    timeout_seconds: float
    provider_settings: dict[str, Any]
    provider_secrets: dict[str, Any]
    source_profile_id: str | None = None
    source_profile_label: str | None = None
    clone_mode: str = "remote_voice"


class SpeechVoiceCloneService:
    """Tenant-scoped Qwen voice clone asset and clone management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.asset_repo = RepositoryBase(db, SpeechVoiceCloneAsset)
        self.clone_repo = RepositoryBase(db, SpeechVoiceCloneProfile)
        self.speech_service = SpeechConfigService(db)

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_audio_language(language_type: str | None) -> str | None:
        normalized = str(language_type or "").strip()
        if not normalized:
            return None
        lowered = normalized.lower().replace("_", "-")
        if lowered in {"zh", "zh-cn", "zh_cn", "chinese", "中文", "普通话", "cn"}:
            return "zh"
        if lowered in {"en", "en-us", "en_us", "english", "英语"}:
            return "en"
        return normalized

    @staticmethod
    def _build_remote_preferred_name(*candidates: str | None) -> str:
        for candidate in candidates:
            normalized = re.sub(r"[^A-Za-z0-9_]+", "_", str(candidate or "").strip())
            normalized = re.sub(r"_+", "_", normalized).strip("_")
            if normalized:
                return normalized[:16]
        digest = hashlib.sha1("|".join(str(item or "") for item in candidates).encode("utf-8")).hexdigest()[:12]
        return f"vc_{digest}"[:16]

    @staticmethod
    def _private_storage_root() -> Path:
        root = PRIVATE_SPEECH_VOICE_CLONE_ROOT
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _normalize_timeout_seconds(raw_timeout: Any, *, fallback: float) -> float:
        try:
            timeout_seconds = float(raw_timeout)
        except (TypeError, ValueError):
            return fallback
        return min(max(timeout_seconds, 5.0), 300.0)

    @staticmethod
    def _normalize_voice_clone_base_url(raw_base_url: Any) -> str | None:
        normalized = str(raw_base_url or "").strip()
        if not normalized:
            return None
        if normalized.startswith("ws://") or normalized.startswith("wss://"):
            return None
        return normalized

    @classmethod
    def _build_private_storage_path(cls, *, tenant_id: int, user_id: int, suffix: str) -> Path:
        extension = suffix.lower().strip()
        if extension and not extension.startswith("."):
            extension = f".{extension}"
        filename = f"{int(cls._utcnow().timestamp())}-{uuid4().hex}{extension}"
        return cls._private_storage_root() / str(tenant_id) / str(user_id) / filename

    @staticmethod
    def _detect_audio_duration_ms(audio_path: Path) -> int:
        if MutagenFile is None:
            if audio_path.suffix.lower() == ".wav":
                try:
                    with wave.open(str(audio_path), "rb") as wav_file:
                        frame_rate = wav_file.getframerate()
                        frame_count = wav_file.getnframes()
                except Exception as exc:  # pragma: no cover
                    raise BusinessError(message="无法解析上传音频，请改用 MP3/WAV/M4A 后重试") from exc
                if frame_rate <= 0 or frame_count <= 0:
                    raise BusinessError(message="上传音频缺少有效时长信息，请改用 MP3/WAV/M4A 后重试")
                return max(int(round((frame_count / frame_rate) * 1000)), 1)
            raise BusinessError(message="当前环境缺少 mutagen 依赖，暂时无法解析 MP3/WAV/M4A 音频时长")
        try:
            audio = MutagenFile(str(audio_path))
        except Exception as exc:  # pragma: no cover
            raise BusinessError(message="无法解析上传音频，请改用 MP3/WAV/M4A 后重试") from exc
        length = getattr(getattr(audio, "info", None), "length", None)
        if not isinstance(length, int | float) or length <= 0:
            raise BusinessError(message="上传音频缺少有效时长信息，请改用 MP3/WAV/M4A 后重试")
        return max(int(round(float(length) * 1000)), 1)

    @staticmethod
    def _normalize_client_duration_ms(raw_duration_ms: Any) -> int | None:
        try:
            normalized = int(raw_duration_ms or 0)
        except (TypeError, ValueError):
            return None
        return normalized if normalized > 0 else None

    @classmethod
    def _validate_upload(
        cls,
        *,
        file_name: str,
        content_type: str,
        audio_bytes: bytes,
    ) -> tuple[str, str]:
        normalized_name = str(file_name or "").strip() or "voice-sample"
        suffix = Path(normalized_name).suffix.lower()
        if suffix not in SPEECH_VOICE_CLONE_ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(SPEECH_VOICE_CLONE_ALLOWED_EXTENSIONS))
            raise BusinessError(message=f"声音复刻目前仅支持 {allowed} 文件")
        raw_content_type = str(content_type or "").strip().lower()
        normalized_content_type = raw_content_type.split(";", 1)[0].strip()
        normalized_content_type = SPEECH_VOICE_CLONE_CONTENT_TYPE_ALIASES.get(
            normalized_content_type,
            normalized_content_type,
        )
        if normalized_content_type in SPEECH_VOICE_CLONE_FALLBACK_CONTENT_TYPES:
            normalized_content_type = SPEECH_VOICE_CLONE_INFERRED_CONTENT_TYPE_BY_EXTENSION.get(
                suffix,
                "application/octet-stream",
            )
        if normalized_content_type and normalized_content_type not in SPEECH_VOICE_CLONE_ALLOWED_CONTENT_TYPES:
            allowed = ", ".join(sorted(SPEECH_VOICE_CLONE_ALLOWED_CONTENT_TYPES))
            raise BusinessError(message=f"声音复刻音频类型不支持，仅支持 {allowed}")
        size_bytes = len(audio_bytes or b"")
        if size_bytes <= 0:
            raise BusinessError(message="上传音频为空")
        if size_bytes > SPEECH_VOICE_CLONE_MAX_UPLOAD_BYTES:
            max_mb = SPEECH_VOICE_CLONE_MAX_UPLOAD_BYTES / 1024 / 1024
            raise BusinessError(message=f"上传音频超过限制，当前仅允许 {max_mb:.0f}MB 以内")
        return normalized_name, normalized_content_type or "application/octet-stream"

    async def _get_speech_cfg(self, *, tenant_id: int) -> SpeechTenantConfig:
        return await self.speech_service.get_or_create(tenant_id=tenant_id)

    @classmethod
    def _resolve_default_profile_from_cfg(cls, *, cfg: SpeechTenantConfig) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
        config = cfg.config or {}
        secrets = cfg.secrets or {}
        default_profile = SpeechConfigService.resolve_default_tts_profile_storage(config)
        tts_section = config.get("tts") if isinstance(config, dict) else {}
        tts_secrets = secrets.get("tts") if isinstance(secrets, dict) else {}
        return (
            tts_section if isinstance(tts_section, dict) else {},
            tts_secrets if isinstance(tts_secrets, dict) else {},
            default_profile,
        )

    @classmethod
    def _iter_voice_clone_candidate_profiles(cls, *, cfg: SpeechTenantConfig) -> list[dict[str, Any]]:
        config = cfg.config or {}
        profiles = SpeechConfigService._normalize_tts_profiles_storage(  # noqa: SLF001 - shared storage normalizer
            config.get("ttsProfiles") if isinstance(config, dict) else []
        )
        default_id = SpeechConfigService._resolve_default_tts_profile_id(  # noqa: SLF001
            profiles,
            requested_default_id=(config.get("defaultTtsProfileId") if isinstance(config, dict) else None),
        )
        default_profile = next((item for item in profiles if str(item.get("id") or "").strip() == str(default_id or "")), None)
        ordered: list[dict[str, Any]] = []
        if default_profile is not None:
            ordered.append(default_profile)
        ordered.extend(
            item
            for item in profiles
            if bool(item.get("allowVoiceClone")) and str(item.get("id") or "").strip() != str(default_id or "")
        )
        return ordered

    @classmethod
    def _resolve_qwen_clone_provider_from_cfg(
        cls,
        *,
        cfg: SpeechTenantConfig,
    ) -> ResolvedSpeechVoiceCloneProvider:
        config = cfg.config or {}
        secrets = cfg.secrets or {}
        failures: list[str] = []

        for profile in cls._iter_voice_clone_candidate_profiles(cfg=cfg):
            provider_id = normalize_provider_id(profile.get("providerId"))
            allow_voice_clone = bool(profile.get("allowVoiceClone"))
            label = str(profile.get("label") or profile.get("id") or provider_id or "模型").strip()
            profile_id = str(profile.get("id") or "").strip() or None
            if not provider_id or not allow_voice_clone:
                continue

            descriptor = get_provider_by_id(provider_id)
            if descriptor is None or not bool(getattr(descriptor.capabilities, "supports_voice_clone", False)):
                failures.append(f"{label} 不支持声音复刻")
                continue

            provider_settings = profile.get("settings") if isinstance(profile.get("settings"), dict) else {}
            secrets_with_profiles = dict(secrets) if isinstance(secrets, dict) else {}
            secrets_with_profiles["__config_tts_profiles"] = config.get("ttsProfiles") if isinstance(config, dict) else []
            provider_secrets = SpeechConfigService.resolve_tts_provider_secrets(
                secrets=secrets_with_profiles,
                provider_id=provider_id,
                default_provider_id=(config.get("tts") or {}).get("providerId") if isinstance(config.get("tts"), dict) else None,
            )
            api_key = str(provider_secrets.get("apiKey") or "").strip()
            if not api_key:
                failures.append(f"{label} 未配置 API Key")
                continue

            if provider_id in {"aliyun_qwen_tts", "aliyun_qwen_tts_realtime_sdk"}:
                return ResolvedSpeechVoiceCloneProvider(
                    provider_id=provider_id,
                    base_url=cls._normalize_voice_clone_base_url(provider_settings.get("baseUrl")),
                    api_key=api_key,
                    enrollment_model=DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL,
                    synthesis_model=DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL,
                    timeout_seconds=cls._normalize_timeout_seconds(provider_settings.get("timeoutSeconds"), fallback=120.0),
                    provider_settings=provider_settings,
                    provider_secrets=provider_secrets,
                    source_profile_id=profile_id,
                    source_profile_label=label,
                    clone_mode="remote_voice",
                )

            if provider_id == "xiaomi_mimo":
                model = str(provider_settings.get("model") or DEFAULT_XIAOMI_MIMO_MODEL).strip()
                if model != "mimo-v2.5-tts-voiceclone":
                    failures.append(f"{label} 需要选择 mimo-v2.5-tts-voiceclone")
                    continue
                return ResolvedSpeechVoiceCloneProvider(
                    provider_id=provider_id,
                    base_url=str(provider_settings.get("baseUrl") or "").strip() or None,
                    api_key=api_key,
                    enrollment_model="mimo-v2.5-tts-voiceclone",
                    synthesis_model="mimo-v2.5-tts-voiceclone",
                    timeout_seconds=cls._normalize_timeout_seconds(provider_settings.get("timeoutSeconds"), fallback=120.0),
                    provider_settings=provider_settings,
                    provider_secrets=provider_secrets,
                    source_profile_id=profile_id,
                    source_profile_label=label,
                    clone_mode="sample_data_uri",
                )

            failures.append(f"{label} 尚未接入可复用的复刻通道")

        if failures:
            raise BusinessError(message="；".join(failures[:3]))
        raise BusinessError(message="当前租户没有开启可用的声音复刻候选模型。")

    async def build_support_view(self, *, tenant_id: int) -> SpeechVoiceCloneSupportView:
        cfg = await self._get_speech_cfg(tenant_id=tenant_id)
        try:
            provider = self._resolve_qwen_clone_provider_from_cfg(cfg=cfg)
        except BusinessError as exc:
            tts_section, _tts_secrets, _default_profile = self._resolve_default_profile_from_cfg(cfg=cfg)
            candidates = self._iter_voice_clone_candidate_profiles(cfg=cfg)
            candidate_provider_id = normalize_provider_id(candidates[0].get("providerId")) if candidates else normalize_provider_id(tts_section.get("providerId"))
            return SpeechVoiceCloneSupportView(
                enabled=False,
                providerId=candidate_provider_id or None,
                enrollmentModel=DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL,
                synthesisModel=DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL,
                maxUploadBytes=SPEECH_VOICE_CLONE_MAX_UPLOAD_BYTES,
                maxDurationSeconds=SPEECH_VOICE_CLONE_MAX_DURATION_SECONDS,
                allowedContentTypes=sorted(SPEECH_VOICE_CLONE_ALLOWED_CONTENT_TYPES),
                note=str(exc.message or "当前租户暂未启用声音复刻"),
            )

        return SpeechVoiceCloneSupportView(
            enabled=True,
            providerId=provider.provider_id,
            enrollmentModel=provider.enrollment_model,
            synthesisModel=provider.synthesis_model,
            maxUploadBytes=SPEECH_VOICE_CLONE_MAX_UPLOAD_BYTES,
            maxDurationSeconds=SPEECH_VOICE_CLONE_MAX_DURATION_SECONDS,
            allowedContentTypes=sorted(SPEECH_VOICE_CLONE_ALLOWED_CONTENT_TYPES),
            note="当前已可创建个人音色。创建后可以直接用于语音合成。",
        )

    async def _get_asset(self, *, tenant_id: int, asset_id: int) -> SpeechVoiceCloneAsset:
        asset = await self.asset_repo.get_one(
            where=[
                SpeechVoiceCloneAsset.id == asset_id,
                SpeechVoiceCloneAsset.tenant_id == tenant_id,
            ]
        )
        if asset is None or str(asset.status or "").strip() == "deleted":
            raise NotFoundError(message="声音资产不存在")
        return asset

    async def _get_clone(self, *, tenant_id: int, clone_id: int) -> SpeechVoiceCloneProfile:
        clone = await self.clone_repo.get_one(
            where=[
                SpeechVoiceCloneProfile.id == clone_id,
                SpeechVoiceCloneProfile.tenant_id == tenant_id,
            ]
        )
        if clone is None or str(clone.status or "").strip() == "deleted":
            raise NotFoundError(message="复刻音色不存在")
        return clone

    @staticmethod
    def _serialize_asset(asset: SpeechVoiceCloneAsset) -> SpeechVoiceCloneAssetView:
        source_extension = Path(str(asset.source_file_name or "").strip()).suffix.lower()
        source_file_label = f"音频样本{source_extension}" if source_extension else "音频样本"
        return SpeechVoiceCloneAssetView(
            id=asset.id,
            displayName=str(asset.display_name or "").strip(),
            sourceFileName=source_file_label,
            sourceContentType=str(asset.source_content_type or "").strip(),
            sourceFileSizeBytes=max(int(asset.source_file_size_bytes or 0), 0),
            sourceDurationMs=max(int(asset.source_duration_ms or 0), 0),
            transcriptText=str(asset.transcript_text or "").strip() or None,
            languageType=str(asset.language_type or "").strip() or None,
            status=str(asset.status or "").strip() or "uploaded",
            lastError=str(asset.last_error or "").strip() or None,
            createdAt=asset.created_at,
            updatedAt=asset.updated_at,
            createdByUserId=int(asset.created_by_user_id or 0),
            sourceStreamUrl=f"/api/v1/speech/voice-clones/assets/{asset.id}/source",
        )

    @staticmethod
    def _serialize_clone(clone: SpeechVoiceCloneProfile) -> SpeechVoiceCloneView:
        return SpeechVoiceCloneView(
            id=clone.id,
            assetId=clone.asset_id,
            displayName=str(clone.display_name or "").strip(),
            providerId=str(clone.provider_id or "").strip() or "aliyun_qwen_tts",
            enrollmentModel=str(clone.enrollment_model or "").strip() or DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL,
            synthesisModel=str(clone.synthesis_model or "").strip() or DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL,
            remoteVoiceId=str(clone.remote_voice_id or "").strip(),
            languageType=str(clone.language_type or "").strip() or None,
            status=str(clone.status or "").strip() or "ready",
            errorMessage=str(clone.error_message or "").strip() or None,
            createdAt=clone.created_at,
            updatedAt=clone.updated_at,
            createdByUserId=int(clone.created_by_user_id or 0),
        )

    async def list_workspace(self, *, tenant_id: int, user_id: int | None = None) -> SpeechVoiceCloneWorkspacePayload:
        asset_filters = [SpeechVoiceCloneAsset.tenant_id == tenant_id]
        clone_filters = [SpeechVoiceCloneProfile.tenant_id == tenant_id]
        if user_id is not None:
            asset_filters.append(SpeechVoiceCloneAsset.created_by_user_id == int(user_id))
            clone_filters.append(SpeechVoiceCloneProfile.created_by_user_id == int(user_id))
        assets = await self.asset_repo.get_list(
            page_size=0,
            where=asset_filters,
            order_by="created_at",
            order_desc=True,
        )
        clones = await self.clone_repo.get_list(
            page_size=0,
            where=clone_filters,
            order_by="created_at",
            order_desc=True,
        )
        clone_by_asset_id = {
            item.asset_id: item
            for item in clones
            if str(item.status or "").strip() != "deleted"
        }
        items = [
            SpeechVoiceCloneWorkspaceItemView(
                asset=self._serialize_asset(asset),
                clone=self._serialize_clone(clone_by_asset_id.get(asset.id))
                if clone_by_asset_id.get(asset.id) is not None
                else None,
            )
            for asset in assets
            if str(asset.status or "").strip() != "deleted"
        ]
        return SpeechVoiceCloneWorkspacePayload(
            support=await self.build_support_view(tenant_id=tenant_id),
            items=items,
        )

    async def create_voice_clone(
        self,
        *,
        tenant_id: int,
        created_by_user_id: int,
        file_name: str,
        content_type: str,
        audio_bytes: bytes,
        display_name: str | None = None,
        transcript_text: str | None = None,
        language_type: str | None = None,
        source_duration_ms: int | None = None,
    ) -> SpeechVoiceCloneWorkspaceItemView:
        cfg = await self._get_speech_cfg(tenant_id=tenant_id)
        provider = self._resolve_qwen_clone_provider_from_cfg(cfg=cfg)
        normalized_name, normalized_content_type = self._validate_upload(
            file_name=file_name,
            content_type=content_type,
            audio_bytes=audio_bytes,
        )
        resolved_display_name = str(display_name or "").strip() or "我的声音"
        remote_preferred_name = self._build_remote_preferred_name(display_name, "voice_clone")
        storage_path = self._build_private_storage_path(
            tenant_id=tenant_id,
            user_id=created_by_user_id,
            suffix=Path(normalized_name).suffix,
        )
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(audio_bytes)
        remote_voice_id = ""
        try:
            try:
                duration_ms = self._detect_audio_duration_ms(storage_path)
            except BusinessError:
                duration_ms = self._normalize_client_duration_ms(source_duration_ms)
                if duration_ms is None:
                    raise
            if duration_ms > SPEECH_VOICE_CLONE_MAX_DURATION_SECONDS * 1000:
                raise BusinessError(message=f"上传音频时长超过限制，当前仅允许 {SPEECH_VOICE_CLONE_MAX_DURATION_SECONDS} 秒以内")

            normalized_language = self._normalize_audio_language(language_type)
            clone_result = None
            if provider.clone_mode == "sample_data_uri":
                remote_voice_id = f"mimo-asset:{hashlib.sha256(audio_bytes).hexdigest()[:16]}"
            else:
                clone_result = await aliyun_qwen_create_voice_clone(
                    api_key=provider.api_key,
                    audio_bytes=audio_bytes,
                    content_type=normalized_content_type,
                    preferred_name=remote_preferred_name,
                    text=str(transcript_text or "").strip() or None,
                    language=normalized_language,
                    base_url=provider.base_url,
                    model=provider.enrollment_model,
                    target_model=provider.synthesis_model,
                    count=1,
                    timeout_seconds=provider.timeout_seconds,
                )
                remote_voice_id = str(clone_result.voice or "").strip()

            asset = await self.asset_repo.create(
                {
                    "tenant_id": tenant_id,
                    "created_by_user_id": created_by_user_id,
                    "display_name": resolved_display_name,
                    "source_file_name": normalized_name,
                    "source_content_type": normalized_content_type,
                    "source_file_size_bytes": len(audio_bytes),
                    "source_duration_ms": duration_ms,
                    "source_storage_path": str(storage_path),
                    "source_sha256": hashlib.sha256(audio_bytes).hexdigest(),
                    "transcript_text": str(transcript_text or "").strip() or None,
                    "language_type": normalized_language,
                    "status": "uploaded",
                    "extra": {},
                }
            )
            clone = await self.clone_repo.create(
                {
                    "tenant_id": tenant_id,
                    "asset_id": asset.id,
                    "created_by_user_id": created_by_user_id,
                    "display_name": resolved_display_name,
                    "provider_id": provider.provider_id,
                    "enrollment_model": provider.enrollment_model,
                    "synthesis_model": provider.synthesis_model,
                    "remote_voice_id": remote_voice_id,
                    "language_type": normalized_language,
                    "status": "ready",
                    "extra": {
                        "requestId": getattr(clone_result, "request_id", None),
                        "count": getattr(clone_result, "count", 1) if clone_result is not None else 1,
                        "preferredName": remote_preferred_name,
                        "sourceProfileId": provider.source_profile_id,
                        "sourceProfileLabel": provider.source_profile_label,
                        "cloneMode": provider.clone_mode,
                    },
                }
            )
            return SpeechVoiceCloneWorkspaceItemView(
                asset=self._serialize_asset(asset),
                clone=self._serialize_clone(clone),
            )
        except Exception:
            if remote_voice_id and provider.clone_mode == "remote_voice":
                try:
                    await aliyun_qwen_delete_voice_clone(
                        api_key=provider.api_key,
                        voice=remote_voice_id,
                        base_url=provider.base_url,
                        timeout_seconds=provider.timeout_seconds,
                    )
                except Exception:
                    pass
            if storage_path.exists():
                storage_path.unlink(missing_ok=True)
            raise

    async def delete_clone(
        self,
        *,
        tenant_id: int,
        clone_id: int,
        user_id: int | None = None,
    ) -> None:
        clone = await self._get_clone(tenant_id=tenant_id, clone_id=clone_id)
        if user_id is not None and int(clone.created_by_user_id or 0) != int(user_id):
            raise NotFoundError(message="复刻音色不存在")
        asset = await self._get_asset(tenant_id=tenant_id, asset_id=clone.asset_id)
        if user_id is not None and int(asset.created_by_user_id or 0) != int(user_id):
            raise NotFoundError(message="声音资产不存在")
        cfg = await self._get_speech_cfg(tenant_id=tenant_id)
        remote_delete_error: str | None = None
        try:
            provider = self._resolve_qwen_clone_provider_from_cfg(cfg=cfg)
            if str(clone.provider_id or "").strip() == "aliyun_qwen_tts":
                await aliyun_qwen_delete_voice_clone(
                    api_key=provider.api_key,
                    voice=str(clone.remote_voice_id or "").strip(),
                    base_url=provider.base_url,
                    timeout_seconds=provider.timeout_seconds,
                )
        except BusinessError as exc:
            remote_delete_error = str(exc.message or "remote_delete_failed")

        await self.clone_repo.update(
            clone,
            {"status": "deleted", "error_message": remote_delete_error},
            exclude_unset=False,
        )
        await self.asset_repo.update(
            asset,
            {"status": "deleted", "last_error": remote_delete_error},
            exclude_unset=False,
        )
        storage_path = Path(str(asset.source_storage_path or "").strip())
        if storage_path.exists() and storage_path.is_file():
            storage_path.unlink(missing_ok=True)

    async def read_asset_audio(self, *, tenant_id: int, asset_id: int, user_id: int | None = None) -> tuple[Path, SpeechVoiceCloneAsset]:
        asset = await self._get_asset(tenant_id=tenant_id, asset_id=asset_id)
        if user_id is not None and int(asset.created_by_user_id or 0) != int(user_id):
            raise NotFoundError(message="声音资产不存在")
        storage_path = Path(str(asset.source_storage_path or "").strip())
        if not storage_path.exists() or not storage_path.is_file():
            raise NotFoundError(message="声音资产源文件不存在")
        return storage_path, asset

    async def synthesize_clone_preview(
        self,
        *,
        tenant_id: int,
        clone_id: int,
        text: str,
        user_id: int | None = None,
    ):
        clone = await self._get_clone(tenant_id=tenant_id, clone_id=clone_id)
        if user_id is not None and int(clone.created_by_user_id or 0) != int(user_id):
            raise NotFoundError(message="复刻音色不存在")
        cfg = await self._get_speech_cfg(tenant_id=tenant_id)
        provider = self._resolve_qwen_clone_provider_from_cfg(cfg=cfg)
        if str(clone.provider_id or "").strip() == "xiaomi_mimo":
            asset = await self._get_asset(tenant_id=tenant_id, asset_id=int(clone.asset_id))
            storage_path = Path(str(asset.source_storage_path or "").strip())
            if not storage_path.exists() or not storage_path.is_file():
                raise NotFoundError(message="声音资产源文件不存在")
            voice_data_uri = build_xiaomi_mimo_voice_clone_data_uri(
                audio_bytes=storage_path.read_bytes(),
                content_type=str(asset.source_content_type or ""),
            )
            return await xiaomi_mimo_tts_synthesize_stream(
                api_key=provider.api_key,
                text=text,
                base_url=provider.provider_settings.get("baseUrl"),
                model=str(clone.synthesis_model or "mimo-v2.5-tts-voiceclone"),
                voice=voice_data_uri,
                style=str(provider.provider_settings.get("style") or "").strip() or None,
                text_injection_mode=str(provider.provider_settings.get("textInjectionMode") or "plain"),
                audio_format=str(provider.provider_settings.get("audioFormat") or provider.provider_settings.get("format") or "wav"),
                request_overrides=provider.provider_settings.get("requestOverrides"),
                timeout_seconds=provider.timeout_seconds,
            )

        return await aliyun_qwen_tts_synthesize_stream(
            api_key=provider.api_key,
            text=text,
            base_url=DEFAULT_ALIYUN_QWEN_TTS_BASE_URL,
            model=str(clone.synthesis_model or DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL),
            voice=str(clone.remote_voice_id or "").strip() or DEFAULT_ALIYUN_QWEN_TTS_VOICE,
            language_type=str(clone.language_type or "").strip() or None,
            instructions=str(provider.provider_settings.get("instructions") or "").strip() or None,
            optimize_instructions=bool(provider.provider_settings.get("optimizeInstructions") or False),
            stream=False,
            request_overrides=provider.provider_settings.get("requestOverrides"),
            timeout_seconds=provider.timeout_seconds,
        )
