#!/usr/bin/env python3
"""
AOJUAI Skill Script: init_feature_bundle.py

Create a docs bundle for a new feature/module under:
  docs/dev/features/<slug>/

Defaults to dry-run; use --write to create files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    raise SystemExit("Could not locate repo root (missing .git in parents).")


def _validate_slug(value: str) -> str:
    slug = value.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_\-]*", slug):
        raise ValueError("slug must match /^[a-z][a-z0-9_-]*$/")
    return slug


def _read_template(repo_root: Path, rel: str) -> str:
    return (repo_root / rel).read_text(encoding="utf-8")


def _write(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Initialize AOJUAI feature docs bundle (dry-run by default).")
    parser.add_argument("--slug", required=True, help="feature slug, e.g. agents_points")
    parser.add_argument("--write", action="store_true", help="write files")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    slug = _validate_slug(args.slug)
    target_dir = repo_root / "docs" / "dev" / "features" / slug

    mapping: dict[str, str | None] = {
        "REQUIREMENTS.md": "docs/dev/templates/REQUIREMENTS_TEMPLATE.md",
        "DB_DESIGN.md": "docs/dev/templates/DB_DESIGN_TEMPLATE.md",
        "API_CONTRACT.md": "docs/dev/templates/API_CONTRACT_TEMPLATE.md",
        "TEST_TASKLIST.md": "docs/dev/templates/TEST_TASKLIST_TEMPLATE.md",
        "RELEASE_RUNBOOK.md": "docs/dev/templates/RELEASE_RUNBOOK_TEMPLATE.md",
        "README.md": None,
    }

    if not args.write:
        print("Dry-run. Would create:")
        for filename in mapping:
            print(f"  - {(target_dir / filename).relative_to(repo_root)}")
        return 0

    for filename, template_rel in mapping.items():
        if filename == "README.md":
            content = (
                f"# Feature Bundle: {slug}\n\n"
                "本目录由脚手架生成，用于沉淀该功能的闭环交付物：\n\n"
                "- REQUIREMENTS.md\n"
                "- DB_DESIGN.md\n"
                "- API_CONTRACT.md\n"
                "- TEST_TASKLIST.md\n"
                "- RELEASE_RUNBOOK.md\n"
            )
        else:
            content = _read_template(repo_root, template_rel) if template_rel else ""
        _write(target_dir / filename, content, force=args.force)

    print(f"✓ Initialized {target_dir.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
