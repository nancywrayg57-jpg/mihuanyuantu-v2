"""UX audit fixes: preset dedupe, login activity, upload original filename."""

from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.capabilities.realphotos.permissions import ROLE_ADMIN
from app.capabilities.realphotos.services.auth_service import RealphotosAuthService
from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
from app.domain.users.models import User


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (18, 40, 62)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_login_updates_last_login_at(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    user_id = int(summary["rp_merchant_a1"]["userId"])
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    user.last_login_at = None
    await db.commit()

    service = RealphotosAuthService(db)
    challenge = await service.create_challenge(client_key="ux-audit-login")
    await service.login(
        username="rp_merchant_a1",
        password=DEFAULT_PASSWORD,
        challenge_id=str(challenge["challengeId"]),
        challenge_code=str(challenge["devCode"]),
    )
    await db.refresh(user)
    assert user.last_login_at is not None


@pytest.mark.asyncio
async def test_presets_are_deduped_by_brand_and_model_with_names(db) -> None:
    await bootstrap_s0_accounts(db)
    ops = RealphotosOpsService(db)
    roles = {ROLE_ADMIN, "admin"}
    for code, name in (("audit-cam-a", "AuditCam X1 主摄"), ("audit-cam-b", "AuditCam X1 长焦")):
        await ops.save_preset(
            actor_role_codes=roles,
            code=code,
            device_type="phone",
            brand="AuditCam",
            model_name="X1",
            gps_mode="none",
            enabled=True,
            iso="100",
            shutter="1/200",
            aperture="f/1.8",
            focal_length="24mm",
            legacy_parameters={"name": name},
        )
    await db.commit()

    items = await ops.list_enabled_presets()
    identities = [
        (str(item.get("brand") or "").strip().lower(), str(item.get("model") or "").strip().lower())
        for item in items
    ]
    assert len(identities) == len(set(identities))
    audit_rows = [item for item in items if str(item.get("brand")) == "AuditCam"]
    assert len(audit_rows) == 1
    assert audit_rows[0]["name"] in {"AuditCam X1 主摄", "AuditCam X1 长焦"}


@pytest.mark.asyncio
async def test_batch_upload_preserves_original_filename(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant_id = int(summary["rp_merchant_a1"]["tenantId"])
    user_id = int(summary["rp_merchant_a1"]["userId"])
    rows = await RealphotosS1Service(db).upload_batch(
        tenant_id=tenant_id,
        owner_account_id=user_id,
        files=[_jpeg()],
        meta_names=["IMG_0001.jpg"],
    )
    assert len(rows) == 1
    assert rows[0].meta_name == "IMG_0001.jpg"
    assert rows[0].origin_kind == "local_upload"
