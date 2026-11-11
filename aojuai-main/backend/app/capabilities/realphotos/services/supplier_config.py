"""Platform contract rows. One duty, one configuration; secrets live outside the table."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.models.supplier_contract import RealphotosProviderContract
from app.capabilities.realphotos.services.supplier_clients import (
    CONFIG_VERSION,
    DASHSCOPE_URL,
    DEEPSEEK_URL,
    GENERATION_BASE,
)
from app.capabilities.realphotos.services.supplier_material import (
    import_staging_enabled,
    supplier_live_enabled,
)
from app.capabilities.realphotos.services.supplier_secrets import (
    has_duty_secret,
    mask_secret,
    read_duty_secret,
    write_duty_secret,
)
from app.core.config import settings
from app.core.exceptions import BusinessError, ForbiddenError

_LOG = logging.getLogger("realphotos.supplier_config")
_ADMIN_DUTIES = frozenset({"pre_review", "generation", "prompt_opt", "final_detection"})
_URL_RE = re.compile(r"^https?://", re.I)

# ensure() may refresh only these capability keys on non-adminManaged generation rows.
_GENERATION_HONESTY_KEYS = frozenset(
    {"sizeControl", "seed", "width", "height", "quantity", "textToImage", "imageToImage"}
)

_SPECS: tuple[dict[str, Any], ...] = (
    {
        "duty": "generation",
        "provider": "aoju",
        "model_id": "gpt-image-2",
        "region": "relay-unspecified",
        "credential_ref": "生产物料#ChatGPT IMAGE 2 / duty-secrets",
        "base_url": GENERATION_BASE,
        "capabilities": {
            "textToImage": True,
            "imageToImage": "reference-bytes",
            "width": "request-256-2048",
            "height": "request-256-2048",
            "quantity": "1-10",
            "seed": "gap-not-sent",
            "sizeControl": "unsupported_or_not_honored",
            "result": "pending-response",
            "pollingEnabled": False,
        },
        "gap_note": (
            "种子参数供应商合同未提供，不发送、不伪造（AC-009）。"
            "尺寸：请求体原样发送 size=WxH，适配器不静默改写；"
            "MODULE-B-CONTRACT-2026-11-10：物料无尺寸书面合同；"
            "探测 1024x768→1448x1086、1024x1024→1254x1254（无批准映射表）→ "
            "sizeControl 不得标 enforced；客户路径如实展示请求与实际尺寸。"
            "MODEL-API-CONFIG-2026-11-11：管理员可改渠道；第一版不轮询。"
        ),
        "secret_duty": "generation",
    },
    {
        "duty": "prompt_opt",
        "provider": "deepseek",
        "model_id": "deepseek-chat",
        "region": "api.deepseek.com",
        "credential_ref": "生产物料#Deepseek API / duty-secrets",
        "base_url": DEEPSEEK_URL,
        "capabilities": {
            "customerInitiated": True,
            "singleRequest": True,
            "retry": False,
            "truncate": False,
            "pollingEnabled": False,
        },
        "gap_note": "",
        "secret_duty": "prompt_opt",
    },
    {
        "duty": "pre_review",
        "provider": "dashscope",
        "model_id": "qwen3-vl-plus",
        "region": "cn-dashscope-compatible",
        "credential_ref": "生产物料#阿里百炼大模型 / duty-secrets",
        "base_url": DASHSCOPE_URL,
        "capabilities": {
            "imageInput": True,
            "verdicts": ["allow", "reject", "uncertain"],
            "hardCheck": "outside-model",
            "pollingEnabled": False,
        },
        "gap_note": "",
        "secret_duty": "pre_review",
    },
    {
        "duty": "import",
        "provider": "staging-image-host",
        "model_id": "staging-image-host",
        "region": "47.85.47.252",
        "credential_ref": "生产物料清单§4 临时图床（仅联调）",
        "base_url": "http://47.85.47.252",
        "capabilities": {
            "formalSupplier": False,
            "stagingAllowed": True,
            "pathPrefix": "/images/",
            "methods": ["GET"],
            "readOnlyInModelApi": True,
        },
        "gap_note": (
            "正式供应商 PENDING；管理员 2026-11-10 授权临时图床联调外呼，"
            "不得宣称 ND-012 正式闭合。MODEL-API 主表单不写此职责。"
        ),
        "secret_duty": "",
    },
    {
        "duty": "final_detection",
        "provider": "google-gemini",
        "model_id": "gemini-3.1-pro-preview",
        "region": "generativelanguage",
        "credential_ref": "生产物料#Gemini / duty-secrets / GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "capabilities": {
            "role": "final_physical_detection",
            "dimensions": ["noise", "depthOfField", "lighting", "colorRealism", "overallRealism"],
            "passRule": "total_score>=75 and passed=true",
            "pollingEnabled": False,
        },
        "gap_note": "启用识别名以管理员配置为准；通过线 PASS_SCORE 不因换 model id 改变。",
        "secret_duty": "final_detection",
    },
)

_PURPOSE_TO_DUTY = {
    "图片预审": "pre_review",
    "生图渠道": "generation",
    "提示词优化": "prompt_opt",
    "最终检测": "final_detection",
}
_DUTY_TO_PURPOSE = {v: k for k, v in _PURPOSE_TO_DUTY.items()}


def purpose_to_duty(purpose: str) -> str:
    label = str(purpose or "").strip()
    if label in _PURPOSE_TO_DUTY:
        return _PURPOSE_TO_DUTY[label]
    if label in _ADMIN_DUTIES:
        return label
    raise BusinessError(message="用途无效", code="INPUT_INVALID")


def _is_admin_managed(row: RealphotosProviderContract) -> bool:
    caps = row.capabilities if isinstance(row.capabilities, dict) else {}
    return bool(caps.get("adminManaged"))


def _loaded_updated_at(row: RealphotosProviderContract) -> str | None:
    """Avoid async lazy-refresh of TimestampMixin fields after flush."""
    from sqlalchemy import inspect as sa_inspect

    try:
        state = sa_inspect(row)
        if "updated_at" in state.unloaded:
            return None
        value = row.updated_at
    except Exception:
        return None
    if value is None:
        return None
    try:
        return value.isoformat()
    except Exception:
        return None


def _public(row: RealphotosProviderContract) -> dict[str, Any]:
    caps = dict(row.capabilities or {})
    key_prefix = str(caps.get("keyPrefix") or "")
    if not key_prefix and row.duty in _ADMIN_DUTIES:
        secret = read_duty_secret(row.duty)
        if secret:
            key_prefix = mask_secret(secret)
    return {
        "duty": row.duty,
        "purpose": _DUTY_TO_PURPOSE.get(row.duty, row.duty),
        "provider": row.provider,
        "modelId": row.model_id,
        "configVersion": row.config_version,
        "region": row.region,
        "credentialRef": row.credential_ref,
        "baseUrl": row.base_url,
        "capabilities": caps,
        "enabled": bool(row.enabled),
        "gapNote": row.gap_note,
        "keyPrefix": key_prefix,
        "masked": key_prefix,
        "hasSecret": bool(key_prefix) or has_duty_secret(row.duty),
        "updatedAt": _loaded_updated_at(row),
        "adminManaged": _is_admin_managed(row),
        "pollingEnabled": False,
        "scope": "平台",
    }


def _validate_base_url(url: str) -> str:
    text = str(url or "").strip()
    if not text or not _URL_RE.match(text):
        raise BusinessError(message="Base URL 须为 http(s) 地址", code="INPUT_INVALID")
    parsed = urlparse(text)
    if not parsed.netloc:
        raise BusinessError(message="Base URL 无效", code="INPUT_INVALID")
    if len(text) > 200:
        raise BusinessError(message="Base URL 过长", code="INPUT_INVALID")
    return text


def _next_config_version() -> str:
    return datetime.now(UTC).strftime("admin-%Y%m%dT%H%M%SZ")


def _seed_enabled(spec: dict[str, Any]) -> bool:
    duty = str(spec["duty"])
    if duty == "import":
        return bool(import_staging_enabled() and dict(spec["capabilities"]).get("stagingAllowed") is True)
    if duty == "final_detection":
        return has_duty_secret("final_detection") or bool(str(settings.GEMINI_API_KEY or "").strip())
    secret_duty = str(spec.get("secret_duty") or "")
    if not secret_duty:
        return False
    if not supplier_live_enabled() and duty in {"generation", "prompt_opt", "pre_review"}:
        # Still insert the row; leave enabled only when secret exists AND live flag on.
        return bool(has_duty_secret(secret_duty) and supplier_live_enabled())
    return has_duty_secret(secret_duty)


class RealphotosSupplierConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure(self) -> None:
        """Insert missing duty rows only. Never overwrite admin-managed fields."""
        live = supplier_live_enabled()
        for spec in _SPECS:
            duty = str(spec["duty"])
            # Skip seeding non-import/non-detection when live is off AND row already handled —
            # but still allow insert of disabled seed rows so admin UI can enable later.
            if duty not in {"final_detection", "import", "generation", "prompt_opt", "pre_review"}:
                continue
            if duty in {"prompt_opt", "pre_review"} and not live:
                # Insert disabled seed if missing so admin can configure without live flag.
                pass
            existing = await self._row(duty)
            if existing is not None:
                if _is_admin_managed(existing):
                    continue
                # Whitelist: generation honesty metadata only (evidence for MODEL-API-CONFIG).
                if duty == "generation":
                    caps = dict(existing.capabilities or {})
                    seed_caps = dict(spec["capabilities"])
                    changed = False
                    for key in _GENERATION_HONESTY_KEYS:
                        if key in seed_caps and caps.get(key) != seed_caps[key]:
                            caps[key] = seed_caps[key]
                            changed = True
                    if changed:
                        existing.capabilities = caps
                    if existing.gap_note != spec["gap_note"]:
                        existing.gap_note = str(spec["gap_note"])
                elif duty == "import":
                    # Staging host is ops-controlled; keep enabled aligned with flag when not adminManaged.
                    staging = import_staging_enabled()
                    caps = dict(spec["capabilities"])
                    existing.enabled = bool(staging and caps.get("stagingAllowed") is True)
                    existing.base_url = str(spec["base_url"])
                    existing.provider = str(spec["provider"])
                    existing.model_id = str(spec["model_id"])
                    existing.capabilities = caps
                    existing.gap_note = str(spec["gap_note"])
                continue

            model_id = str(spec["model_id"])
            if duty == "final_detection":
                model_id = str(settings.GEMINI_MODEL or model_id).strip() or model_id
            enabled = _seed_enabled(spec)
            self.db.add(
                RealphotosProviderContract(
                    tenant_id=0,
                    duty=duty,
                    provider=str(spec["provider"]),
                    model_id=model_id,
                    config_version=CONFIG_VERSION,
                    region=str(spec["region"]),
                    credential_ref=str(spec["credential_ref"]),
                    base_url=str(spec["base_url"]),
                    capabilities=dict(spec["capabilities"]),
                    enabled=enabled,
                    gap_note=str(spec["gap_note"]),
                )
            )
        await self.db.flush()

    async def enabled(self, duty: str) -> RealphotosProviderContract | None:
        await self.ensure()
        row = await self._row(duty)
        if row is None or not row.enabled:
            return None
        return row

    async def list_masked(self, *, actor_role_codes: set[str]) -> dict[str, Any]:
        self._admin(actor_role_codes)
        await self.ensure()
        rows = (
            await self.db.execute(
                select(RealphotosProviderContract)
                .where(RealphotosProviderContract.deleted_at.is_(None))
                .order_by(RealphotosProviderContract.id.asc())
            )
        ).scalars().all()
        return {
            "items": [_public(row) for row in rows],
            "pollingEnabled": False,
            "passScoreHint": "total_score≥75 且 passed=true（不因换 model id 改变）",
        }

    async def save(
        self,
        *,
        actor_role_codes: set[str],
        duty: str,
        model_id: str,
        api_key: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
        enabled: bool | None = None,
        actor_user_id: int | None = None,
    ) -> dict[str, Any]:
        self._admin(actor_role_codes)
        label = purpose_to_duty(duty)
        if label == "import":
            raise BusinessError(message="临时图床职责只读，请走联调开关", code="INPUT_INVALID")
        if label not in _ADMIN_DUTIES:
            raise BusinessError(message="职责不存在", code="NOT_FOUND")

        await self.ensure()
        row = await self._row(label)
        before = _public(row) if row is not None else None

        model_label = str(model_id or "").strip()
        want_enabled = bool(enabled) if enabled is not None else (bool(row.enabled) if row else True)
        if want_enabled and not model_label and not (row and row.model_id):
            raise BusinessError(message="启用前须填写 model ID", code="INPUT_INVALID")

        if row is None:
            seed = next(s for s in _SPECS if s["duty"] == label)
            if not model_label:
                raise BusinessError(message="model ID 必填", code="INPUT_INVALID")
            base = _validate_base_url(base_url or str(seed["base_url"]))
            prov = str(provider or seed["provider"]).strip() or str(seed["provider"])
            caps = dict(seed["capabilities"])
            caps["adminManaged"] = True
            caps["pollingEnabled"] = False
            row = RealphotosProviderContract(
                tenant_id=0,
                duty=label,
                provider=prov,
                model_id=model_label,
                config_version=_next_config_version(),
                region=str(seed["region"]),
                credential_ref=str(seed["credential_ref"]),
                base_url=base,
                capabilities=caps,
                enabled=False,
                gap_note=str(seed["gap_note"]),
            )
            self.db.add(row)
            await self.db.flush()

        if model_label:
            row.model_id = model_label
        if provider is not None and str(provider).strip():
            row.provider = str(provider).strip()[:32]
        if base_url is not None and str(base_url).strip():
            row.base_url = _validate_base_url(str(base_url))

        key_written = False
        if api_key and str(api_key).strip():
            prefix = write_duty_secret(label, str(api_key).strip())
            caps = dict(row.capabilities or {})
            caps["keyPrefix"] = prefix
            caps["adminManaged"] = True
            caps["pollingEnabled"] = False
            row.capabilities = caps
            key_written = True
        else:
            caps = dict(row.capabilities or {})
            caps["adminManaged"] = True
            caps["pollingEnabled"] = False
            if not caps.get("keyPrefix") and has_duty_secret(label):
                caps["keyPrefix"] = mask_secret(read_duty_secret(label))
            row.capabilities = caps

        if enabled is not None:
            if want_enabled:
                if not str(row.model_id or "").strip():
                    raise BusinessError(message="启用前须填写 model ID", code="INPUT_INVALID")
                if not has_duty_secret(label):
                    raise BusinessError(message="启用前须配置 API Key", code="INPUT_INVALID")
            row.enabled = want_enabled

        row.config_version = _next_config_version()
        await self.db.flush()
        await self.db.refresh(row)
        after = _public(row)
        # FR-030: do NOT write user_action_log. Ops audit via app log + updated_at.
        _LOG.info(
            "provider_contract_saved actor=%s duty=%s before=%s after=%s keyRotated=%s",
            actor_user_id,
            label,
            {
                "provider": (before or {}).get("provider"),
                "modelId": (before or {}).get("modelId"),
                "baseUrl": (before or {}).get("baseUrl"),
                "enabled": (before or {}).get("enabled"),
                "configVersion": (before or {}).get("configVersion"),
            },
            {
                "provider": after.get("provider"),
                "modelId": after.get("modelId"),
                "baseUrl": after.get("baseUrl"),
                "enabled": after.get("enabled"),
                "configVersion": after.get("configVersion"),
                "keyPrefix": after.get("keyPrefix"),
            },
            key_written,
        )
        return after

    async def set_enabled(
        self,
        *,
        actor_role_codes: set[str],
        duty: str,
        enabled: bool,
        actor_user_id: int | None = None,
    ) -> dict[str, Any]:
        row = await self._row(purpose_to_duty(duty))
        if row is None:
            raise BusinessError(message="职责不存在", code="NOT_FOUND")
        return await self.save(
            actor_role_codes=actor_role_codes,
            duty=row.duty,
            model_id=row.model_id,
            provider=row.provider,
            base_url=row.base_url,
            enabled=enabled,
            actor_user_id=actor_user_id,
        )

    async def soft_delete(
        self,
        *,
        actor_role_codes: set[str],
        duty: str,
        actor_user_id: int | None = None,
    ) -> dict[str, Any]:
        self._admin(actor_role_codes)
        label = purpose_to_duty(duty)
        if label == "import":
            raise BusinessError(message="临时图床职责不可删除", code="INPUT_INVALID")
        row = await self._row(label)
        if row is None:
            raise BusinessError(message="职责不存在", code="NOT_FOUND")
        before = _public(row)
        row.enabled = False
        row.deleted_at = datetime.now(UTC)
        await self.db.flush()
        _LOG.info(
            "provider_contract_deleted actor=%s duty=%s before=%s",
            actor_user_id,
            label,
            {
                "provider": before.get("provider"),
                "modelId": before.get("modelId"),
                "baseUrl": before.get("baseUrl"),
                "enabled": before.get("enabled"),
            },
        )
        return {"duty": label, "deleted": True}

    async def note_response(self, *, duty: str, model_id: str, result_kind: str) -> None:
        row = await self._row(duty)
        if row is None:
            return
        # Do not overwrite admin-chosen model id with upstream echo.
        if model_id and not _is_admin_managed(row):
            row.model_id = model_id
        capabilities = dict(row.capabilities or {})
        capabilities["result"] = result_kind
        row.capabilities = capabilities
        await self.db.flush()

    async def _row(self, duty: str) -> RealphotosProviderContract | None:
        return (
            await self.db.execute(
                select(RealphotosProviderContract).where(
                    RealphotosProviderContract.duty == duty,
                    RealphotosProviderContract.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    def _admin(roles: set[str]) -> None:
        from app.capabilities.realphotos.permissions import ROLE_ADMIN

        if ROLE_ADMIN in roles or "admin" in roles:
            return
        raise ForbiddenError(message="只有平台管理员可以登记模型合同")
