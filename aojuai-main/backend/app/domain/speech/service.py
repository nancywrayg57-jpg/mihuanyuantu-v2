"""
AOJU Backend - Speech Config Service

租户级语音配置（TTS/STT）读写与校验。
当前仅做配置管理与 provider 选项输出，不包含实际语音合成/识别运行逻辑。
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError
from app.domain.speech.models import SpeechTenantConfig
from app.domain.speech.registry import (
    get_provider_by_id,
    get_provider_secret_keys,
    get_speech_provider_catalog,
    normalize_provider_id,
)
from app.domain.speech.schemas import (
    SpeechBargeInConfig,
    SpeechProviderDescriptor,
    SpeechProviderProfileView,
    SpeechProviderSelection,
    SpeechTenantConfigUpsertRequest,
    SpeechTenantConfigView,
)
from app.infrastructure.repository import RepositoryBase


class SpeechConfigService(RepositoryBase[SpeechTenantConfig]):
    """Speech tenant config service"""

    ACTIVE_STATUS = "active"
    DISABLED_STATUS = "disabled"
    ALLOWED_STATUSES = {ACTIVE_STATUS, DISABLED_STATUS, "degraded", "error"}
    STATUS_ALIASES = {
        "enabled": ACTIVE_STATUS,
        "inactive": DISABLED_STATUS,
        "off": DISABLED_STATUS,
        "ready": ACTIVE_STATUS,
        "healthy": ACTIVE_STATUS,
    }

    def __init__(self, db: AsyncSession):
        super().__init__(db, SpeechTenantConfig)

    @staticmethod
    def _normalize_profile_id(value: Any, *, fallback: str) -> str:
        normalized = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower()).strip("-")
        return normalized or fallback

    @classmethod
    def _normalize_status_token(cls, value: Any) -> str:
        raw_status = str(value or "").strip().lower()
        return cls.STATUS_ALIASES.get(raw_status, raw_status)

    @classmethod
    def _resolve_enabled_flag(cls, *, status: Any, is_active: Any | None) -> bool:
        normalized_status = cls._normalize_status_token(status)
        if normalized_status == cls.DISABLED_STATUS:
            return False
        if normalized_status:
            return True
        if is_active is None:
            return True
        return bool(is_active)

    @classmethod
    def _normalize_status(cls, value: Any, *, enabled: bool) -> str:
        raw = cls._normalize_status_token(value)

        if raw == cls.DISABLED_STATUS:
            return cls.DISABLED_STATUS
        if not enabled:
            return cls.DISABLED_STATUS
        if not raw:
            return cls.ACTIVE_STATUS
        if raw not in cls.ALLOWED_STATUSES:
            allowed = ", ".join(sorted(cls.ALLOWED_STATUSES))
            raise BusinessError(message=f"不支持的语音配置状态: {value}，允许值: {allowed}")
        return raw

    @classmethod
    def _resolve_availability_state(cls, *, status: Any, is_active: Any | None) -> tuple[bool, str]:
        enabled = cls._resolve_enabled_flag(status=status, is_active=is_active)
        normalized_status = cls._normalize_status(status, enabled=enabled)
        return enabled, normalized_status

    async def get_or_create(self, *, tenant_id: int) -> SpeechTenantConfig:
        existing = await self.get_one(where=[SpeechTenantConfig.tenant_id == tenant_id])
        if existing:
            return existing

        try:
            return await self.create(
                {
                    "tenant_id": tenant_id,
                    "status": self.ACTIVE_STATUS,
                    "is_active": True,
                    "config": {
                        "tts": {"providerId": None, "settings": {}},
                        "ttsProfiles": [],
                        "defaultTtsProfileId": None,
                        "stt": {"providerId": None, "settings": {}},
                        "bargeIn": SpeechBargeInConfig().model_dump(by_alias=True),
                    },
                    "secrets": {"tts": {}, "ttsProfiles": {}, "stt": {}},
                }
            )
        except IntegrityError:
            await self.db.rollback()
            existing = await self.get_one(where=[SpeechTenantConfig.tenant_id == tenant_id])
            if not existing:
                raise
            return existing

    @staticmethod
    def list_providers() -> list[SpeechProviderDescriptor]:
        return list(get_speech_provider_catalog())

    @staticmethod
    def _validate_provider(provider_id: str, *, category: str) -> None:
        normalized_provider_id = normalize_provider_id(provider_id)
        provider = get_provider_by_id(normalized_provider_id)
        if not provider:
            raise BusinessError(message=f"不支持的 provider: {provider_id}")
        if provider.category != category:
            raise BusinessError(message=f"provider 类型不匹配: {provider_id} 不是 {category}")

    @staticmethod
    def _merge_dict(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
        """Shallow merge dict (src overrides dst)."""
        if not src:
            return dst
        merged = dict(dst)
        merged.update(src)
        return merged

    @staticmethod
    def _pick_settings(section: Any, *, provider_id: str | None) -> dict[str, Any]:
        """
        Pick settings from section config.

        Supports both legacy and current formats:
        - legacy: {"providerId": "...", "providers": {"pid": {...}}}
        - current: {"providerId": "...", "settings": {...}}
        """
        if not isinstance(section, dict):
            return {}

        normalized_provider_id = normalize_provider_id(provider_id)

        settings = section.get("settings")
        if isinstance(settings, dict):
            selected_pid = normalize_provider_id(section.get("providerId"))
            if normalized_provider_id and selected_pid and normalized_provider_id != selected_pid:
                return {}
            return dict(settings)

        providers = section.get("providers")
        if isinstance(providers, dict) and normalized_provider_id:
            raw = providers.get(normalized_provider_id)
            if not isinstance(raw, dict) and provider_id:
                raw = providers.get(provider_id)
            return dict(raw) if isinstance(raw, dict) else {}

        return {}

    @staticmethod
    def _pick_secrets(
        section_secrets: Any,
        *,
        provider_id: str | None,
        selected_provider_id: str | None,
    ) -> dict[str, Any]:
        """
        Pick secrets from secrets section.

        Supports both legacy and current formats:
        - legacy: {"pid": {"apiKey": "..."}}
        - current: {"apiKey": "..."}
        """
        if not isinstance(section_secrets, dict):
            return {}

        normalized_provider_id = normalize_provider_id(provider_id)
        normalized_selected_provider_id = normalize_provider_id(selected_provider_id)

        if normalized_provider_id and isinstance(section_secrets.get(normalized_provider_id), dict):
            # legacy format
            return dict(section_secrets.get(normalized_provider_id) or {})
        if provider_id and isinstance(section_secrets.get(provider_id), dict):
            return dict(section_secrets.get(provider_id) or {})

        # current format
        if normalized_provider_id and normalized_selected_provider_id and normalized_provider_id != normalized_selected_provider_id:
            return {}
        return dict(section_secrets)

    @classmethod
    def _normalize_tts_provider_secret_map(cls, raw: Any) -> dict[str, dict[str, Any]]:
        source = raw if isinstance(raw, dict) else {}
        result: dict[str, dict[str, Any]] = {}
        for raw_provider_id, raw_secrets in source.items():
            provider_id = normalize_provider_id(raw_provider_id)
            if not provider_id:
                continue
            try:
                cls._validate_provider(provider_id, category="tts")
            except BusinessError:
                continue
            if isinstance(raw_secrets, dict):
                result[provider_id] = cls._merge_secret_values({}, raw_secrets)
        return result

    @classmethod
    def _build_section_secrets_set(cls, provider_id: str | None, raw_secrets: Any) -> dict[str, bool]:
        normalized_provider_id = normalize_provider_id(provider_id)
        source = raw_secrets if isinstance(raw_secrets, dict) else {}
        secret_keys = get_provider_secret_keys(normalized_provider_id) if normalized_provider_id else set()
        if secret_keys:
            return {key: bool(str(source.get(key) or "").strip()) for key in sorted(secret_keys)}
        return {str(key): bool(str(value or "").strip()) for key, value in source.items()}

    def _build_secrets_set(self, *, config: dict[str, Any], secrets: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        tts_provider_secrets = self._normalize_tts_provider_secret_map(secrets.get("ttsProviders"))

        def build_section(section_key: str) -> None:
            section = config.get(section_key) or {}
            provider_id = normalize_provider_id(section.get("providerId"))
            if not provider_id:
                return
            if section_key == "tts" and provider_id in tts_provider_secrets:
                result[section_key] = self._build_section_secrets_set(provider_id, tts_provider_secrets.get(provider_id))
                return
            section_secrets_raw = secrets.get(section_key) if isinstance(secrets, dict) else None
            section_secrets = self._pick_secrets(section_secrets_raw, provider_id=provider_id, selected_provider_id=provider_id)
            secrets_set = self._build_section_secrets_set(provider_id, section_secrets)
            if secrets_set:
                result[section_key] = secrets_set

        build_section("tts")
        build_section("stt")

        raw_profiles = self._normalize_tts_profiles_storage(config.get("ttsProfiles"))
        if raw_profiles:
            profile_result: dict[str, Any] = {}
            profile_secrets_map = secrets.get("ttsProfiles") if isinstance(secrets.get("ttsProfiles"), dict) else {}
            for profile in raw_profiles:
                profile_id = str(profile.get("id") or "").strip()
                provider_id = normalize_provider_id(profile.get("providerId"))
                if not profile_id or not provider_id:
                    continue
                raw_profile_secrets = profile_secrets_map.get(profile_id) if isinstance(profile_secrets_map, dict) else {}
                profile_secrets = raw_profile_secrets if isinstance(raw_profile_secrets, dict) else {}
                if not any(str(value or "").strip() for value in profile_secrets.values()):
                    profile_secrets = tts_provider_secrets.get(provider_id) or {}
                profile_result[profile_id] = self._build_section_secrets_set(provider_id, profile_secrets)
            if profile_result:
                result["ttsProfiles"] = profile_result
        return result


    @classmethod
    def resolve_tts_provider_secrets(cls, *, secrets: dict[str, Any], provider_id: str, default_provider_id: str | None = None) -> dict[str, Any]:
        normalized_provider_id = normalize_provider_id(provider_id)
        if not normalized_provider_id:
            return {}

        provider_secrets = cls._normalize_tts_provider_secret_map(secrets.get("ttsProviders"))
        if normalized_provider_id in provider_secrets:
            return dict(provider_secrets.get(normalized_provider_id) or {})

        profile_secrets_map = secrets.get("ttsProfiles") if isinstance(secrets.get("ttsProfiles"), dict) else {}
        config_profiles = secrets.get("__config_tts_profiles") if isinstance(secrets.get("__config_tts_profiles"), list) else []
        if isinstance(profile_secrets_map, dict):
            for raw_profile in config_profiles:
                profile = raw_profile if isinstance(raw_profile, dict) else {}
                if normalize_provider_id(profile.get("providerId")) != normalized_provider_id:
                    continue
                profile_id = str(profile.get("id") or "").strip()
                raw = profile_secrets_map.get(profile_id)
                if isinstance(raw, dict) and any(str(value or "").strip() for value in raw.values()):
                    return cls._merge_secret_values({}, raw)

        if normalized_provider_id == normalize_provider_id(default_provider_id):
            raw_default = secrets.get("tts") if isinstance(secrets.get("tts"), dict) else {}
            if isinstance(raw_default, dict):
                return cls._merge_secret_values({}, raw_default)
        return {}

    @classmethod
    def _normalize_legacy_section(cls, raw: Any, *, category: str) -> dict[str, Any]:
        source = raw if isinstance(raw, dict) else {}
        provider_id = normalize_provider_id(source.get("providerId") or source.get("provider_id"))
        if provider_id:
            cls._validate_provider(provider_id, category=category)
        settings = source.get("settings") if isinstance(source.get("settings"), dict) else {}
        secrets = source.get("secrets") if isinstance(source.get("secrets"), dict) else {}
        return {
            "providerId": provider_id or None,
            "settings": deepcopy(settings),
            "secrets": deepcopy(secrets),
        }

    @staticmethod
    def _merge_secret_values(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = dict(existing or {})
        for key, value in (incoming or {}).items():
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            merged[str(key)] = value
        return merged

    @classmethod
    def _build_legacy_section_view(cls, section: dict[str, Any]) -> dict[str, Any]:
        provider_id = normalize_provider_id(section.get("providerId"))
        secrets = section.get("secrets") if isinstance(section.get("secrets"), dict) else {}
        secret_keys = get_provider_secret_keys(provider_id) if provider_id else set()
        if secret_keys:
            secrets_set = {key: bool(str(secrets.get(key) or "").strip()) for key in sorted(secret_keys)}
        else:
            secrets_set = {str(key): bool(str(value or "").strip()) for key, value in secrets.items()}
        return {
            "providerId": provider_id or None,
            "settings": deepcopy(section.get("settings") if isinstance(section.get("settings"), dict) else {}),
            "secretsSet": secrets_set,
        }

    @classmethod
    def _normalize_tts_profiles_storage(cls, raw_profiles: Any) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        if not isinstance(raw_profiles, list):
            return normalized

        for index, raw_profile in enumerate(raw_profiles):
            source = raw_profile if isinstance(raw_profile, dict) else {}
            provider_id = normalize_provider_id(source.get("providerId") or source.get("provider_id"))
            if not provider_id:
                continue
            cls._validate_provider(provider_id, category="tts")

            normalized.append(
                {
                    "id": cls._normalize_profile_id(source.get("id"), fallback=f"tts-profile-{index + 1}"),
                    "label": str(source.get("label") or f"模型 {index + 1}").strip() or f"模型 {index + 1}",
                    "providerId": provider_id,
                    "settings": deepcopy(source.get("settings") if isinstance(source.get("settings"), dict) else {}),
                    "allowVoiceClone": bool(source.get("allowVoiceClone")),
                    "isDefault": bool(source.get("isDefault")),
                }
            )
        return normalized

    @classmethod
    def _resolve_default_tts_profile_id(
        cls,
        profiles: list[dict[str, Any]],
        *,
        requested_default_id: Any | None = None,
    ) -> str | None:
        requested = str(requested_default_id or "").strip()
        if requested and any(str(item.get("id") or "").strip() == requested for item in profiles):
            return requested

        explicit = next((str(item.get("id") or "").strip() for item in profiles if bool(item.get("isDefault"))), "")
        if explicit:
            return explicit

        first = next((str(item.get("id") or "").strip() for item in profiles if str(item.get("id") or "").strip()), "")
        return first or None

    @classmethod
    def _sync_default_tts_from_profiles(cls, *, config: dict[str, Any], secrets: dict[str, Any]) -> None:
        profiles = cls._normalize_tts_profiles_storage(config.get("ttsProfiles"))
        default_id = cls._resolve_default_tts_profile_id(
            profiles,
            requested_default_id=config.get("defaultTtsProfileId"),
        )

        config["ttsProfiles"] = profiles
        config["defaultTtsProfileId"] = default_id

        if not default_id:
            config["tts"] = {"providerId": None, "settings": {}}
            secrets["tts"] = {}
            return

        default_profile = next(
            (item for item in profiles if str(item.get("id") or "").strip() == default_id),
            None,
        )
        if default_profile is None:
            config["tts"] = {"providerId": None, "settings": {}}
            secrets["tts"] = {}
            return

        config["tts"] = {
            "providerId": default_profile.get("providerId"),
            "settings": deepcopy(default_profile.get("settings") if isinstance(default_profile.get("settings"), dict) else {}),
        }

        provider_id = normalize_provider_id(default_profile.get("providerId"))
        tts_profile_secrets = secrets.get("ttsProfiles") if isinstance(secrets.get("ttsProfiles"), dict) else {}
        tts_provider_secrets = cls._normalize_tts_provider_secret_map(secrets.get("ttsProviders"))
        selected_profile_secrets = tts_provider_secrets.get(provider_id) or (
            tts_profile_secrets.get(default_id)
            if isinstance(tts_profile_secrets, dict)
            else {}
        )
        secrets["tts"] = deepcopy(selected_profile_secrets if isinstance(selected_profile_secrets, dict) else {})

    @classmethod
    def merge(cls, raw: Any, incoming: Any) -> dict[str, Any]:
        stored = raw if isinstance(raw, dict) else {}
        source = incoming if isinstance(incoming, dict) else {}

        merged_tts = cls._normalize_legacy_section(stored.get("tts"), category="tts")
        incoming_tts = source.get("tts") if isinstance(source.get("tts"), dict) else None
        if isinstance(incoming_tts, dict):
            provider_id = normalize_provider_id(
                incoming_tts.get("providerId")
                or incoming_tts.get("provider_id")
                or merged_tts.get("providerId")
                or ""
            )
            if provider_id:
                cls._validate_provider(provider_id, category="tts")
                merged_tts["providerId"] = provider_id
            if isinstance(incoming_tts.get("settings"), dict):
                merged_tts["settings"] = cls._merge_dict(
                    merged_tts.get("settings") if isinstance(merged_tts.get("settings"), dict) else {},
                    incoming_tts.get("settings") or {},
                )
            if isinstance(incoming_tts.get("secrets"), dict):
                merged_tts["secrets"] = cls._merge_secret_values(
                    merged_tts.get("secrets") if isinstance(merged_tts.get("secrets"), dict) else {},
                    incoming_tts.get("secrets") or {},
                )

        merged_tts_profiles = cls._normalize_tts_profiles_storage(stored.get("ttsProfiles"))
        incoming_tts_profiles = source.get("ttsProfiles")
        if isinstance(incoming_tts_profiles, list):
            merged_tts_profiles = cls._normalize_tts_profiles_storage(incoming_tts_profiles)
        merged_default_tts_profile_id = cls._resolve_default_tts_profile_id(
            merged_tts_profiles,
            requested_default_id=source.get("defaultTtsProfileId") or stored.get("defaultTtsProfileId"),
        )

        merged_stt = cls._normalize_legacy_section(stored.get("stt") or stored.get("asr"), category="stt")
        incoming_stt = source.get("stt") if isinstance(source.get("stt"), dict) else None
        if incoming_stt is None and isinstance(source.get("asr"), dict):
            incoming_stt = source.get("asr")
        if isinstance(incoming_stt, dict):
            provider_id = normalize_provider_id(
                incoming_stt.get("providerId")
                or incoming_stt.get("provider_id")
                or merged_stt.get("providerId")
                or ""
            )
            if provider_id:
                cls._validate_provider(provider_id, category="stt")
                merged_stt["providerId"] = provider_id
            if isinstance(incoming_stt.get("settings"), dict):
                merged_stt["settings"] = cls._merge_dict(
                    merged_stt.get("settings") if isinstance(merged_stt.get("settings"), dict) else {},
                    incoming_stt.get("settings") or {},
                )
            if isinstance(incoming_stt.get("secrets"), dict):
                merged_stt["secrets"] = cls._merge_secret_values(
                    merged_stt.get("secrets") if isinstance(merged_stt.get("secrets"), dict) else {},
                    incoming_stt.get("secrets") or {},
                )

        barge_in = stored.get("bargeIn")
        if isinstance(source.get("bargeIn"), dict):
            barge_in = cls._merge_dict(
                barge_in if isinstance(barge_in, dict) else {},
                source.get("bargeIn") or {},
            )

        return {
            "tts": {
                "providerId": merged_tts.get("providerId"),
                "settings": deepcopy(merged_tts.get("settings") if isinstance(merged_tts.get("settings"), dict) else {}),
                "secrets": deepcopy(merged_tts.get("secrets") if isinstance(merged_tts.get("secrets"), dict) else {}),
            },
            "ttsProfiles": [
                {
                    "id": item.get("id"),
                    "label": item.get("label"),
                    "providerId": item.get("providerId"),
                    "settings": deepcopy(item.get("settings") if isinstance(item.get("settings"), dict) else {}),
                    "allowVoiceClone": bool(item.get("allowVoiceClone")),
                    "isDefault": str(item.get("id") or "").strip() == str(merged_default_tts_profile_id or "").strip(),
                }
                for item in merged_tts_profiles
            ],
            "defaultTtsProfileId": merged_default_tts_profile_id,
            "stt": {
                "providerId": merged_stt.get("providerId"),
                "settings": deepcopy(merged_stt.get("settings") if isinstance(merged_stt.get("settings"), dict) else {}),
                "secrets": deepcopy(merged_stt.get("secrets") if isinstance(merged_stt.get("secrets"), dict) else {}),
            },
            "bargeIn": SpeechBargeInConfig.model_validate(barge_in if isinstance(barge_in, dict) else {}).model_dump(
                by_alias=True
            ),
        }

    @classmethod
    def to_legacy_view(cls, raw: Any) -> dict[str, Any]:
        source = raw if isinstance(raw, dict) else {}
        tts = cls._normalize_legacy_section(source.get("tts"), category="tts")
        tts_profiles = cls._normalize_tts_profiles_storage(source.get("ttsProfiles"))
        default_tts_profile_id = cls._resolve_default_tts_profile_id(
            tts_profiles,
            requested_default_id=source.get("defaultTtsProfileId"),
        )
        stt = cls._normalize_legacy_section(source.get("stt") or source.get("asr"), category="stt")
        barge_in = SpeechBargeInConfig.model_validate(
            source.get("bargeIn") if isinstance(source.get("bargeIn"), dict) else {}
        )
        return {
            "tts": cls._build_legacy_section_view(tts),
            "ttsProfiles": [
                {
                    "id": item.get("id"),
                    "label": item.get("label"),
                    "providerId": item.get("providerId"),
                    "settings": deepcopy(item.get("settings") if isinstance(item.get("settings"), dict) else {}),
                    "allowVoiceClone": bool(item.get("allowVoiceClone")),
                    "isDefault": str(item.get("id") or "").strip() == str(default_tts_profile_id or "").strip(),
                }
                for item in tts_profiles
            ],
            "defaultTtsProfileId": default_tts_profile_id,
            "stt": cls._build_legacy_section_view(stt),
            "bargeIn": barge_in.model_dump(by_alias=True),
        }

    @classmethod
    def resolve_default_tts_profile_storage(cls, raw: Any) -> dict[str, Any] | None:
        source = raw if isinstance(raw, dict) else {}
        profiles = cls._normalize_tts_profiles_storage(source.get("ttsProfiles"))
        default_tts_profile_id = cls._resolve_default_tts_profile_id(
            profiles,
            requested_default_id=source.get("defaultTtsProfileId"),
        )
        for profile in profiles:
            if str(profile.get("id") or "").strip() == str(default_tts_profile_id or "").strip():
                return deepcopy(profile)
        return None

    def to_view(self, cfg: SpeechTenantConfig) -> SpeechTenantConfigView:
        config = cfg.config or {}
        secrets = cfg.secrets or {}

        def pick_selection(section_key: str) -> SpeechProviderSelection | None:
            section = config.get(section_key) or {}
            provider_id = normalize_provider_id(section.get("providerId"))
            if not provider_id:
                return None
            settings = self._pick_settings(section, provider_id=provider_id)
            return SpeechProviderSelection(providerId=provider_id, settings=settings)

        barge_in_raw = config.get("bargeIn")
        barge_in = SpeechBargeInConfig.model_validate(barge_in_raw) if isinstance(barge_in_raw, dict) else None
        enabled, status = self._resolve_availability_state(status=cfg.status, is_active=cfg.is_active)
        tts_profiles = self._normalize_tts_profiles_storage(config.get("ttsProfiles"))
        default_tts_profile_id = self._resolve_default_tts_profile_id(
            tts_profiles,
            requested_default_id=config.get("defaultTtsProfileId"),
        )

        if not tts_profiles:
            default_tts = pick_selection("tts")
            if default_tts is not None:
                profile_id = default_tts_profile_id or "default-tts"
                tts_profiles = [
                    {
                        "id": profile_id,
                        "label": "默认模型",
                        "providerId": default_tts.provider_id,
                        "settings": deepcopy(default_tts.settings),
                        "allowVoiceClone": False,
                        "isDefault": True,
                    }
                ]
                default_tts_profile_id = profile_id

        tts_profiles_view: list[SpeechProviderProfileView] = []
        tts_profiles_secrets = secrets.get("ttsProfiles") if isinstance(secrets.get("ttsProfiles"), dict) else {}
        tts_provider_secrets = self._normalize_tts_provider_secret_map(secrets.get("ttsProviders"))
        for profile in tts_profiles:
            profile_id = str(profile.get("id") or "").strip()
            provider_id = normalize_provider_id(profile.get("providerId"))
            if not profile_id or not provider_id:
                continue
            secret_keys = get_provider_secret_keys(provider_id)
            raw_profile_secrets = tts_profiles_secrets.get(profile_id) if isinstance(tts_profiles_secrets, dict) else {}
            profile_secrets = raw_profile_secrets if isinstance(raw_profile_secrets, dict) else {}
            if not any(str(value or "").strip() for value in profile_secrets.values()):
                profile_secrets = tts_provider_secrets.get(provider_id) or {}
            if not profile_secrets and profile_id == str(default_tts_profile_id or "").strip():
                raw_default_secrets = secrets.get("tts") if isinstance(secrets.get("tts"), dict) else {}
                profile_secrets = raw_default_secrets if isinstance(raw_default_secrets, dict) else {}
            secrets_set = self._build_section_secrets_set(provider_id, profile_secrets)
            tts_profiles_view.append(
                SpeechProviderProfileView(
                    id=profile_id,
                    label=str(profile.get("label") or profile_id).strip() or profile_id,
                    providerId=provider_id,
                    settings=deepcopy(profile.get("settings") if isinstance(profile.get("settings"), dict) else {}),
                    isDefault=profile_id == str(default_tts_profile_id or "").strip(),
                    allowVoiceClone=bool(profile.get("allowVoiceClone")),
                    secretsSet=secrets_set,
                )
            )

        return SpeechTenantConfigView(
            enabled=enabled,
            status=status,
            tts=pick_selection("tts"),
            ttsProfiles=tts_profiles_view,
            defaultTtsProfileId=default_tts_profile_id,
            stt=pick_selection("stt"),
            bargeIn=barge_in,
            secretsSet=self._build_secrets_set(config=config, secrets=secrets),
        )

    async def get_view(self, *, tenant_id: int) -> SpeechTenantConfigView:
        cfg = await self.get_or_create(tenant_id=tenant_id)
        return self.to_view(cfg)

    async def upsert(self, *, tenant_id: int, data: SpeechTenantConfigUpsertRequest) -> SpeechTenantConfig:
        cfg = await self.get_or_create(tenant_id=tenant_id)
        config = dict(cfg.config or {})
        secrets = dict(cfg.secrets or {})
        if not isinstance(secrets.get("ttsProfiles"), dict):
            secrets["ttsProfiles"] = {}
        enabled, status = self._resolve_availability_state(status=cfg.status, is_active=cfg.is_active)

        def upsert_section(section_key: str, payload: Any, category: str) -> None:
            if payload is None:
                return
            provider_id = normalize_provider_id(payload.provider_id)
            if not provider_id:
                config[section_key] = {"providerId": None, "settings": {}}
                secrets[section_key] = {}
                return
            self._validate_provider(provider_id, category=category)

            section_cfg = dict(config.get(section_key) or {})
            prev_provider_id = normalize_provider_id(section_cfg.get("providerId"))
            current_settings = self._pick_settings(section_cfg, provider_id=provider_id)
            merged_settings = self._merge_dict(current_settings, payload.settings or {})
            config[section_key] = {"providerId": provider_id, "settings": merged_settings}

            # secrets 仅存当前 provider，避免跨 provider 误用；切换 provider 时默认清空
            section_secrets_raw = secrets.get(section_key) if isinstance(secrets, dict) else None
            base_secrets: dict[str, Any] = {}
            if prev_provider_id == provider_id:
                base_secrets = self._pick_secrets(section_secrets_raw, provider_id=provider_id, selected_provider_id=provider_id)
            if prev_provider_id != provider_id:
                base_secrets = {}

            if payload.secrets is not None:
                provider_secrets = dict(base_secrets)
                for k, v in (payload.secrets or {}).items():
                    # 默认：空值不覆盖（避免前端“占位符”误清空）
                    if v is None or (isinstance(v, str) and v.strip() == ""):
                        continue
                    provider_secrets[k] = v
                secrets[section_key] = provider_secrets
            else:
                # provider 切换且未提交 secrets：清空，避免沿用旧密钥
                secrets[section_key] = {} if prev_provider_id != provider_id else dict(base_secrets)

        upsert_section("tts", data.tts, "tts")

        if data.tts_profiles is not None:
            existing_profiles = self._normalize_tts_profiles_storage(config.get("ttsProfiles"))
            existing_profile_map = {str(item.get("id") or "").strip(): item for item in existing_profiles}
            existing_profile_secrets = secrets.get("ttsProfiles") if isinstance(secrets.get("ttsProfiles"), dict) else {}
            provider_secret_fallbacks: dict[str, dict[str, Any]] = self._normalize_tts_provider_secret_map(
                secrets.get("ttsProviders")
            )
            for existing_profile in existing_profiles:
                existing_provider_id = normalize_provider_id(existing_profile.get("providerId"))
                existing_profile_id = str(existing_profile.get("id") or "").strip()
                if not existing_provider_id or not existing_profile_id:
                    continue
                raw_secrets = existing_profile_secrets.get(existing_profile_id) if isinstance(existing_profile_secrets, dict) else {}
                if isinstance(raw_secrets, dict) and any(str(value or "").strip() for value in raw_secrets.values()):
                    provider_secret_fallbacks.setdefault(existing_provider_id, dict(raw_secrets))
            current_tts = self._normalize_legacy_section(config.get("tts"), category="tts")
            current_tts_provider_id = normalize_provider_id(current_tts.get("providerId"))
            current_tts_secrets = secrets.get("tts") if isinstance(secrets.get("tts"), dict) else {}
            if current_tts_provider_id and isinstance(current_tts_secrets, dict) and any(
                str(value or "").strip() for value in current_tts_secrets.values()
            ):
                provider_secret_fallbacks.setdefault(current_tts_provider_id, dict(current_tts_secrets))

            next_profiles: list[dict[str, Any]] = []
            next_profile_secrets: dict[str, dict[str, Any]] = {}
            used_profile_ids: set[str] = set()
            explicit_default_id: str | None = None

            for index, payload in enumerate(data.tts_profiles):
                provider_id = normalize_provider_id(payload.provider_id)
                if not provider_id:
                    continue
                self._validate_provider(provider_id, category="tts")

                base_profile_id = self._normalize_profile_id(
                    payload.id or payload.label or provider_id,
                    fallback=f"tts-profile-{index + 1}",
                )
                profile_id = base_profile_id
                suffix = 2
                while profile_id in used_profile_ids:
                    profile_id = f"{base_profile_id}-{suffix}"
                    suffix += 1
                used_profile_ids.add(profile_id)

                existing_profile = existing_profile_map.get(str(payload.id or "").strip()) or existing_profile_map.get(profile_id) or {}
                current_settings = (
                    existing_profile.get("settings") if isinstance(existing_profile.get("settings"), dict) else {}
                )
                merged_settings = self._merge_dict(current_settings, payload.settings or {})

                raw_existing_profile_secrets = {}
                if isinstance(existing_profile_secrets, dict):
                    raw_existing_profile_secrets = existing_profile_secrets.get(str(existing_profile.get("id") or profile_id)) or {}
                # Keep profile secrets unless the request explicitly changes them.
                # The UI returns masked config without secret values; clearing on provider drift would
                # silently break TTS when users switch tabs or restore a profile shape.
                base_profile_secrets = (
                    dict(raw_existing_profile_secrets)
                    if isinstance(raw_existing_profile_secrets, dict)
                    else {}
                )
                if not any(str(value or "").strip() for value in base_profile_secrets.values()):
                    base_profile_secrets = dict(provider_secret_fallbacks.get(provider_id) or {})
                if payload.secrets is not None:
                    profile_secrets = self._merge_secret_values(base_profile_secrets, payload.secrets or {})
                else:
                    profile_secrets = base_profile_secrets

                next_profiles.append(
                    {
                        "id": profile_id,
                        "label": str(payload.label or existing_profile.get("label") or f"模型 {index + 1}").strip()
                        or f"模型 {index + 1}",
                        "providerId": provider_id,
                        "settings": merged_settings,
                        "allowVoiceClone": (
                            bool(payload.allow_voice_clone)
                            if payload.allow_voice_clone is not None
                            else bool(existing_profile.get("allowVoiceClone"))
                        ),
                        "isDefault": bool(payload.is_default),
                    }
                )
                next_profile_secrets[profile_id] = profile_secrets

                if payload.is_default:
                    explicit_default_id = profile_id

            requested_default_id = explicit_default_id or data.default_tts_profile_id or config.get("defaultTtsProfileId")
            resolved_default_id = self._resolve_default_tts_profile_id(
                next_profiles,
                requested_default_id=requested_default_id,
            )
            for item in next_profiles:
                item["isDefault"] = str(item.get("id") or "").strip() == str(resolved_default_id or "").strip()

            config["ttsProfiles"] = next_profiles
            config["defaultTtsProfileId"] = resolved_default_id
            used_provider_ids = {str(item.get("providerId") or "").strip() for item in next_profiles if item.get("providerId")}
            secrets["ttsProviders"] = {
                provider_id: self._merge_secret_values({}, secret_values)
                for provider_id, secret_values in provider_secret_fallbacks.items()
                if provider_id in used_provider_ids
            }
            secrets["ttsProfiles"] = {
                profile_id: self._merge_secret_values({}, secret_values)
                for profile_id, secret_values in next_profile_secrets.items()
            }
            self._sync_default_tts_from_profiles(config=config, secrets=secrets)
        else:
            if data.default_tts_profile_id is not None:
                config["defaultTtsProfileId"] = self._resolve_default_tts_profile_id(
                    self._normalize_tts_profiles_storage(config.get("ttsProfiles")),
                    requested_default_id=data.default_tts_profile_id,
                )
                self._sync_default_tts_from_profiles(config=config, secrets=secrets)

            if data.tts is not None:
                current_profiles = self._normalize_tts_profiles_storage(config.get("ttsProfiles"))
                default_profile_id = self._resolve_default_tts_profile_id(
                    current_profiles,
                    requested_default_id=config.get("defaultTtsProfileId"),
                )
                if current_profiles and default_profile_id:
                    current_tts = self._normalize_legacy_section(config.get("tts"), category="tts")
                    updated_profiles: list[dict[str, Any]] = []
                    for profile in current_profiles:
                        if str(profile.get("id") or "").strip() == str(default_profile_id):
                            updated_profiles.append(
                                {
                                    **profile,
                                    "providerId": current_tts.get("providerId"),
                                    "settings": deepcopy(
                                        current_tts.get("settings")
                                        if isinstance(current_tts.get("settings"), dict)
                                        else {}
                                    ),
                                }
                            )
                        else:
                            updated_profiles.append(profile)
                    config["ttsProfiles"] = updated_profiles
                    profile_secrets_map = secrets.get("ttsProfiles") if isinstance(secrets.get("ttsProfiles"), dict) else {}
                    profile_secrets_map[str(default_profile_id)] = deepcopy(
                        secrets.get("tts") if isinstance(secrets.get("tts"), dict) else {}
                    )
                    secrets["ttsProfiles"] = profile_secrets_map
                    self._sync_default_tts_from_profiles(config=config, secrets=secrets)

        upsert_section("stt", data.stt, "stt")

        if data.barge_in is not None:
            config["bargeIn"] = data.barge_in.model_dump(by_alias=True)

        if data.enabled is not None:
            enabled = bool(data.enabled)
        status_source = data.status if data.status is not None else status
        status = self._normalize_status(status_source, enabled=enabled)
        enabled = self._resolve_enabled_flag(status=status, is_active=enabled)

        await self.update(
            cfg,
            {
                "config": config,
                "secrets": secrets,
                "status": status,
                "is_active": enabled,
            },
            exclude_unset=False,
        )
        return cfg

    async def get_by_tenant_id(self, *, tenant_id: int) -> SpeechTenantConfig:
        cfg = await self.get_one(where=[SpeechTenantConfig.tenant_id == tenant_id])
        if not cfg:
            raise NotFoundError(message="语音配置不存在")
        return cfg
