#!/usr/bin/env python3
"""Validate the minimal AidevOps workspace shape without external packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PHASE_FILES = {
    "00-discovery.yaml",
    "01-design.yaml",
    "02-delivery.yaml",
    "03-acceptance.yaml",
}

EXPECTED_CAPABILITIES = {
    "intake": "00-discovery.yaml",
    "idea-forge": "00-discovery.yaml",
    "prd": "00-discovery.yaml",
    "mvp-slicing": "00-discovery.yaml",
    "governance": "00-discovery.yaml",
    "designer": "01-design.yaml",
    "prototype-image-request": "01-design.yaml",
    "architect": "01-design.yaml",
    "delivery-planner": "02-delivery.yaml",
    "reviewer": "03-acceptance.yaml",
    "retro-knowledge": "03-acceptance.yaml",
}

REQUIRED: dict[str, tuple[str, ...]] = {
    "progress.yaml": (
        "workflow:",
        "current_phase:",
        "clarification_policy:",
        "vibe_coding:",
        "capability_queue:",
        "phase_gates:",
        "evidence_pointers:",
        "wiki: wiki.md",
        "next_action:",
    ),
    "wiki.md": (
        "# Local LLM Wiki:",
        "## Project Snapshot",
        "## Decision Ledger",
        "## Phase Knowledge",
        "### Discovery",
        "### Design",
        "### Delivery",
        "### Acceptance",
        "## Reusable Prompts and Commands",
        "## Vibe Coding Loops",
        "## Risks and Watchpoints",
        "## Backlog Knowledge",
    ),
    "00-discovery.yaml": (
        "phase: discovery",
        "phase_confirmation:",
        "knowledge_assets:",
        "clarification:",
        "idea_forge:",
        "business_case:",
        "governance:",
        "prd:",
        "requirements:",
        "mvp_scope:",
        "success_metrics:",
        "gate:",
    ),
    "01-design.yaml": (
        "phase: design",
        "phase_confirmation:",
        "knowledge_assets:",
        "product_design:",
        "service_system_design:",
        "interaction_design:",
        "information_architecture:",
        "design_spines:",
        "visual_system:",
        "prototype_image_request:",
        "system_flow_diagram:",
        "architecture:",
        "design_review:",
        "gate:",
    ),
    "02-delivery.yaml": (
        "phase: delivery",
        "phase_confirmation:",
        "knowledge_assets:",
        "sprint:",
        "tasks:",
        "governance_controls:",
        "deployment:",
        "git:",
        "version_control_required_before_code:",
        "verification:",
        "gate:",
    ),
    "03-acceptance.yaml": (
        "phase: acceptance",
        "phase_confirmation:",
        "knowledge_assets:",
        "verification:",
        "review:",
        "quality_gates:",
        "release_decision:",
        "retro:",
        "gate:",
    ),
}

REQUIRED_DIRS = ("input", "prototypes")


def png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:32]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def validate_progress(root: Path, text: str) -> list[str]:
    errors: list[str] = []

    clarification_mode = re.search(
        r"^clarification_policy:\s*\n(?:^\s{2}.+\n)*?^\s{2}mode:\s*([a-z-]+)\s*$",
        text,
        flags=re.MULTILINE,
    )
    if not clarification_mode:
        errors.append("progress.yaml: missing clarification_policy.mode")
    elif clarification_mode.group(1) not in {"ask-user", "auto-assume"}:
        errors.append(f"progress.yaml: unknown clarification_policy.mode {clarification_mode.group(1)!r}")

    current_phase = re.search(r"^current_phase:\s*([a-z_-]+)\s*$", text, flags=re.MULTILINE)
    if not current_phase:
        errors.append("progress.yaml: missing current_phase value")
    elif current_phase.group(1) not in {"discovery", "design", "delivery", "acceptance"}:
        errors.append(f"progress.yaml: unknown current_phase {current_phase.group(1)!r}")

    for phase_file in PHASE_FILES:
        if phase_file not in text:
            errors.append(f"progress.yaml: missing reference to {phase_file}")
        elif not (root / phase_file).exists():
            errors.append(f"progress.yaml: referenced file does not exist: {phase_file}")

    if "wiki.md" not in text:
        errors.append("progress.yaml: missing reference to wiki.md")
    elif not (root / "wiki.md").exists():
        errors.append("progress.yaml: referenced file does not exist: wiki.md")

    for capability, phase_file in EXPECTED_CAPABILITIES.items():
        pattern = (
            rf"capability:\s*{re.escape(capability)}\s*\n"
            rf"\s*phase_file:\s*{re.escape(phase_file)}\s*\n"
        )
        if not re.search(pattern, text):
            errors.append(f"progress.yaml: missing capability route {capability} -> {phase_file}")

    gate_names = set(re.findall(r"^\s{2}(discovery|design|delivery|acceptance):\s*$", text, flags=re.MULTILINE))
    for phase in ("discovery", "design", "delivery", "acceptance"):
        if phase not in gate_names:
            errors.append(f"progress.yaml: missing phase gate {phase}")
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    if not root.exists():
        return [f"missing workspace: {root}"]
    if not root.is_dir():
        return [f"not a directory: {root}"]

    for dirname in REQUIRED_DIRS:
        path = root / dirname
        if not path.exists():
            errors.append(f"missing directory: {dirname}")
        elif not path.is_dir():
            errors.append(f"not a directory: {dirname}")

    for filename, markers in REQUIRED.items():
        path = root / filename
        if not path.exists():
            errors.append(f"missing file: {filename}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in markers:
            if marker not in text:
                errors.append(f"{filename}: missing marker {marker!r}")
        if filename == "progress.yaml":
            errors.extend(validate_progress(root, text))
        if filename == "01-design.yaml":
            errors.extend(validate_required_prototype_images(root, text))
    return errors


def validate_required_prototype_images(root: Path, text: str) -> list[str]:
    errors: list[str] = []
    block_match = re.search(r"^prototype_image_request:\s*$", text, flags=re.MULTILINE)
    if not block_match:
        return errors
    block_start = block_match.start()
    next_top = re.search(r"^[a-zA-Z0-9_]+:\s*$", text[block_match.end():], flags=re.MULTILINE)
    block_end = block_match.end() + next_top.start() if next_top else len(text)
    block = text[block_start:block_end]

    required = re.search(r"^\s{2}required:\s*true\s*$", block, flags=re.MULTILINE)
    if not required:
        return errors

    validation_mode_match = re.search(r"^\s{2}validation_mode:\s*([a-z_]+)\s*$", block, flags=re.MULTILINE)
    validation_mode = validation_mode_match.group(1) if validation_mode_match else "design_review"

    if "design_system_lock:" not in block:
        errors.append("01-design.yaml: required prototype images need prototype_image_request.design_system_lock")
    if "visual_consistency_review:" not in block:
        errors.append("01-design.yaml: required prototype images need prototype_image_request.visual_consistency_review")
    elif validation_mode != "simple_return" and not re.search(r"^\s{4}status:\s*pass\s*$", block, flags=re.MULTILINE):
        errors.append("01-design.yaml: visual_consistency_review.status must be pass for strict prototype validation")

    asset_match = re.search(
        r"^\s{2}generated_assets:\s*\n((?:^\s{2,4}-\s+.+\n?)+)",
        block,
        flags=re.MULTILINE,
    )
    if not asset_match:
        errors.append("01-design.yaml: prototype_image_request.required is true but generated_assets is empty")
        return errors

    assets = []
    for line in asset_match.group(1).splitlines():
        item = re.sub(r"^\s*-\s*", "", line).strip().strip('"').strip("'")
        if item:
            assets.append(item)
    png_assets = [item for item in assets if item.lower().endswith(".png")]
    if not png_assets:
        errors.append("01-design.yaml: prototype_image_request.required is true but generated_assets lists no PNG files")
        return errors
    recommended_count_match = re.search(r"^\s{2}recommended_count:\s*([0-9]+)\s*$", block, flags=re.MULTILINE)
    if recommended_count_match:
        recommended_count = int(recommended_count_match.group(1))
        if len(png_assets) < recommended_count:
            errors.append(
                "01-design.yaml: generated PNG count "
                f"{len(png_assets)} is below recommended_count {recommended_count}"
            )
    for item in png_assets:
        path = root / item
        normalized = item.replace("\\", "/").lower()
        if "contact-sheet" in normalized:
            errors.append(f"01-design.yaml: contact sheet must not be listed as generated prototype PNG: {item}")
        if "visual-system" in normalized:
            errors.append(f"01-design.yaml: generated asset appears to be a visual-board screenshot, not a prototype PNG: {item}")
        if "/rejected/" in normalized:
            errors.append(f"01-design.yaml: rejected PNG must not be listed as generated asset: {item}")
        if not path.exists():
            errors.append(f"01-design.yaml: generated PNG does not exist: {item}")
        elif not path.is_file():
            errors.append(f"01-design.yaml: generated PNG is not a file: {item}")
        elif png_dimensions(path) is None:
            errors.append(f"01-design.yaml: generated asset is not a valid PNG file: {item}")

    report_match = re.search(
        r"^\s{2}validation_reports:\s*\n((?:^\s{2,4}-\s+.+\n?)+)",
        block,
        flags=re.MULTILINE,
    )
    if not report_match:
        errors.append("01-design.yaml: required prototype images need validation_reports")
    else:
        reports = []
        for line in report_match.group(1).splitlines():
            item = re.sub(r"^\s*-\s*", "", line).strip().strip('"').strip("'")
            if item:
                reports.append(item)
        if len(reports) < len(png_assets):
            errors.append("01-design.yaml: validation_reports should cover each generated prototype PNG")
        for item in reports:
            path = root / item
            normalized = item.replace("\\", "/").lower()
            if "contact-sheet" in normalized:
                errors.append(f"01-design.yaml: contact sheet report must not validate generated prototype PNGs: {item}")
            if not path.exists():
                errors.append(f"01-design.yaml: validation report does not exist: {item}")
            elif not path.is_file():
                errors.append(f"01-design.yaml: validation report is not a file: {item}")
            else:
                errors.extend(validate_prototype_report(path, png_assets))

    errors.extend(validate_system_flow(root, text))
    return errors


def validate_prototype_report(path: Path, png_assets: list[str]) -> list[str]:
    errors: list[str] = []
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"01-design.yaml: validation report is not valid JSON: {path.relative_to(path.parents[2])}: {exc}"]

    rel = str(path.relative_to(path.parents[1])).replace("\\", "/")
    if report.get("status") != "ok":
        errors.append(f"01-design.yaml: prototype report is not ok: {rel}")
    if report.get("mode") != "responses-image-tool":
        errors.append(f"01-design.yaml: prototype report did not use responses-image-tool: {rel}")
    if report.get("response_mode") != "responses_image_tool":
        errors.append(f"01-design.yaml: prototype report missing responses_image_tool response_mode: {rel}")
    if report.get("model") != "gpt-image-2":
        errors.append(f"01-design.yaml: prototype report did not use gpt-image-2: {rel}")
    if report.get("prompt_includes_size") is not True:
        errors.append(f"01-design.yaml: prototype report prompt does not include target size: {rel}")
    if report.get("prompt_includes_quality") is not True:
        errors.append(f"01-design.yaml: prototype report prompt does not include quality: {rel}")
    if report.get("size") != "1536x1024":
        errors.append(f"01-design.yaml: prototype report requested size should be 1536x1024: {rel}")
    if report.get("quality") != "high":
        errors.append(f"01-design.yaml: prototype report requested quality should be high: {rel}")

    output = str(report.get("output") or "").replace("\\", "/")
    if output and output not in png_assets:
        errors.append(f"01-design.yaml: prototype report output is not listed in generated_assets: {rel} -> {output}")
    if output:
        png_path = path.parents[1] / output
        dims = png_dimensions(png_path) if png_path.exists() else None
        report_dims = report.get("png_dimensions")
        if dims and isinstance(report_dims, list) and len(report_dims) == 2:
            if tuple(report_dims) != dims:
                errors.append(f"01-design.yaml: report dimensions do not match PNG bytes: {rel}")
    return errors


def validate_system_flow(root: Path, text: str) -> list[str]:
    errors: list[str] = []
    block_match = re.search(r"^system_flow_diagram:\s*$", text, flags=re.MULTILINE)
    if not block_match:
        return ["01-design.yaml: missing system_flow_diagram block"]
    next_top = re.search(r"^[a-zA-Z0-9_]+:\s*$", text[block_match.end():], flags=re.MULTILINE)
    block_end = block_match.end() + next_top.start() if next_top else len(text)
    block = text[block_match.start():block_end]

    html_match = re.search(r"^\s{2}html:\s*(.+?)\s*$", block, flags=re.MULTILINE)
    png_match = re.search(r"^\s{2}png:\s*(.+?)\s*$", block, flags=re.MULTILINE)
    if not html_match:
        errors.append("01-design.yaml: system_flow_diagram.html is missing")
    else:
        html_path = root / html_match.group(1).strip().strip('"').strip("'")
        if not html_path.exists():
            errors.append(f"01-design.yaml: system flow HTML does not exist: {html_path.relative_to(root)}")
    if not png_match:
        errors.append("01-design.yaml: system_flow_diagram.png is missing")
    else:
        png_path = root / png_match.group(1).strip().strip('"').strip("'")
        if not png_path.exists():
            errors.append(f"01-design.yaml: system flow PNG does not exist: {png_path.relative_to(root)}")
        elif png_dimensions(png_path) is None:
            errors.append(f"01-design.yaml: system flow asset is not a valid PNG: {png_path.relative_to(root)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an AidevOps generated workspace.")
    parser.add_argument("workspace", help="Path such as docs/<feature-slug>")
    args = parser.parse_args()

    root = Path(args.workspace)
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(f"ok workspace={root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
