"""Unit coverage for BLOCKING-FIX A–G slices that do not need live suppliers."""

from __future__ import annotations

import io
import json
import subprocess

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import func, select

from app.capabilities.realphotos.models import RealphotosCreditReservation, RealphotosImageTask
from app.capabilities.realphotos.permissions import ROLE_MERCHANT
from app.capabilities.realphotos.services.asset_naming import compose_list_filename
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.five_layer import run_five_layer
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.core.config import settings
from app.core.exceptions import BusinessError


def _jpeg(*, width: int = 320, height: int = 240) -> bytes:
    rng = np.random.default_rng(3)
    pixels = rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buf, format="JPEG", quality=40, subsampling=0)
    return buf.getvalue()


def test_gemini_default_is_local_available_model() -> None:
    assert settings.GEMINI_MODEL == "gemini-3.1-pro-preview"


def test_filename_order_and_degrade() -> None:
    named = compose_list_filename(
        meta={
            "name": "杯",
            "seller": "店",
            "sku": "SKU1",
            "asn": "",
            "price": "9.9",
            "website": "",
            "url": "https://x.example/a.jpg",
        },
        asset_id=7,
        origin_kind="local_upload",
    )
    assert named["displayName"] == "杯_店_SKU1_9.9_https://x.example/a.jpg"
    assert named["degraded"] == "false"
    empty = compose_list_filename(
        meta={"name": "", "seller": "", "sku": "", "asn": "", "price": "", "website": "", "url": ""},
        asset_id=8,
        origin_kind="local_upload",
    )
    assert empty["degraded"] == "true"
    assert "8" in empty["displayName"]


def test_gps_fixed_and_none_roundtrip() -> None:
    source = _jpeg()
    none_preset = dict(S1_ENABLED_PRESETS[0])
    none_out = run_five_layer(source=source, preset=none_preset, seed=11)
    raw = subprocess.run(
        ["exiftool", "-json", "-GPSLatitude#", "-"],
        input=none_out.jpeg,
        check=True,
        capture_output=True,
    )
    assert "GPSLatitude" not in json.loads(raw.stdout.decode())[0]

    fixed = dict(S1_ENABLED_PRESETS[0])
    fixed["gpsMode"] = "fixed"
    fixed["gpsConfig"] = {"latitude": "31.2304", "longitude": "121.4737", "altitude": "12"}
    fixed_out = run_five_layer(source=source, preset=fixed, seed=12)
    raw2 = subprocess.run(
        ["exiftool", "-json", "-GPSLatitude#", "-GPSLongitude#", "-"],
        input=fixed_out.jpeg,
        check=True,
        capture_output=True,
    )
    row = json.loads(raw2.stdout.decode())[0]
    assert abs(float(row["GPSLatitude"]) - 31.2304) < 0.001
    assert abs(float(row["GPSLongitude"]) - 121.4737) < 0.001
    gps_field = next(f for f in fixed_out.fields if f["tag"] == "GPSLatitude")
    assert gps_field["verification_status"] == "verified"


def test_gps_random_by_scene_writes_or_skips_with_reason() -> None:
    source = _jpeg()
    preset = dict(S1_ENABLED_PRESETS[0])
    preset["gpsMode"] = "random_by_scene"
    preset["gpsConfig"] = {"sceneRule": "urban"}
    out = run_five_layer(source=source, preset=preset, seed=99)
    gps_field = next(f for f in out.fields if f["tag"] == "GPSLatitude")
    assert gps_field["verification_status"] in {"verified", "skipped"}


def test_generation_png_with_legacy_random_gps_processes() -> None:
    """Reproduce merchant generation→process: PNG + random_by_scene without sceneRule."""
    rng = np.random.default_rng(9)
    pixels = rng.integers(0, 255, size=(512, 768, 3), dtype=np.uint8)
    png_buf = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(png_buf, format="PNG")
    source = png_buf.getvalue()
    assert source.startswith(b"\x89PNG")
    preset = dict(S1_ENABLED_PRESETS[0])
    preset["gpsMode"] = "random_by_scene"
    preset["gpsConfig"] = {}
    out = run_five_layer(source=source, preset=preset, seed=101)
    assert out.jpeg.startswith(b"\xff\xd8\xff")
    assert out.width == 768 and out.height == 512
    gps_field = next(f for f in out.fields if f["tag"] == "GPSLatitude")
    assert gps_field["verification_status"] == "skipped"


def test_aperture_f14_does_not_fail_apex_write() -> None:
    """f/1.4 → ApertureValue APEX < 1; exiftool may refuse the tag — FNumber must still pass."""
    source = _jpeg(width=640, height=480)
    preset = dict(S1_ENABLED_PRESETS[0])
    preset["aperture"] = "f/1.4"
    preset["gpsMode"] = "none"
    preset["makerNote"] = "Huawei"
    out = run_five_layer(source=source, preset=preset, seed=106)
    assert out.jpeg.startswith(b"\xff\xd8\xff")
    fn = next(f for f in out.fields if f["tag"] == "FNumber")
    av = next(f for f in out.fields if f["tag"] == "ApertureValue")
    assert fn["verification_status"] == "verified"
    assert av["verification_status"] == "verified"
    assert "1.4" in str(fn["read_back"]) or float(fn["read_back"]) == 1.4


@pytest.mark.asyncio
async def test_copy_no_reserve_and_latch(db):
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="copy",
        idempotency_key="copy-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    loop = RealphotosS1Service(db)
    credits = RealphotosCreditService(db)
    asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg(width=1024, height=768))
    source = await loop.submit_single(
        tenant_id=tenant,
        owner_account_id=user,
        actor_role_codes={ROLE_MERCHANT},
        asset_id=int(asset.id),
        preset_code=S1_ENABLED_PRESETS[0]["code"],
        idempotency_key="copy-src",
        detection_mode="gemini",
    )
    before = await credits.get_wallet(tenant_id=tenant)
    copied = await loop.copy_processing_task(
        tenant_id=tenant,
        owner_account_id=user,
        source_task_id=int(source.id),
        idempotency_key="copy-dst",
        actor_role_codes={ROLE_MERCHANT},
        detection_mode="gemini",
    )
    assert copied.copied_from_task_id == int(source.id)
    assert copied.billing_mode == "copy_no_reserve"
    after = await credits.get_wallet(tenant_id=tenant)
    assert int(after["reservedInteger"]) == int(before["reservedInteger"])
    reservations = int(
        await db.scalar(
            select(func.count()).select_from(RealphotosCreditReservation).where(
                RealphotosCreditReservation.task_id == int(copied.id)
            )
        )
        or 0
    )
    assert reservations == 0
    with pytest.raises(BusinessError) as exc:
        await loop.submit_single(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset.id),
            preset_code=S1_ENABLED_PRESETS[0]["code"],
            idempotency_key="copy-blocked",
            detection_mode="gemini",
        )
    assert exc.value.code == "COPY_LATCH_ACTIVE"
    assert await db.scalar(select(func.count()).select_from(RealphotosImageTask)) >= 2
