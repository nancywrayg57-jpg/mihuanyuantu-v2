"""KEY-MODEL-SET T1: per-credential model meta + enabled contract sync."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.capabilities.realphotos.services import supplier_secrets as secrets
from app.capabilities.realphotos.services.supplier_clients import DEEPSEEK_URL
from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService


@pytest.mark.asyncio
async def test_update_credential_meta_syncs_when_enabled(db, monkeypatch: pytest.MonkeyPatch) -> None:
    key_a = "sk-keymodel-t1-ALPHA0001"
    key_b = "sk-keymodel-t1-BRAVO0002"
    with tempfile.TemporaryDirectory(prefix="key-model-set-t1-") as tmp:
        store = Path(tmp) / "realphotos-duty-secrets.json"
        monkeypatch.setattr(secrets, "secret_store_paths", lambda: [store])

        roles = {"rp_admin"}
        service = RealphotosSupplierConfigService(db)
        await service.ensure()
        await service.save(
            actor_role_codes=roles,
            duty="prompt_opt",
            model_id="deepseek-chat",
            provider="deepseek",
            base_url=DEEPSEEK_URL,
            api_key=key_a,
            enabled=True,
            actor_user_id=0,
        )
        listed = await service.list_masked(actor_role_codes=roles)
        item = next(row for row in listed["items"] if row.get("duty") == "prompt_opt")
        cred_id = str(item.get("activeCredentialId") or "")
        assert cred_id

        await service.update_credential_meta(
            actor_role_codes=roles,
            duty="prompt_opt",
            credential_id=cred_id,
            model_id="deepseek-reasoner",
            provider="deepseek",
            base_url=DEEPSEEK_URL,
            actor_user_id=0,
        )
        row = await service._row("prompt_opt")
        assert row is not None
        assert row.model_id == "deepseek-reasoner"

        creds = secrets.list_duty_credentials("prompt_opt")
        active = next(c for c in creds if c.get("id") == cred_id)
        assert active.get("modelId") == "deepseek-reasoner"

        await service.save(
            actor_role_codes=roles,
            duty="prompt_opt",
            model_id="deepseek-chat",
            provider="deepseek",
            base_url=DEEPSEEK_URL,
            api_key=key_b,
            enabled=True,
            actor_user_id=0,
        )
        creds2 = secrets.list_duty_credentials("prompt_opt")
        disabled = next(c for c in creds2 if c.get("modelId") == "deepseek-reasoner" and not c.get("enabled"))
        assert disabled.get("id") == cred_id

        await service.update_credential_meta(
            actor_role_codes=roles,
            duty="prompt_opt",
            credential_id=cred_id,
            model_id="deepseek-reasoner-v2",
            provider="deepseek",
            base_url=DEEPSEEK_URL,
            actor_user_id=0,
        )
        row2 = await service._row("prompt_opt")
        assert row2 is not None
        assert row2.model_id == "deepseek-chat"
        disabled2 = next(c for c in secrets.list_duty_credentials("prompt_opt") if c.get("id") == cred_id)
        assert disabled2.get("modelId") == "deepseek-reasoner-v2"

        await service.set_enabled(
            actor_role_codes=roles,
            duty="prompt_opt",
            enabled=True,
            credential_id=cred_id,
            actor_user_id=0,
        )
        row3 = await service._row("prompt_opt")
        assert row3 is not None
        assert row3.model_id == "deepseek-reasoner-v2"
        blob = json.dumps(await service.list_masked(actor_role_codes=roles), ensure_ascii=False)
        assert key_a not in blob and key_b not in blob

        await db.rollback()
