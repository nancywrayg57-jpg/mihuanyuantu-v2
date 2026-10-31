"""Unit tests for label rules and metric formulas (no production images required)."""

from __future__ import annotations

import math
from pathlib import Path

from eval.labels import is_excluded_original, label_for_stem, stem_of
from eval.metrics import summarize_detector, wilson_interval
from eval.schema import map_probability


def test_label_ai_jimeng_and_doubao():
    assert label_for_stem("AI图片1-即梦生成") == "ai_generated"
    assert label_for_stem("即梦AI生图 (3)") == "ai_generated"
    assert label_for_stem("AI生图-豆包 (12)") == "ai_generated"
    assert label_for_stem("豆包AI生成") == "ai_generated"


def test_label_physical_and_screenshot_q4():
    assert label_for_stem("手机实拍 (12)") == "physical_device"
    assert label_for_stem("手机实拍-微信导出 (5)") == "physical_device"
    assert label_for_stem("手机截屏") == "physical_device"
    assert label_for_stem("电脑截屏") == "physical_device"
    assert label_for_stem("真实拍摄-网页保存") == "physical_device"


def test_excluded_png():
    assert is_excluded_original(Path("即梦AI生图 (1).png"))
    assert not is_excluded_original(Path("即梦AI生图 (1).jpg"))


def test_stem_alignment():
    assert stem_of(Path("手机实拍 (12)_legacy_20261029_exif.jpg")) == "手机实拍 (12)"
    assert stem_of(Path("手机实拍 (12)_legacy_r2_20261031.jpg")) == "手机实拍 (12)"
    assert stem_of(Path("手机实拍 (12)_legacy_r3_20261031.jpg")) == "手机实拍 (12)"


def test_map_probability():
    assert map_probability(0.8, threshold=0.5, uncertain_band=0.0) == "ai_generated"
    assert map_probability(0.2, threshold=0.5, uncertain_band=0.0) == "physical_device"
    assert map_probability(0.52, threshold=0.5, uncertain_band=0.05) == "uncertain"


def test_wilson_and_metric_b_example_from_appendix():
    # Appendix B: 8 fail / 194 denom = 4.12%
    lo, hi = wilson_interval(8, 194)
    assert 0.01 < lo < 0.05
    assert 0.04 < hi < 0.09

    manifest = []
    results = {}
    # 66 AI + 132 physical on g0, crafted to match appendix-ish rates
    for i in range(66):
        stem = f"AI生图-豆包 ({i})"
        manifest.append({"stem": stem, "label": "ai_generated", "round": "g0", "status": "ok"})
        # 58 ai, 6 physical, 2 uncertain → A_ai=6/64
        if i < 58:
            v = "ai_generated"
        elif i < 64:
            v = "physical_device"
        else:
            v = "uncertain"
        results[(stem, "g0")] = {"stem": stem, "round": "g0", "verdict": v, "ts": 1}
    for i in range(132):
        stem = f"手机实拍 ({i})"
        manifest.append({"stem": stem, "label": "physical_device", "round": "g0", "status": "ok"})
        if i < 124:
            v = "physical_device"
        elif i < 129:
            v = "ai_generated"
        else:
            v = "uncertain"
        results[(stem, "g0")] = {"stem": stem, "round": "g0", "verdict": v, "ts": 1}

    # one processed round: 186 phys, 8 ai, 3 unc, 1 tech
    for i in range(198):
        stem = f"stem{i}"
        label = "ai_generated" if i < 66 else "physical_device"
        manifest.append({"stem": stem, "label": label, "round": "r1", "status": "ok"})
        if i < 186:
            v = "physical_device"
        elif i < 194:
            v = "ai_generated"
        elif i < 197:
            v = "uncertain"
        else:
            v = "tech_fail"
        results[(stem, "r1")] = {"stem": stem, "round": "r1", "verdict": v, "ts": 1}

    rep = summarize_detector("toy", manifest, results)
    assert abs(rep["metric_A"]["A_ai"] - 6 / 64) < 1e-9
    assert abs(rep["metric_A"]["A_real"] - 5 / 129) < 1e-9
    b = rep["rounds"]["r1"]["B_round"]
    assert abs(b - 8 / 194) < 1e-9
    assert rep["rounds"]["r1"]["pass_B_lt_5"] is True
