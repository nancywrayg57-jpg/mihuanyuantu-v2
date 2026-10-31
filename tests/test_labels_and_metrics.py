"""Unit tests for label rules and metric formulas."""

from __future__ import annotations

from pathlib import Path

from eval.labels import is_excluded_original, label_for_stem, stem_of, subclass_for_stem
from eval.metrics import summarize_detector, wilson_interval
from eval.schema import map_probability


def test_label_ai_renamed_pack():
    assert label_for_stem("AI生图-即梦-0001") == "ai_generated"
    assert label_for_stem("AI生图-豆包-0042") == "ai_generated"


def test_label_physical_renamed_pack():
    assert label_for_stem("手机实拍-0012") == "physical_device"
    assert label_for_stem("手机实拍-微信导出-0005") == "physical_device"
    assert label_for_stem("其他-0001") == "physical_device"
    assert subclass_for_stem("其他-0006") == "physical_other"


def test_excluded_r1():
    assert is_excluded_original(Path("AI生图-即梦-0025.png"))
    assert is_excluded_original(Path("AI生图-即梦-0029.png"))
    assert not is_excluded_original(Path("AI生图-即梦-0024.png"))


def test_stem_alignment_same_stem():
    assert stem_of(Path("AI生图-即梦-0001.png")) == "AI生图-即梦-0001"
    assert stem_of(Path("AI生图-即梦-0001.jpg")) == "AI生图-即梦-0001"


def test_map_probability():
    assert map_probability(0.8, threshold=0.5, uncertain_band=0.0) == "ai_generated"
    assert map_probability(0.2, threshold=0.5, uncertain_band=0.0) == "physical_device"
    assert map_probability(0.52, threshold=0.5, uncertain_band=0.05) == "uncertain"


def test_wilson_and_metric_b_example_from_appendix():
    lo, hi = wilson_interval(8, 194)
    assert 0.01 < lo < 0.05
    assert 0.04 < hi < 0.09

    manifest = []
    results = {}
    for i in range(66):
        stem = f"AI生图-豆包-{i:04d}"
        manifest.append({"stem": stem, "label": "ai_generated", "round": "g0", "status": "ok"})
        if i < 58:
            v = "ai_generated"
        elif i < 64:
            v = "physical_device"
        else:
            v = "uncertain"
        results[(stem, "g0")] = {"stem": stem, "round": "g0", "verdict": v, "ts": 1}
    for i in range(132):
        stem = f"手机实拍-{i:04d}"
        manifest.append({"stem": stem, "label": "physical_device", "round": "g0", "status": "ok"})
        if i < 124:
            v = "physical_device"
        elif i < 129:
            v = "ai_generated"
        else:
            v = "uncertain"
        results[(stem, "g0")] = {"stem": stem, "round": "g0", "verdict": v, "ts": 1}

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
    assert abs(rep["rounds"]["r1"]["B_round"] - 8 / 194) < 1e-9
    assert rep["rounds"]["r1"]["pass_B_lt_5"] is True
