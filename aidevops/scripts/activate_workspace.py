#!/usr/bin/env python3
"""Activate AidevOps for a workspace by writing a marker and AGENTS.md block."""

from __future__ import annotations

import argparse
from pathlib import Path


VERSION = "v20260701-persistent-activation"
START = "<!-- AIDEVOPS-ACTIVE:START -->"
END = "<!-- AIDEVOPS-ACTIVE:END -->"


def instruction_block(skill_path: str) -> str:
    return f"""{START}
This workspace has AidevOps activated.

For PRD, user story, design, visual prototype, gpt-image-2 image prototype, architecture, sprint, implementation, review, acceptance, deployment, rollback, or beginner vibe-coding work:

1. Read `{skill_path}` before acting, even if the user does not repeat the skill name.
2. Continue from `docs/<feature>/progress.yaml` and the phase files when they exist.
3. Keep Chinese guidance by default for domestic beginner users; keep code/API/env/model identifiers in English.
4. Do not treat this activation as permission to skip clarification, Git checks, protected decisions, or quality gates.

For unrelated small coding questions, answer normally without forcing the full AidevOps workflow.
{END}
"""


def marker_text(skill_path: str) -> str:
    return f"""active: true
skill_path: {skill_path}
version: {VERSION}
activation_scope:
  - PRD
  - user stories
  - design
  - visual prototype
  - gpt-image-2 prototype image
  - architecture
  - sprint
  - implementation loop
  - review
  - acceptance
  - deployment
  - rollback
  - vibe coding
rule: "For relevant product/software delivery work, read {skill_path} before acting even when the user does not repeat the skill name."
"""


def replace_or_append_block(existing: str, block: str) -> str:
    if START in existing and END in existing:
        before = existing.split(START, 1)[0].rstrip()
        after = existing.split(END, 1)[1].lstrip()
        pieces = [piece for piece in (before, block.rstrip(), after.rstrip()) if piece]
        return "\n\n".join(pieces) + "\n"
    if existing.strip():
        return existing.rstrip() + "\n\n" + block
    return "# Agent Instructions\n\n" + block


def main() -> int:
    parser = argparse.ArgumentParser(description="Activate AidevOps project instructions in a workspace.")
    parser.add_argument("--workspace", default=".", help="Target workspace directory.")
    parser.add_argument("--skill-path", default="aidevops/SKILL.md", help="Skill path relative to the workspace.")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise SystemExit(f"workspace does not exist or is not a directory: {workspace}")

    skill_path = args.skill_path.replace("\\", "/")
    marker = workspace / ".aidevops-active.yaml"
    marker.write_text(marker_text(skill_path), encoding="utf-8")

    agents = workspace / "AGENTS.md"
    existing = agents.read_text(encoding="utf-8") if agents.exists() else ""
    agents.write_text(replace_or_append_block(existing, instruction_block(skill_path)), encoding="utf-8")

    print(f"activated workspace={workspace}")
    print(f"marker={marker}")
    print(f"instructions={agents}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
