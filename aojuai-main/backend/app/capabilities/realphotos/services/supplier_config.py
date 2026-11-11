"""Platform contract rows. One duty, one configuration, no secret column."""

from __future__ import annotations

from typing import Any

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
    read_material_secret,
    supplier_live_enabled,
)
from app.core.config import settings
from app.core.exceptions import BusinessError, ForbiddenError

_SPECS: tuple[dict[str, Any], ...] = (
    {
        "duty": "generation",
        "provider": "aoju",
        "model_id": "gpt-image-2",
        "region": "relay-unspecified",
        "credential_ref": "生产物料#ChatGPT IMAGE 2",
        "base_url": GENERATION_BASE,
        "capabilities": {
            "textToImage": True,
            "imageToImage": "reference-bytes",
            "width": "request-256-2048",
            "height": "request-256-2048",
            "quantity": "1-10",
            "seed": "gap-not-sent",
            "result": "pending-response",
        },
        "gap_note": "种子参数供应商合同未提供，不发送、不伪造。尺寸按请求原样发送，不在适配器里改写。",
        "secret_duty": "generation",
    },
    {
        "duty": "prompt_opt",
        "provider": "deepseek",
        "model_id": "deepseek-chat",
        "region": "api.deepseek.com",
        "credential_ref": "生产物料#Deepseek API",
        "base_url": DEEPSEEK_URL,
        "capabilities": {
            "customerInitiated": True,
            "singleRequest": True,
            "retry": False,
            "truncate": False,
        },
        "gap_note": "",
        "secret_duty": "prompt_opt",
    },
    {
        "duty": "pre_review",
        "provider": "dashscope",
        "model_id": "qwen3-vl-plus",
        "region": "cn-dashscope-compatible",
        "credential_ref": "生产物料#阿里百炼大模型",
        "base_url": DASHSCOPE_URL,
        "capabilities": {
            "imageInput": True,
            "verdicts": ["allow", "reject", "uncertain"],
            "hardCheck": "outside-model",
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
        },
        "gap_note": (
            "正式供应商 PENDING；管理员 2026-11-10 授权临时图床联调外呼，"
            "不得宣称 ND-012 正式闭合。"
        ),
        "secret_duty": "",
    },
    {
        "duty": "final_detection",
        "provider": "google-gemini",
        "model_id": "gemini-3.1-pro-preview",
        "region": "generativelanguage",
        "credential_ref": "生产物料#Gemini / .env GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "capabilities": {
            "role": "final_physical_detection",
            "dimensions": ["noise", "depthOfField", "lighting", "colorRealism", "overallRealism"],
            "passRule": "total_score>=75 and passed=true",
        },
        "gap_note": "启用识别名以本机可调用型号为准；不可用的 gemini-2.5-pro 不再作为客户默认。",
        "secret_duty": "final_detection",
    },
)


def _public(row: RealphotosProviderContract) -> dict[str, Any]:
    return {
        "duty": row.duty,
        "provider": row.provider,
        "modelId": row.model_id,
        "configVersion": row.config_version,
        "region": row.region,
        "credentialRef": row.credential_ref,
        "baseUrl": row.base_url,
        "capabilities": dict(row.capabilities or {}),
        "enabled": bool(row.enabled),
        "gapNote": row.gap_note,
    }


class RealphotosSupplierConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure(self) -> None:
        live = supplier_live_enabled()
        staging = import_staging_enabled()
        for spec in _SPECS:
            # import may enable under staging flag without supplier_live.
            # final_detection is config/settings based; other duties still require supplier live.
            if spec["duty"] not in {"final_detection", "import"} and not live:
                continue
            if spec["duty"] == "import" and not staging and not live:
                # Still upsert the honest contract row when staging off, but keep disabled.
                pass
            existing = await self._row(spec["duty"])
            model_id = str(spec["model_id"])
            if spec["duty"] == "final_detection":
                model_id = str(settings.GEMINI_MODEL or model_id).strip() or model_id
                secret_ok = bool(str(settings.GEMINI_API_KEY or "").strip())
                enabled = secret_ok
            elif spec["duty"] == "import":
                secret_ok = True
                caps = dict(spec["capabilities"])
                enabled = bool(staging and caps.get("stagingAllowed") is True)
            else:
                secret_ok = bool(spec["secret_duty"]) and bool(read_material_secret(str(spec["secret_duty"])))
                enabled = secret_ok
            if existing is not None:
                if spec["duty"] == "final_detection":
                    if existing.model_id in {"", "gemini-2.5-pro"} or existing.model_id != model_id:
                        existing.model_id = model_id
                    existing.enabled = enabled
                    existing.config_version = CONFIG_VERSION
                    existing.gap_note = spec["gap_note"]
                elif spec["duty"] == "import":
                    existing.provider = str(spec["provider"])
                    existing.model_id = model_id
                    existing.region = str(spec["region"])
                    existing.credential_ref = str(spec["credential_ref"])
                    existing.base_url = str(spec["base_url"])
                    existing.capabilities = dict(spec["capabilities"])
                    existing.enabled = enabled
                    existing.config_version = CONFIG_VERSION
                    existing.gap_note = spec["gap_note"]
                continue
            self.db.add(
                RealphotosProviderContract(
                    tenant_id=0,
                    duty=spec["duty"],
                    provider=spec["provider"],
                    model_id=model_id,
                    config_version=CONFIG_VERSION,
                    region=spec["region"],
                    credential_ref=spec["credential_ref"],
                    base_url=spec["base_url"],
                    capabilities=dict(spec["capabilities"]),
                    enabled=enabled,
                    gap_note=spec["gap_note"],
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
        return {"items": [_public(row) for row in rows]}

    async def save(
        self,
        *,
        actor_role_codes: set[str],
        duty: str,
        model_id: str,
        api_key: str | None,
    ) -> dict[str, Any]:
        self._admin(actor_role_codes)
        if api_key:
            raise BusinessError(message="登记页不接收上游 Key", code="INPUT_INVALID")
        await self.ensure()
        row = await self._row(duty)
        if row is None:
            raise BusinessError(message="职责不存在", code="NOT_FOUND")
        label = str(model_id or "").strip()
        if row.duty != "import" and not label:
            raise BusinessError(message="model ID 必填", code="INPUT_INVALID")
        if label:
            row.model_id = label
        await self.db.flush()
        return _public(row)

    async def note_response(self, *, duty: str, model_id: str, result_kind: str) -> None:
        row = await self._row(duty)
        if row is None:
            return
        if model_id:
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
