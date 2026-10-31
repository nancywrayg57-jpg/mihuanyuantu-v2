"""Filename → ground-truth label rules.

Work order §3.3 / Q1 / Q4, adapted to the renamed asset pack uploaded 2026-10-31:

  AI生图-即梦-NNNN.(png|jpg)     → ai_generated
  AI生图-豆包-NNNN.(png|jpg)     → ai_generated
  手机实拍-NNNN.jpg              → physical_device
  手机实拍-微信导出-NNNN.jpg     → physical_device
  其他-NNNN.(jpg|png)            → physical_device  (Q4: screenshots/web-saved)

R-1 exclusions (no processed counterpart): AI生图-即梦-0025 .. 0029
Processed rounds share the same stem; files are always .jpg (no _legacy_ suffix).
"""

from __future__ import annotations

import re
from pathlib import Path

AI_PREFIXES = (
    "AI生图-即梦-",
    "AI生图-豆包-",
)

PHYSICAL_PREFIXES = (
    "手机实拍-微信导出-",
    "手机实拍-",
    "其他-",
)

# R-1: five originals without processed products
EXCLUDED_STEMS = {f"AI生图-即梦-{i:04d}" for i in range(25, 30)}

# Legacy suffix support (older pack); current pack has none.
ROUND_SUFFIXES = {
    "r1": "_legacy_20261029_exif",
    "r2": "_legacy_r2_20261031",
    "r3": "_legacy_r3_20261031",
}


def stem_of(path: Path) -> str:
    name = path.name
    for suf in ROUND_SUFFIXES.values():
        if suf in name:
            return name.split(suf)[0]
    return path.stem


def label_for_stem(stem: str) -> str:
    # Order matters: 微信导出 before 手机实拍-
    for pref in AI_PREFIXES:
        if stem.startswith(pref):
            return "ai_generated"
    for pref in PHYSICAL_PREFIXES:
        if stem.startswith(pref):
            return "physical_device"
    return "UNKNOWN"


def is_excluded_original(path: Path) -> bool:
    """Exclude R-1 stems (any extension) that have no processed counterpart."""
    return stem_of(path) in EXCLUDED_STEMS


def subclass_for_stem(stem: str) -> str:
    if stem.startswith("AI生图-即梦-"):
        return "ai_jimeng"
    if stem.startswith("AI生图-豆包-"):
        return "ai_doubao"
    if stem.startswith("手机实拍-微信导出-"):
        return "physical_wechat"
    if stem.startswith("手机实拍-"):
        return "physical_phone"
    if stem.startswith("其他-"):
        return "physical_other"  # screenshots / web-saved (Q4)
    return "unknown"
