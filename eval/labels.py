"""Filename → ground-truth label rules (work order §3.3 / Q1 / Q4)."""

from __future__ import annotations

import re
from pathlib import Path

AI_PATTERNS = [
    re.compile(r"AI图片1-即梦生成"),
    re.compile(r"即梦AI图片3"),
    re.compile(r"AI生图-即梦"),
    re.compile(r"即梦AI生图"),
    re.compile(r"AI生图-豆包"),
    re.compile(r"豆包AI生成"),
]

# Screenshots + web-saved + phone real / wechat exports → physical_device (Q4)
PHYSICAL_HINTS = [
    "手机实拍",
    "手机直出",
    "手机截屏",
    "电脑截屏",
    "真实拍摄-网页保存",
]

ROUND_SUFFIXES = {
    "r1": "_legacy_20261029_exif",
    "r2": "_legacy_r2_20261031",
    "r3": "_legacy_r3_20261031",
}

EXCLUDED_PNG_STEMS = {f"即梦AI生图 ({i})" for i in range(1, 6)}


def stem_of(path: Path) -> str:
    name = path.name
    for suf in ROUND_SUFFIXES.values():
        if suf in name:
            # e.g. foo_legacy_....jpg → foo
            base = name.split(suf)[0]
            return base
    return path.stem


def label_for_stem(stem: str) -> str:
    for pat in AI_PATTERNS:
        if pat.search(stem):
            return "ai_generated"
    for hint in PHYSICAL_HINTS:
        if hint in stem:
            return "physical_device"
    # Fallback: unknown — must be registered as anomaly, not silently labeled
    return "UNKNOWN"


def is_excluded_original(path: Path) -> bool:
    if path.suffix.lower() != ".png":
        return False
    return path.stem in EXCLUDED_PNG_STEMS
