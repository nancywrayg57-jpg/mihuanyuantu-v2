"""PRODUCT-GAP-FIX unit/contract coverage: captcha login, lock, batch20, outbox."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.capabilities.realphotos.constants import UPLOAD_BATCH_MAX
from app.capabilities.realphotos.models import RealphotosImageLock, RealphotosOutbox
from app.capabilities.realphotos.services.auth_service import RealphotosAuthService
from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
from app.capabilities.realphotos.services.notify_outbox import RealphotosNotifyOutboxService
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService, pixel_identity
from app.core.exceptions import BusinessError, UnauthorizedError


def _jpeg(color: tuple[int, int, int] = (12, 34, 56), size: tuple[int, int] = (1280, 960)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_g1_login_rejects_missing_or_wrong_captcha(db) -> None:
    await bootstrap_s0_accounts(db)
    auth = RealphotosAuthService(db)
    with pytest.raises((BusinessError, TypeError, UnauthorizedError)):
        await auth.login(
            username="rp_merchant_a1",
            password=DEFAULT_PASSWORD,
            challenge_id="",
            challenge_code="",
        )
    challenge = await auth.create_challenge()
    assert str(challenge.get("imageBase64") or "").startswith("data:image/png;base64,")
    with pytest.raises(BusinessError) as wrong:
        await auth.login(
            username="rp_merchant_a1",
            password=DEFAULT_PASSWORD,
            challenge_id=challenge["challengeId"],
            challenge_code="000000",
        )
    assert wrong.value.code == "INPUT_INVALID"
    ok = await auth.create_challenge()
    assert str(ok.get("imageBase64") or "").startswith("data:image/png;base64,")
    assert ok.get("devCode"), "unit tests expect allow_dev_captcha for plaintext code"
    session = await auth.login(
        username="rp_merchant_a1",
        password=DEFAULT_PASSWORD,
        challenge_id=ok["challengeId"],
        challenge_code=ok["devCode"],
    )
    assert session["accessToken"]
    assert session["absoluteSessionDays"] == 30


@pytest.mark.asyncio
async def test_g2_image_lock_blocks_submit(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant_id = int(summary["rp_merchant_a1"]["tenantId"])
    owner_id = int(summary["rp_merchant_a1"]["userId"])
    service = RealphotosS1Service(db)
    data = _jpeg((90, 10, 10))
    asset = await service.upload(tenant_id=tenant_id, owner_account_id=owner_id, data=data)
    identity = pixel_identity(data)
    db.add(
        RealphotosImageLock(
            tenant_id=tenant_id,
            owner_account_id=owner_id,
            image_identity=identity,
            reason="content_review",
        )
    )
    await db.flush()
    # 提交入口在冻结/入队前调用同一校验；单测直达以避免依赖启用预设种子
    with pytest.raises(BusinessError) as locked:
        await service._assert_asset_unlocked(
            tenant_id=tenant_id,
            owner_account_id=owner_id,
            asset=asset,
        )
    assert locked.value.code == "IMAGE_LOCKED"


@pytest.mark.asyncio
async def test_g3_upload_batch_hard_limit(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant_id = int(summary["rp_merchant_a1"]["tenantId"])
    owner_id = int(summary["rp_merchant_a1"]["userId"])
    service = RealphotosS1Service(db)
    ok_files = [_jpeg((i % 200, 40, 80)) for i in range(UPLOAD_BATCH_MAX)]
    created = await service.upload_batch(
        tenant_id=tenant_id, owner_account_id=owner_id, files=ok_files
    )
    assert len(created) == UPLOAD_BATCH_MAX
    with pytest.raises(BusinessError) as rejected:
        await service.upload_batch(
            tenant_id=tenant_id,
            owner_account_id=owner_id,
            files=ok_files + [_jpeg((1, 2, 3))],
        )
    assert rejected.value.code == "UPLOAD_BATCH_REJECTED"


@pytest.mark.asyncio
async def test_g4_outbox_retry_then_sent(db, monkeypatch) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant_id = int(summary["rp_merchant_a1"]["tenantId"])
    owner_id = int(summary["rp_merchant_a1"]["userId"])
    monkeypatch.setenv("REALPHOTOS_NOTIFY_FORCE_FAIL_UNTIL", "2")
    notify = RealphotosNotifyOutboxService(db)
    row = await notify.enqueue_inbox(
        tenant_id=tenant_id,
        recipient_user_id=owner_id,
        event_key="gap-notify-1",
        title="测试",
        body="body",
    )
    await db.flush()
    first = await notify.deliver_one()
    assert first is not None and first["status"] == "pending" and first["attemptCount"] == 1
    # 立即到期再试
    row.next_attempt_at = None
    await db.flush()
    second = await notify.deliver_one()
    assert second is not None and second["status"] == "pending" and second["attemptCount"] == 2
    row.next_attempt_at = None
    await db.flush()
    monkeypatch.delenv("REALPHOTOS_NOTIFY_FORCE_FAIL_UNTIL", raising=False)
    third = await notify.deliver_one()
    assert third is not None and third["status"] == "sent" and third["attemptCount"] == 3
    out = (
        await db.get(RealphotosOutbox, int(row.id))
    )
    assert out is not None and out.status == "sent"


@pytest.mark.asyncio
async def test_g2_assert_unlocked_helper(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant_id = int(summary["rp_merchant_a1"]["tenantId"])
    owner_id = int(summary["rp_merchant_a1"]["userId"])
    data = _jpeg((11, 22, 33))
    ops = RealphotosOpsService(db)
    await ops.assert_image_unlocked(tenant_id=tenant_id, owner_account_id=owner_id, data=data)
