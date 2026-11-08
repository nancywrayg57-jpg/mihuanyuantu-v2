"""FIX-TASK-FAILURE-UX-2026-11-08 static + unit contract e2e.

Covers E-F1–E-F6 source/API contracts (display maps, detail blocks, GPS soft
hint, retry membership). Exit mark: FIX_TASK_FAILURE_UX_E2E_PASS.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

LOG_PATH = Path("/tmp/fix-task-failure-ux-e2e.log")
ROOT = Path(__file__).resolve().parents[3]
FE = ROOT / "aojuai-main" / "frontend" / "src"
BE = ROOT / "aojuai-main" / "backend"
LABELS = FE / "lib" / "realphotos-labels.ts"
TASKS = FE / "app" / "(app)" / "realphotos" / "tasks" / "page.tsx"
BATCH = FE / "app" / "(app)" / "realphotos" / "batch" / "batch-client.tsx"
PRESETS = FE / "app" / "(app)" / "realphotos" / "presets" / "page.tsx"
S1_PROC = BE / "app" / "capabilities" / "realphotos" / "services" / "s1_processing.py"
S1_API = BE / "app" / "capabilities" / "realphotos" / "api" / "s1.py"
GPS = BE / "app" / "capabilities" / "realphotos" / "services" / "gps_write.py"


def note(message: str) -> None:
    line = message.rstrip()
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def must(cond: bool, msg: str) -> None:
    if not cond:
        note(f"FAIL {msg}")
        raise AssertionError(msg)
    note(f"PASS {msg}")


def _load_gps():
    sys.path.insert(0, str(BE))
    spec = importlib.util.spec_from_file_location("gps_write_mod", GPS)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    note("fix_task_failure_ux_e2e start")
    note("production_billing=false s7_started=false")
    note("ticket=FIX-TASK-FAILURE-UX-2026-11-08 branch=cursor/fix-task-failure-ux-9973")

    labels = LABELS.read_text(encoding="utf-8")
    tasks = TASKS.read_text(encoding="utf-8")
    batch = BATCH.read_text(encoding="utf-8")
    presets = PRESETS.read_text(encoding="utf-8")
    s1_proc = S1_PROC.read_text(encoding="utf-8")
    s1_api = S1_API.read_text(encoding="utf-8")
    gps_src = GPS.read_text(encoding="utf-8")

    # --- E-F1: failure / credit maps ---
    for code, cn in (
        ("detection_not_passed", "检测未通过"),
        ("pre_review_failed", "预审请求失败（技术）"),
        ("GEMINI_TECHNICAL", "Gemini 检测技术异常"),
        ("GEMINI_NOT_CONFIGURED", "最终检测未配置"),
        ("technical", "历史联调替身（已停用）"),
        ("released_detection_not_passed", "检测未通过已释放"),
        ("held_unresolved_prd_4_5_vs_fr016", "争议冻结"),
    ):
        must(code in labels and cn in labels, f"E-F1_map_{code}")
    must("未知${kind}" in labels or "未知" in labels, "E-F1_unknown_prefix_kept_for_novel_codes")
    must("'失败原因'" in labels, "E-F1_failure_kind_token")
    must("failureClassLabelForTask" in labels, "E-F1_for_task_helper")

    # --- E-F2 / E-F3: detail blocks ---
    must("failureMessage" in tasks, "E-F2_failureMessage_ui")
    must("failedTags" in tasks, "E-F2_exif_failed_tags_ui")
    must("passScoreThreshold" in tasks or "DETECTION_PASS_SCORE" in tasks, "E-F2_threshold_ui")
    must("通过线" in tasks, "E-F2_pass_line_copy")
    must("detectionNotPassedExplanation" in labels and "未达通过线" in labels, "E-F3_scheme_A_copy")
    must("platformGateExplanation" in s1_proc, "E-F2_api_platform_gate")
    must("failure_detail" in s1_proc, "E-F2_snapshot_kind")
    must("failureMessage" in s1_api and "_enrich_task_detail" in s1_api, "E-F2_api_enrich")
    must("detectionMode" in s1_api, "E-F2_detectionMode_payload")

    # --- E-F5: fixture vs real tech ---
    must("历史联调替身（已停用）" in labels, "E-F5_fixture_label")
    must("failureClassLabelForTask" in tasks, "E-F5_list_uses_for_task")
    must("历史联调替身（已停用）" in tasks, "E-F5_detail_mode_copy")

    # --- E-F4: GPS soft hint / hard block ---
    must("gpsWillSkip" in gps_src, "E-F4_gpsWillSkip_field")
    must("gpsSubmitBlocked" in batch, "E-F4_batch_hard_block")
    must("GPS 提示" in batch or "将跳过 GPS" in batch, "E-F4_batch_soft_hint")
    must("gpsWritableReason" in presets, "E-F4_preset_detail_reason")
    gps = _load_gps()
    fixed = gps.gps_writability(gps_mode="fixed", gps_config={})
    must(fixed["gpsWritable"] is True and fixed["gpsWillSkip"] is True, "E-F4_fixed_skip_writable")
    must("跳过" in str(fixed.get("gpsWritableReason") or ""), "E-F4_fixed_reason_cn")
    rnd = gps.gps_writability(gps_mode="random_by_scene", gps_config={})
    must(rnd["gpsWritable"] is True and rnd["gpsWillSkip"] is True, "E-F4_random_skip_writable")
    bad = gps.gps_writability(gps_mode="weird_mode", gps_config={})
    must(bad["gpsWritable"] is False, "E-F4_unknown_mode_blocked")

    # --- E-F6: retry membership ---
    must('"pre_review_failed"' in s1_proc or "'pre_review_failed'" in s1_proc, "E-F6_backend_retryable")
    must("'pre_review_failed'" in tasks, "E-F6_frontend_retryable")
    must("pre_review" in labels and "pre_review_failed" in labels, "E-F6_labels_distinct")

    note("FIX_TASK_FAILURE_UX_E2E_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
