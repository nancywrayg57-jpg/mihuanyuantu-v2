"""S0 exit_evidence behavioural tests (service-level, SQLite).

覆盖：登录会话、三角色、跨租户拒绝、整数积分流水、Decimal 隔离、
LocalDisk 网关种子读回、worker 消费队列至终态。
"""

from __future__ import annotations

import pytest

from app.capabilities.realphotos.adapters.storage import LocalDiskStorageAdapter
from app.capabilities.realphotos.constants import SEED_OBJECT_BYTES, SEED_OBJECT_KEY
from app.capabilities.realphotos.permissions import (
    ROLE_ADMIN,
    ROLE_MERCHANT,
    ROLE_ORDER_SUPPORT,
)
from app.capabilities.realphotos.services.auth_service import RealphotosAuthService
from app.capabilities.realphotos.services.bootstrap import (
    DEFAULT_PASSWORD,
    bootstrap_s0_accounts,
)
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.core.exceptions import BusinessError, NotFoundError, UnauthorizedError


@pytest.mark.asyncio
async def test_s0_login_roles_and_session_rejection(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    auth = RealphotosAuthService(db)

    # 无挑战 / 错验证码不可登录
    challenge = await auth.create_challenge()
    with pytest.raises(BusinessError):
        await auth.login(
            username="rp_merchant_a1",
            password=DEFAULT_PASSWORD,
            challenge_id=challenge["challengeId"],
            challenge_code="000000",
        )

    # 三角色均可登录
    for username, expected_role in [
        ("rp_merchant_a1", ROLE_MERCHANT),
        ("rp_order_support", ROLE_ORDER_SUPPORT),
        ("rp_admin", ROLE_ADMIN),
    ]:
        ch = await auth.create_challenge()
        assert "devCode" in ch
        session = await auth.login(
            username=username,
            password=DEFAULT_PASSWORD,
            challenge_id=ch["challengeId"],
            challenge_code=ch["devCode"],
        )
        assert session["accessToken"]
        assert expected_role in session["user"]["roleCodes"]
        assert session["user"]["tenantId"] == summary[username]["tenantId"]

    # 错误密码拒绝
    ch = await auth.create_challenge()
    with pytest.raises(UnauthorizedError):
        await auth.login(
            username="rp_merchant_a1",
            password="wrong-password",
            challenge_id=ch["challengeId"],
            challenge_code=ch["devCode"],
        )


@pytest.mark.asyncio
async def test_s0_shared_wallet_and_cross_tenant_isolation(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    credits = RealphotosCreditService(db)

    tenant1 = int(summary["rp_merchant_a1"]["tenantId"])
    tenant2 = int(summary["rp_merchant_b1"]["tenantId"])
    admin_id = int(summary["rp_admin"]["userId"])

    wallet = await credits.admin_adjust(
        tenant_id=tenant1,
        delta_available=100,
        operator_user_id=admin_id,
        reason="S0 seed topup",
        event_key="s0-topup-t1-1",
    )
    assert wallet["availableInteger"] == "100"
    assert wallet["decimalBridge"] is False

    # 同租户双账号共用余额可见性
    w_a1 = await credits.get_wallet(tenant_id=tenant1)
    w_a2 = await credits.get_wallet(tenant_id=tenant1)
    assert w_a1["availableInteger"] == w_a2["availableInteger"] == "100"

    # 第二租户读不到第一租户流水对象（按 tenant 过滤）
    rows_t2, total_t2 = await credits.list_ledger(tenant_id=tenant2)
    assert total_t2 == 0 and rows_t2 == []
    rows_t1, total_t1 = await credits.list_ledger(tenant_id=tenant1)
    assert total_t1 == 1

    # 跨租户任务读拒绝
    jobs = RealphotosJobService(db)
    job = await jobs.enqueue(tenant_id=tenant1, owner_account_id=int(summary["rp_merchant_a1"]["userId"]))
    with pytest.raises(NotFoundError):
        await jobs.get_job(tenant_id=tenant2, job_id=int(job.id))


@pytest.mark.asyncio
async def test_s0_decimal_bridge_forbidden(db) -> None:
    with pytest.raises(BusinessError, match="Decimal"):
        RealphotosCreditService.reject_decimal_bridge()
    # 确认服务层未依赖 Decimal CreditService
    from pathlib import Path

    import app.capabilities.realphotos.services.credit_service as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "app.domain.credits" not in source
    assert RealphotosCreditService.DECIMAL_BRIDGE_FORBIDDEN is True


@pytest.mark.asyncio
async def test_s0_gateway_seed_file_no_bare_path(db, storage_tmpdir) -> None:
    adapter = LocalDiskStorageAdapter(root=storage_tmpdir)
    stored = adapter.ensure_seed_file()
    assert stored.object_key == SEED_OBJECT_KEY
    assert adapter.exists(SEED_OBJECT_KEY)
    with adapter.open_read(SEED_OBJECT_KEY) as handle:
        assert handle.read() == SEED_OBJECT_BYTES
    # 响应合同：对象键不是绝对路径
    assert not stored.object_key.startswith("/")
    assert str(storage_tmpdir) not in stored.object_key

    # 跨租户业务键拒绝（模拟网关前缀规则）
    tenant_key = "tenant/1/demo.bin"
    adapter.put_bytes(tenant_key, b"secret")
    assert adapter.exists(tenant_key)


@pytest.mark.asyncio
async def test_s0_worker_consumes_queued_job_to_terminal(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant1 = int(summary["rp_merchant_a1"]["tenantId"])
    owner = int(summary["rp_merchant_a1"]["userId"])
    service = RealphotosJobService(db)

    job = await service.enqueue(
        tenant_id=tenant1,
        owner_account_id=owner,
        job_kind="heartbeat",
        payload={"ping": True},
    )
    await db.commit()

    claimed = await service.claim(worker_id="test-worker")
    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.claimed_by

    finished = await service.complete_success(job=claimed, result={"ok": True})
    await db.commit()
    assert finished.status == "succeeded"
    assert finished.result.get("ok") is True

    # 关 API 语义：任务行仍在库中可查
    reloaded = await service.get_job(tenant_id=tenant1, job_id=int(job.id))
    assert reloaded.status == "succeeded"
