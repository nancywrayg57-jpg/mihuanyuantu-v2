"""S3 detector parsing and auto-redo rules. A live Gemini call is the dev-host smoke."""

from __future__ import annotations

import pytest

from app.capabilities.realphotos.services.gemini_detector import parse_gemini_report
from app.capabilities.realphotos.services.redo_policy import accepted, should_auto_redo, validate_setting
from app.core.exceptions import BusinessError


def test_pass_rule_requires_both_and_does_not_average() -> None:
    assert accepted(passed=True, total_score=75)
    assert accepted(passed=True, total_score=74) is False
    assert accepted(passed=False, total_score=90) is False


def test_threshold_equality_does_not_redo_and_baseline_is_independent() -> None:
    assert should_auto_redo(enabled=True, total_score=69, threshold=70, redo_count=0, extra_rounds=1)
    assert should_auto_redo(enabled=True, total_score=70, threshold=70, redo_count=0, extra_rounds=1) is False
    assert should_auto_redo(enabled=False, total_score=10, threshold=70, redo_count=0, extra_rounds=1) is False
    assert should_auto_redo(enabled=True, total_score=80, threshold=90, redo_count=0, extra_rounds=1)
    assert should_auto_redo(enabled=True, total_score=10, threshold=70, redo_count=1, extra_rounds=1) is False


def test_setting_bounds() -> None:
    validate_setting(threshold=0, extra_rounds=1)
    validate_setting(threshold=100, extra_rounds=5)
    with pytest.raises(BusinessError):
        validate_setting(threshold=101, extra_rounds=1)
    with pytest.raises(BusinessError):
        validate_setting(threshold=70, extra_rounds=0)


def test_parser_keeps_model_total_and_rejects_html() -> None:
    report = parse_gemini_report(
        '{"noise":10,"depthOfField":10,"lighting":10,"colorRealism":10,"overallRealism":10,'
        '"total_score":80,"passed":true,"reason":""}'
    )
    assert report["total_score"] == 80
    with pytest.raises(BusinessError) as exc:
        parse_gemini_report("<html>nope</html>")
    assert exc.value.code == "GEMINI_TECHNICAL"
    with pytest.raises(BusinessError):
        parse_gemini_report('{"noise":1,"depthOfField":1,"lighting":1,"colorRealism":1,"overallRealism":1,"passed":true}')
    with pytest.raises(BusinessError) as fractional:
        parse_gemini_report(
            '{"noise":1.5,"depthOfField":10,"lighting":10,"colorRealism":10,"overallRealism":10,'
            '"total_score":10,"passed":false,"reason":""}'
        )
    assert fractional.value.code == "GEMINI_TECHNICAL"
    with pytest.raises(BusinessError) as boolean_score:
        parse_gemini_report(
            '{"noise":true,"depthOfField":10,"lighting":10,"colorRealism":10,"overallRealism":10,'
            '"total_score":10,"passed":false,"reason":""}'
        )
    assert boolean_score.value.code == "GEMINI_TECHNICAL"


def test_detect_timeout_is_technical(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.capabilities.realphotos.services import gemini_detector
    from app.core.config import settings

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-test")

    def _timeout(*_args, **_kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(gemini_detector.urllib.request, "urlopen", _timeout)
    with pytest.raises(BusinessError) as exc:
        gemini_detector.detect_jpeg(b"\xff\xd8\xff")
    assert exc.value.code == "GEMINI_TECHNICAL"


def _jpeg() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (12, 24, 36)).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _envelope(text: str) -> bytes:
    import json

    return json.dumps(
        {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    ).encode()


class _Response:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.raw


@pytest.mark.asyncio
async def test_timeout_and_non_integer_hold_without_download(db, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import func, select

    from app.capabilities.realphotos.constants import DETECT_GEMINI
    from app.capabilities.realphotos.models import RealphotosCreditReservation, RealphotosDetectionResult
    from app.capabilities.realphotos.permissions import ROLE_MERCHANT
    from app.capabilities.realphotos.services import five_layer, gemini_detector
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
    from app.core.config import settings

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-test")
    monkeypatch.setattr(
        five_layer,
        "run_five_layer",
        lambda *, source, preset, seed: five_layer.FiveLayerOutput(
            jpeg=source, fields=[], width=1024, height=768
        ),
    )
    mode = {"kind": "timeout"}

    def _urlopen(*_args, **_kwargs):
        if mode["kind"] == "timeout":
            raise TimeoutError("timed out")
        return _Response(
            _envelope(
                '{"noise":1.5,"depthOfField":10,"lighting":10,"colorRealism":10,"overallRealism":10,'
                '"total_score":10,"passed":false,"reason":""}'
            )
        )

    monkeypatch.setattr(gemini_detector.urllib.request, "urlopen", _urlopen)
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    loop = RealphotosS1Service(db)
    recharge = RealphotosRechargeService(db)
    jobs = RealphotosJobService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="s3-unit",
        idempotency_key="s3-technical-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
    preset = S1_ENABLED_PRESETS[0]["code"]

    async def run(key: str):
        task = await loop.submit_single(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset.id),
            preset_code=preset,
            idempotency_key=key,
            detection_mode=DETECT_GEMINI,
        )
        claimed = await jobs.claim(
            worker_id="s3-unit",
            job_kinds=("process_image",),
            payload_task_id=int(task.id),
        )
        assert claimed is not None
        done = await loop.execute_queued(claimed)
        reservation = (
            await db.execute(
                select(RealphotosCreditReservation).where(
                    RealphotosCreditReservation.task_id == int(done.id)
                )
            )
        ).scalar_one()
        reports = await db.scalar(
            select(func.count())
            .select_from(RealphotosDetectionResult)
            .where(RealphotosDetectionResult.task_id == int(done.id))
        )
        assert done.failure_class == "GEMINI_TECHNICAL"
        assert done.output_object_key is None
        assert done.credit_disposition == "held_until_tech_support"
        assert reservation.state == "held"
        assert int(reservation.amount) == 10
        assert int(reports or 0) == 0
        assert await loop.detection_payload(tenant_id=tenant, task_id=int(done.id)) is None

    await run("s3-timeout")
    mode["kind"] = "fraction"
    await run("s3-fraction")


@pytest.mark.asyncio
async def test_reprocess_rejects_fixture_accepted_and_missing_file(db) -> None:
    from app.capabilities.realphotos.models import (
        RealphotosBatch,
        RealphotosDetectionResult,
        RealphotosImageTask,
        RealphotosTaskChain,
    )
    from app.capabilities.realphotos.permissions import ROLE_MERCHANT
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service

    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    loop = RealphotosS1Service(db)
    asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
    preset = S1_ENABLED_PRESETS[0]["code"]
    batch = RealphotosBatch(tenant_id=tenant, owner_account_id=user, image_count=1, preset_code=preset)
    db.add(batch)
    await db.flush()
    chain = RealphotosTaskChain(tenant_id=tenant, batch_id=int(batch.id), round_no=1)
    db.add(chain)
    await db.flush()

    async def source(*, key: str, detector: str, passed: bool, total: int, output: str | None) -> int:
        task = RealphotosImageTask(
            tenant_id=tenant,
            owner_account_id=user,
            batch_id=int(batch.id),
            chain_id=int(chain.id),
            asset_id=int(asset.id),
            status="FAILED",
            preset_code=preset,
            preset_snapshot={"model": "HB-Phone-1"},
            pre_review_mode="pass",
            detection_mode="gemini",
            idempotency_key=key,
            output_object_key=output,
            failure_class="detection_not_passed",
            pipeline_version="s2-five-layer-1",
        )
        db.add(task)
        await db.flush()
        db.add(
            RealphotosDetectionResult(
                tenant_id=tenant,
                task_id=int(task.id),
                noise=total,
                depth_of_field=total,
                lighting=total,
                color_realism=total,
                overall_realism=total,
                total_score=total,
                passed=passed,
                reason="unit",
                detector=detector,
            )
        )
        await db.flush()
        return int(task.id)

    fixture_id = await source(
        key="fixture-source", detector="fixture", passed=False, total=40, output="tenant/1/output/fixture.jpg"
    )
    accepted_id = await source(
        key="accepted-source", detector="gemini-control", passed=True, total=80, output="tenant/1/output/accepted.jpg"
    )
    missing_id = await source(
        key="missing-source", detector="gemini-control", passed=False, total=40, output=None
    )
    for task_id in (fixture_id, accepted_id, missing_id):
        with pytest.raises(BusinessError) as exc:
            await loop.reprocess(
                tenant_id=tenant,
                owner_account_id=user,
                actor_role_codes={ROLE_MERCHANT},
                source_task_id=task_id,
                preset_code=preset,
                idempotency_key=f"reprocess-{task_id}",
            )
        assert exc.value.code == "REPROCESS_REJECTED"
