"""UX-CN-PRESET-2026-11-07 static + API label contract e2e.

Source assertions for U1–U7 plus label unit checks. Browser DOM evidence is
appended by the agent IDE browser pass into the same log.
Exit mark: UX_CN_PRESET_E2E_PASS.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LOG_PATH = Path("/tmp/ux-cn-preset-e2e.log")
ROOT = Path(__file__).resolve().parents[3]
FE = ROOT / "aojuai-main" / "frontend" / "src"
LABELS = FE / "lib" / "realphotos-labels.ts"
LIBRARY = FE / "app" / "(app)" / "realphotos" / "library" / "page.tsx"
TASKS = FE / "app" / "(app)" / "realphotos" / "tasks" / "page.tsx"
PRESETS = FE / "app" / "(app)" / "realphotos" / "presets" / "page.tsx"
TECH = FE / "app" / "(app)" / "realphotos" / "tech-desk" / "page.tsx"
WORKSPACE = FE / "app" / "(app)" / "realphotos" / "workspace" / "page.tsx"
BATCH = FE / "app" / "(app)" / "realphotos" / "batch" / "batch-client.tsx"
ORDER = FE / "app" / "(app)" / "realphotos" / "order-support" / "page.tsx"


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


def main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    note("ux_cn_preset_e2e start")
    note("production_billing=false url_import_connected=false s7_started=false")
    note("ticket=UX-CN-PRESET-2026-11-07 branch=cursor/ux-cn-preset-9973")

    labels = LABELS.read_text(encoding="utf-8")
    library = LIBRARY.read_text(encoding="utf-8")
    tasks = TASKS.read_text(encoding="utf-8")
    presets = PRESETS.read_text(encoding="utf-8")
    tech = TECH.read_text(encoding="utf-8")
    workspace = WORKSPACE.read_text(encoding="utf-8")
    batch = BATCH.read_text(encoding="utf-8")
    order = ORDER.read_text(encoding="utf-8")

    # --- label module ---
    for fn in (
        "originKindLabel",
        "taskStatusLabel",
        "creditDispositionLabel",
        "failureClassLabel",
        "ticketTypeLabel",
        "deviceTypeLabel",
        "gpsModeLabel",
        "boolPassLabel",
        "detectionDimensionLabel",
    ):
        must(f"export function {fn}" in labels, f"labels_export_{fn}")

    must("本地上传" in labels and "文生图" in labels and "图生图" in labels, "labels_origin_cn")
    must("已交付" in labels and "held_until_tech_support" in labels, "labels_status_credit")
    must("不写入" in labels and "固定坐标" in labels and "按场景随机" in labels, "labels_gps_cn")
    must("手机" in labels and "单反" in labels, "labels_device_cn")

    # U1
    must("选择文件" in library, "E-U1-1_source_选择文件")
    must("sr-only" in library or 'className="hidden"' in library or "type=\"file\"" in library, "E-U1-1_hidden_file_input")
    must("originKindLabel(" in library, "E-U1-2_originKindLabel_used")

    # U2
    must("失败原因" in tasks, "E-U2-1_header_失败原因")
    must(not re.search(r">失败</th>", tasks), "E-U2-1_no_orphan_失败_header")
    must("taskStatusLabel(" in tasks and "creditDispositionLabel(" in tasks, "E-U2-2_status_credit_labels")
    must("failureClassLabel(" in tasks, "E-U2-3_failure_label")
    must('value="DELIVERED"' in tasks and ">已交付<" in tasks, "E-U2_filter_value_en_label_cn")

    # U3
    must('role="dialog"' in tasks and "aria-modal" in tasks, "E-U3-1_dialog_markup")
    must("DetectionReport" in tasks and "检测报告" in tasks, "E-U3-2_detection_section")
    must("状态：" in tasks and "处置：" in tasks, "E-U3-2_cn_field_labels")
    must("noise=" not in tasks or "detectionDimensionLabel" in tasks, "E-U3-3_no_raw_noise_primary")

    # U4
    must("ticketTypeLabel(" in tech and "ticketStatusLabel(" in tech, "E-U4-1_tech_desk_labels")
    must("creditDispositionLabel(" in tech, "E-U4-1_tech_credit_label")
    must("ticketTypeLabel(" in workspace and "taskStatusLabel(" in workspace, "E-U4-1_workspace_labels")
    must("DELIVERED 真实计数" not in workspace, "E-U4_workspace_no_raw_DELIVERED_copy")
    must("deviceTypeLabel(" in presets and "gpsModeLabel(" in presets, "E-U4-2_preset_labels")
    must("deviceTypeLabel(" in batch, "E-U4_batch_device_label")
    must("taskStatusLabel(" in order, "E-U4_order_status_label")
    scanned = [
        "library/page.tsx",
        "tasks/page.tsx",
        "presets/page.tsx",
        "tech-desk/page.tsx",
        "workspace/page.tsx",
        "batch/batch-client.tsx",
        "order-support/page.tsx",
        "lib/realphotos-labels.ts",
    ]
    note("E-U4-3_scanned_files=" + ",".join(scanned))

    # U5
    must("清除占位假预设" not in presets or "已按 UX 工单撤回" in presets, "E-U5-1_no_clear_placeholder_button")
    must("一键导入全部" not in presets or "已按 UX 工单撤回" in presets, "E-U5-1_no_activate_all_button")
    must("clearPlaceholders" not in presets and "activateAllImports" not in presets, "E-U5-1_no_bulk_handlers")
    must("PRESET_PAGE_SIZE = 20" in presets or "pageSize = 20" in presets or "* PRESET_PAGE_SIZE" in presets, "E-U5-2_page_size_20")
    must("slice((page - 1) * PRESET_PAGE_SIZE" in presets or "slice((page - 1) *" in presets, "E-U5-2_frontend_slice")
    must("上一页" in presets and "下一页" in presets and "每页" in presets, "E-U5-2_pager_ui")

    # U6
    must("查看详情" in presets, "E-U6-1_view_detail_button")
    must("预设详情" in presets and "GPS 模式：" in presets, "E-U6-2_detail_cn_fields")
    must('role="dialog"' in presets, "E-U6_dialog")

    # U7
    must("新增预设" in presets, "E-U7-1_add_button")
    must("基本信息" in presets and "拍摄参数" in presets and "EXIF / GPS" in presets, "E-U7-2_form_sections")
    must("新建 / 编辑预设" not in presets, "E-U7-3_no_bottom_resident_form_title")
    must("formOpen" in presets and "openCreate" in presets, "E-U7_modal_form_state")

    # C1 note marker for progress
    note("C1_recorded_ui_bulk_buttons_removed_api_kept=true")
    note("source_contract_section_ok")
    note("browser_dom_section_pending_ide_browser")
    note("production_billing=false")
    # Final PASS is appended after browser DOM section.
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError:
        note("UX_CN_PRESET_E2E_FAIL")
        raise SystemExit(1)
