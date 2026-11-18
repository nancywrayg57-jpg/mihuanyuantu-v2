"""S6 ops rules on SQLite. PostgreSQL evidence is the smoke script."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.capabilities.realphotos.api.s1 import BatchBody
from app.capabilities.realphotos.models import (
    RealphotosAccountLog,
    RealphotosAuthGuard,
    RealphotosContentReview,
    RealphotosCreditReservation,
    RealphotosMerchantProfile,
    RealphotosSupportTicket,
)
from app.capabilities.realphotos.permissions import (
    ROLE_ADMIN,
    ROLE_MERCHANT,
    ROLE_ORDER_SUPPORT,
    ROLE_TECH_SUPPORT,
)
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
from app.core.exceptions import BusinessError, ForbiddenError
from app.domain.users.models import User


def _jpeg(color: tuple[int, int, int] = (18, 40, 62)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _funded(db):
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    admin = int(summary["rp_admin"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    tech = int(summary["rp_tech_support"]["userId"])
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="s6",
        idempotency_key="s6-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    return {
        "tenant": tenant,
        "user": user,
        "admin": admin,
        "support": support,
        "tech": tech,
        "ops": RealphotosOpsService(db),
        "loop": RealphotosS1Service(db),
        "credits": RealphotosCreditService(db),
        "growth": RealphotosGrowthService(db),
    }


async def _available(ctx) -> int:
    wallet = await ctx["credits"].get_wallet(tenant_id=ctx["tenant"])
    return int(wallet["availableInteger"])


@pytest.mark.asyncio
async def test_content_review_does_not_charge_and_uncertain_is_not_pass(db):
    ctx = await _funded(db)
    before = await _available(ctx)
    with pytest.raises(BusinessError) as missing:
        await ctx["ops"].review_content(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            data=_jpeg(),
            subject="processing",
            provider="unconfigured",
            verdict="reject",
        )
    assert missing.value.code == "SERVICE_NOT_CONFIGURED"
    tiny = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(tiny, format="JPEG")
    with pytest.raises(BusinessError):
        await ctx["ops"].review_content(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            data=tiny.getvalue(),
            subject="processing",
            provider="fixture",
            verdict="reject",
        )
    uncertain = await ctx["ops"].review_content(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        data=_jpeg((9, 9, 9)),
        subject="processing",
        provider="fixture",
        verdict="uncertain",
    )
    assert uncertain["passed"] is False
    assert uncertain["supplierConnected"] is False
    assert await _available(ctx) == before
    assert (
        await db.scalar(select(func.count()).select_from(RealphotosContentReview))
    ) == 1


@pytest.mark.asyncio
async def test_second_failure_locks_and_third_distinct_freezes(db):
    ctx = await _funded(db)
    other = int((await bootstrap_s0_accounts(db))["rp_merchant_a2"]["userId"])
    image_a = _jpeg((11, 22, 33))
    first = await ctx["ops"].review_content(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        data=image_a,
        subject="processing",
        provider="fixture",
        verdict="reject",
    )
    second = await ctx["ops"].review_content(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        data=image_a,
        subject="processing",
        provider="fixture",
        verdict="reject",
    )
    assert first["locked"] is False
    assert second["locked"] is True
    assert second["frozen"] is False
    passed = await ctx["ops"].review_content(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        data=_jpeg((4, 5, 6)),
        subject="processing",
        provider="fixture",
        verdict="pass",
    )
    assert passed["passed"] is True
    colors = [(30, 0, 0), (0, 30, 0), (0, 0, 30)]
    last = None
    for color in colors:
        last = await ctx["ops"].review_content(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            data=_jpeg(color),
            subject="processing",
            provider="fixture",
            verdict="reject",
        )
    assert last is not None
    assert last["frozen"] is True
    assert last["ticketId"] is not None
    tickets = await db.scalar(select(func.count()).select_from(RealphotosSupportTicket))
    assert int(tickets or 0) == 1
    ref = _jpeg((70, 70, 70))
    await ctx["ops"].review_content(
        tenant_id=ctx["tenant"],
        owner_account_id=other,
        data=ref,
        subject="reference",
        provider="fixture",
        verdict="reject",
    )
    again = await ctx["ops"].review_content(
        tenant_id=ctx["tenant"],
        owner_account_id=other,
        data=ref,
        subject="reference",
        provider="fixture",
        verdict="reject",
    )
    assert again["locked"] is True
    assert again["frozen"] is False
    profile = (
        await db.execute(
            select(RealphotosMerchantProfile).where(RealphotosMerchantProfile.user_id == other)
        )
    ).scalar_one()
    assert profile.pre_review_frozen is False
    # FR-002/031：冻结后上传/入库类获取即拒绝（不必等到 submit）
    with pytest.raises(BusinessError) as frozen:
        await ctx["loop"].upload(
            tenant_id=ctx["tenant"], owner_account_id=ctx["user"], data=_jpeg()
        )
    assert frozen.value.code == "ACCOUNT_FROZEN"
    with pytest.raises(BusinessError) as generated:
        await ctx["growth"].submit_generation(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            mode="text_to_image",
            positive_prompt="冻结后不能生图",
            width=256,
            height=256,
            quantity=1,
            idempotency_key="s6-frozen-gen",
            provider="fixture",
        )
    assert generated.value.code == "ACCOUNT_FROZEN"


@pytest.mark.asyncio
async def test_only_tech_or_admin_can_release_held_credit(db):
    ctx = await _funded(db)
    before = await _available(ctx)
    asset = await ctx["loop"].upload(tenant_id=ctx["tenant"], owner_account_id=ctx["user"], data=_jpeg())
    _batch, tasks = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        actor_role_codes={ROLE_ADMIN},
        asset_ids=[int(asset.id)],
        preset_code=S1_ENABLED_PRESETS[0]["code"],
        idempotency_key="s6-held",
        detection_mode="technical",
    )
    jobs = RealphotosJobService(db)
    claimed = await jobs.claim(worker_id="s6", job_kinds=("process_image",), payload_task_id=int(tasks[0].id))
    done = await ctx["loop"].execute_queued(claimed)
    assert done.credit_disposition == "held_until_tech_support"
    with pytest.raises(ForbiddenError):
        await ctx["ops"].release_held_credit(
            actor_role_codes={ROLE_ORDER_SUPPORT},
            operator_user_id=ctx["support"],
            tenant_id=ctx["tenant"],
            task_id=int(done.id),
            reason="客服不能放",
        )
    with pytest.raises(ForbiddenError):
        await ctx["ops"].release_held_credit(
            actor_role_codes={ROLE_MERCHANT},
            operator_user_id=ctx["user"],
            tenant_id=ctx["tenant"],
            task_id=int(done.id),
            reason="商家不能放",
        )
    guard = RealphotosAuthGuard(username_normalized="rp_merchant_a1", locked_until=datetime.now(UTC) + timedelta(minutes=30))
    db.add(guard)
    await db.flush()
    locked_until = guard.locked_until
    released = await ctx["ops"].release_held_credit(
        actor_role_codes={ROLE_TECH_SUPPORT},
        operator_user_id=ctx["tech"],
        tenant_id=ctx["tenant"],
        task_id=int(done.id),
        reason="技术客服审计释放",
    )
    assert released["disposition"] == "released_tech_audit"
    reservation = (
        await db.execute(
            select(RealphotosCreditReservation).where(RealphotosCreditReservation.task_id == int(done.id))
        )
    ).scalar_one()
    assert reservation.state == "released"
    assert await _available(ctx) == before
    assert guard.locked_until == locked_until
    await ctx["ops"].unfreeze_account(
        actor_role_codes={ROLE_ADMIN},
        operator_user_id=ctx["user"],
        tenant_id=ctx["tenant"],
        user_id=ctx["user"],
        reason="没有冻结也只清预审标记",
    )
    assert guard.locked_until == locked_until


async def _make_held_task(ctx, db, *, key: str):
    asset = await ctx["loop"].upload(
        tenant_id=ctx["tenant"], owner_account_id=ctx["user"], data=_jpeg()
    )
    _batch, tasks = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        actor_role_codes={ROLE_ADMIN},
        asset_ids=[int(asset.id)],
        preset_code=S1_ENABLED_PRESETS[0]["code"],
        idempotency_key=key,
        detection_mode="technical",
    )
    jobs = RealphotosJobService(db)
    claimed = await jobs.claim(
        worker_id=f"s6-{key}",
        job_kinds=("process_image",),
        payload_task_id=int(tasks[0].id),
    )
    done = await ctx["loop"].execute_queued(claimed)
    assert done.credit_disposition == "held_until_tech_support"
    return done


@pytest.mark.asyncio
async def test_held_credits_aggregate_and_release_by_amount_fifo(db):
    ctx = await _funded(db)
    before = await _available(ctx)
    first = await _make_held_task(ctx, db, key="s6-held-fifo-1")
    second = await _make_held_task(ctx, db, key="s6-held-fifo-2")
    listed = await ctx["ops"].list_held_credit_tasks(actor_role_codes={ROLE_TECH_SUPPORT})
    assert listed["pageSize"] == 10
    assert listed["total"] == 1
    assert len(listed["items"]) == 1
    agg = listed["items"][0]
    assert agg["tenantId"] == ctx["tenant"]
    assert isinstance(agg.get("tenantName"), str) and agg["tenantName"]
    assert int(agg["heldTotal"]) == 20
    assert int(agg["taskCount"]) == 2
    assert any(int(row["taskId"]) == int(first.id) for row in listed["tasks"])
    assert any(int(row["taskId"]) == int(second.id) for row in listed["tasks"])

    tickets = await ctx["ops"].list_tickets(actor_role_codes={ROLE_TECH_SUPPORT})
    # freeze ticket may or may not exist; names must be present when rows exist
    for row in tickets["items"]:
        assert row.get("tenantName")
        assert row.get("username")

    with pytest.raises(BusinessError) as over:
        await ctx["ops"].release_held_credits_by_amount(
            actor_role_codes={ROLE_TECH_SUPPORT},
            operator_user_id=ctx["tech"],
            tenant_id=ctx["tenant"],
            amount=21,
            reason="超额",
        )
    assert over.value.code == "INPUT_INVALID"
    with pytest.raises(BusinessError):
        await ctx["ops"].release_held_credits_by_amount(
            actor_role_codes={ROLE_TECH_SUPPORT},
            operator_user_id=ctx["tech"],
            tenant_id=ctx["tenant"],
            amount=5.5,  # type: ignore[arg-type]
            reason="小数",
        )
    with pytest.raises(BusinessError):
        await ctx["ops"].release_held_credits_by_amount(
            actor_role_codes={ROLE_TECH_SUPPORT},
            operator_user_id=ctx["tech"],
            tenant_id=ctx["tenant"],
            amount=5,
            reason="   ",
        )

    partial = await ctx["ops"].release_held_credits_by_amount(
        actor_role_codes={ROLE_TECH_SUPPORT},
        operator_user_id=ctx["tech"],
        tenant_id=ctx["tenant"],
        amount=15,
        reason="FIFO 释放十五",
    )
    assert partial["releasedAmount"] == 15
    assert partial["heldTotalAfter"] == 5
    assert [int(c["taskId"]) for c in partial["chunks"]] == [int(first.id), int(second.id)]
    assert int(partial["chunks"][0]["releasedAmount"]) == 10
    assert int(partial["chunks"][1]["releasedAmount"]) == 5
    first_res = (
        await db.execute(
            select(RealphotosCreditReservation).where(
                RealphotosCreditReservation.task_id == int(first.id)
            )
        )
    ).scalar_one()
    second_res = (
        await db.execute(
            select(RealphotosCreditReservation).where(
                RealphotosCreditReservation.task_id == int(second.id)
            )
        )
    ).scalar_one()
    assert first_res.state == "released"
    assert second_res.state == "held"
    assert int(second_res.amount) == 5
    assert await _available(ctx) == before - 5

    rest = await ctx["ops"].release_held_credits_by_amount(
        actor_role_codes={ROLE_TECH_SUPPORT},
        operator_user_id=ctx["tech"],
        tenant_id=ctx["tenant"],
        amount=5,
        reason="FIFO 释放剩余",
    )
    assert rest["heldTotalAfter"] == 0
    assert await _available(ctx) == before
    emptied = await ctx["ops"].list_held_credit_tasks(actor_role_codes={ROLE_TECH_SUPPORT})
    assert emptied["items"] == []
    assert emptied["tasks"] == []


@pytest.mark.asyncio
async def test_held_list_includes_tasks_without_reservation(db):
    """列表以 disposition 为主；缺预留行时仍展示，避免整页空白。"""
    ctx = await _funded(db)
    orphan = await _make_held_task(ctx, db, key="s6-held-orphan")
    orphan_res = (
        await db.execute(
            select(RealphotosCreditReservation).where(
                RealphotosCreditReservation.task_id == int(orphan.id)
            )
        )
    ).scalar_one()
    await db.delete(orphan_res)
    await db.flush()
    listed = await ctx["ops"].list_held_credit_tasks(actor_role_codes={ROLE_TECH_SUPPORT})
    assert listed["pageSize"] == 10
    assert any(int(row["taskId"]) == int(orphan.id) for row in listed["tasks"])
    agg = next(row for row in listed["items"] if int(row["tenantId"]) == int(ctx["tenant"]))
    assert int(agg["taskCount"]) >= 1
    assert int(agg["heldTotal"]) == 0


@pytest.mark.asyncio
async def test_user_admin_log_preset_and_metrics(db):
    ctx = await _funded(db)
    created = await ctx["ops"].create_user(
        actor_role_codes={ROLE_TECH_SUPPORT},
        operator_user_id=ctx["tech"],
        tenant_id=ctx["tenant"],
        username="rp_s6_extra",
        password="S6User@abc",
        role_code=ROLE_MERCHANT,
    )
    with pytest.raises(BusinessError):
        await ctx["ops"].adjust_credits(
            actor_role_codes={ROLE_ADMIN},
            operator_user_id=ctx["admin"],
            tenant_id=ctx["tenant"],
            user_id=int(created["id"]),
            delta=1.5,
            reason="小数",
            event_key="s6-decimal",
        )
    with pytest.raises(BusinessError):
        await ctx["ops"].adjust_credits(
            actor_role_codes={ROLE_ADMIN},
            operator_user_id=ctx["admin"],
            tenant_id=ctx["tenant"],
            user_id=int(created["id"]),
            delta=-100000,
            reason="负数",
            event_key="s6-negative",
        )
    await ctx["ops"].adjust_credits(
        actor_role_codes={ROLE_ADMIN},
        operator_user_id=ctx["admin"],
        tenant_id=ctx["tenant"],
        user_id=int(created["id"]),
        delta=1,
        reason="整数加一",
        event_key="s6-plus-one",
    )
    await ctx["ops"].set_roles(
        actor_role_codes={ROLE_ADMIN},
        operator_user_id=ctx["admin"],
        tenant_id=ctx["tenant"],
        user_id=int(created["id"]),
        role_codes=[ROLE_MERCHANT],
    )
    await ctx["ops"].set_status(
        actor_role_codes={ROLE_ADMIN},
        operator_user_id=ctx["admin"],
        user_id=int(created["id"]),
        enabled=False,
    )
    with pytest.raises(BusinessError):
        await ctx["ops"].reset_password(
            actor_role_codes={ROLE_TECH_SUPPORT},
            operator_user_id=ctx["tech"],
            user_id=int(created["id"]),
            password="S6Reset@abc",
            confirm="other",
        )
    await ctx["ops"].reset_password(
        actor_role_codes={ROLE_TECH_SUPPORT},
        operator_user_id=ctx["tech"],
        user_id=int(created["id"]),
        password="S6Reset@abc",
        confirm="S6Reset@abc",
    )
    with pytest.raises(BusinessError):
        await ctx["ops"].delete_user(
            actor_role_codes={ROLE_ADMIN},
            operator_user_id=ctx["admin"],
            user_id=int(created["id"]),
            confirm_username="wrong",
        )
    await ctx["ops"].delete_user(
        actor_role_codes={ROLE_ADMIN},
        operator_user_id=ctx["admin"],
        user_id=int(created["id"]),
        confirm_username="rp_s6_extra",
    )
    with pytest.raises(ForbiddenError):
        await ctx["ops"].create_user(
            actor_role_codes={ROLE_MERCHANT},
            operator_user_id=ctx["user"],
            tenant_id=ctx["tenant"],
            username="nope",
            password="S6User@abc",
            role_code=ROLE_MERCHANT,
        )
    with pytest.raises(ForbiddenError):
        await ctx["ops"].set_status(
            actor_role_codes={ROLE_ADMIN},
            operator_user_id=ctx["admin"],
            user_id=ctx["admin"],
            enabled=False,
        )
    users = await ctx["ops"].list_users(actor_role_codes={ROLE_TECH_SUPPORT})
    logs = await ctx["ops"].list_logs(actor_role_codes={ROLE_ADMIN})
    assert users["pageSize"] == 10
    assert all("tenantId" in item and "roleCodes" in item for item in users["items"])
    assert logs["pageSize"] == 10  # 2026-11-17：账号日志统一 10 条/页
    dumped = json.dumps(logs["items"], ensure_ascii=False)
    assert "S6User@abc" not in dumped
    assert "S6Reset@abc" not in dumped
    assert "password" not in RealphotosAccountLog.__table__.columns
    stored = await db.get(User, int(created["id"]))
    assert stored is not None
    assert stored.password_hash != "S6Reset@abc"
    disabled = await ctx["ops"].set_preset_enabled(
        actor_role_codes={ROLE_ADMIN}, code=S1_ENABLED_PRESETS[0]["code"], enabled=False
    )
    assert disabled["enabled"] is False
    listed = await ctx["ops"].list_enabled_presets()
    assert S1_ENABLED_PRESETS[0]["code"] not in {item["code"] for item in listed}
    asset = await ctx["loop"].upload(tenant_id=ctx["tenant"], owner_account_id=ctx["user"], data=_jpeg())
    with pytest.raises(BusinessError) as rejected:
        await ctx["loop"].submit_batch(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            actor_role_codes={ROLE_MERCHANT},
            asset_ids=[int(asset.id)],
            preset_code=S1_ENABLED_PRESETS[0]["code"],
            idempotency_key="s6-preset-off",
        )
    assert rejected.value.code == "PRESET_REJECTED"
    # PRODUCT-GAP A7: MakerNote allowed; top-level author/IP-GEO rejected (author via legacyParameters ok).
    saved_mn = await ctx["ops"].save_preset(
        actor_role_codes={ROLE_ADMIN},
        code="s6-brand",
        device_type="phone",
        brand="Canon",
        model_name="EOS-S6",
        maker_note="CANON",
        iso="100",
        shutter="1/125",
        aperture="f/1.8",
        focal_length="26mm",
        ai_positive_prompt="pos",
        ai_negative_prompt="neg",
    )
    assert saved_mn["makerNote"] == "CANON"
    assert saved_mn["aiPositivePrompt"] == "pos"
    with pytest.raises(BusinessError):
        await ctx["ops"].save_preset(
            actor_role_codes={ROLE_ADMIN},
            code="s6-author",
            device_type="phone",
            brand="Canon",
            model_name="EOS-S6",
            author="someone",
        )
    saved_copy = await ctx["ops"].save_preset(
        actor_role_codes={ROLE_ADMIN},
        code="s6-copyright-lp",
        device_type="phone",
        brand="Canon",
        model_name="EOS-CR",
        iso="100",
        shutter="1/125",
        aperture="f/1.8",
        focal_length="26mm",
        legacy_parameters={"author": "Ada", "copyright": "© 2026 Ada", "ip_geo": "SHOULD_STRIP"},
    )
    lp = saved_copy.get("legacyParameters") or {}
    assert lp.get("author") == "Ada"
    assert lp.get("copyright") == "© 2026 Ada"
    assert "ip_geo" not in lp and "ipGeo" not in lp
    with pytest.raises(BusinessError) as hb_rejected:
        await ctx["ops"].save_preset(
            actor_role_codes={ROLE_ADMIN},
            code="s6-hb-block",
            device_type="phone",
            brand="Honeybadger",
            model_name="HB-Blocked",
            iso="100",
            shutter="1/125",
            aperture="f/1.8",
            focal_length="26mm",
        )
    assert hb_rejected.value.code == "INPUT_INVALID"
    with pytest.raises(ForbiddenError):
        await ctx["ops"].save_preset(
            actor_role_codes={ROLE_MERCHANT},
            code="s6-merchant",
            device_type="phone",
            brand="Canon",
            model_name="EOS-No",
        )
    metrics = await ctx["ops"].metrics(actor_role_codes={ROLE_ADMIN})
    assert metrics["merchantCards"] is False
    assert metrics["cost"] is None
    assert metrics["cost"] is None
    assert metrics["costReason"] in {"no_upstream_calls", "unit_price_missing"}
    assert metrics.get("creditsNotUsedForCost") is True
    assert isinstance(metrics["modelCalls"], int)
    assert metrics["modelCalls"] >= 0
    assert isinstance(metrics["storageBytes"], int)
    assert "gps" not in BatchBody.model_fields


@pytest.mark.asyncio
async def test_list_tenants_and_tenant_scoped_users(db):
    ctx = await _funded(db)
    created = await ctx["ops"].create_user(
        actor_role_codes={ROLE_TECH_SUPPORT},
        operator_user_id=ctx["tech"],
        tenant_id=ctx["tenant"],
        username="rp_s6_tenant_row",
        password="S6User@abc",
        role_code=ROLE_MERCHANT,
    )
    tenants = await ctx["ops"].list_tenants(actor_role_codes={ROLE_TECH_SUPPORT})
    assert tenants["pageSize"] == 10
    match = next((row for row in tenants["items"] if int(row["tenantId"]) == int(ctx["tenant"])), None)
    assert match is not None
    assert match["tenantName"]
    assert match["tenantCode"]
    assert int(match["accountCount"]) >= 1
    scoped = await ctx["ops"].list_users(
        actor_role_codes={ROLE_TECH_SUPPORT},
        tenant_id=ctx["tenant"],
    )
    ids = {int(item["id"]) for item in scoped["items"]}
    assert int(created["id"]) in ids
    assert all(int(item["tenantId"]) == int(ctx["tenant"]) for item in scoped["items"])
    hit = next(item for item in scoped["items"] if int(item["id"]) == int(created["id"]))
    assert ROLE_MERCHANT in hit["roleCodes"]
    with pytest.raises(ForbiddenError):
        await ctx["ops"].list_tenants(actor_role_codes={ROLE_MERCHANT})
