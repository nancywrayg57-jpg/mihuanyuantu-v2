"""S1 enabled preset catalog. Not the 405 admin console (that is S6)."""

from __future__ import annotations

from app.capabilities.realphotos.constants import (
    RECHARGE_CREDITS_BY_YUAN,
    RECHARGE_PRICE_FORMULA,
    RECHARGE_TIERS_YUAN,
)

# 虚构型号，避免把未授权品牌 MakerNote 写成已写入。gpsMode=none：不发明坐标。
S1_ENABLED_PRESETS: tuple[dict, ...] = (
    {
        "code": "s1-phone-01",
        "deviceType": "phone",
        "brand": "Honeybadger",
        "model": "HB-Phone-1",
        "iso": "100",
        "shutter": "1/120",
        "aperture": "f/1.8",
        "focalLength": "26mm",
        "gpsMode": "none",
    },
    {
        "code": "s1-dslr-01",
        "deviceType": "dslr",
        "brand": "Honeybadger",
        "model": "HB-DSLR-1",
        "iso": "200",
        "shutter": "1/200",
        "aperture": "f/2.8",
        "focalLength": "50mm",
        "gpsMode": "none",
    },
    {
        "code": "s1-mirrorless-01",
        "deviceType": "mirrorless",
        "brand": "Honeybadger",
        "model": "HB-ML-1",
        "iso": "400",
        "shutter": "1/250",
        "aperture": "f/4",
        "focalLength": "35mm",
        "gpsMode": "none",
    },
)

assert len(S1_ENABLED_PRESETS) <= 3


def preset_by_code(code: str) -> dict | None:
    for item in S1_ENABLED_PRESETS:
        if item["code"] == code:
            return dict(item)
    return None


def credits_for_tier_yuan(yuan: int) -> int:
    """待决策清单已确认档位：100/300/500/1000/3000 元对应 1000/3150/5500/11500/36000 积分。"""
    if int(yuan) not in RECHARGE_TIERS_YUAN:
        return 0
    return int(RECHARGE_CREDITS_BY_YUAN[int(yuan)])


def price_formula() -> str:
    return RECHARGE_PRICE_FORMULA
