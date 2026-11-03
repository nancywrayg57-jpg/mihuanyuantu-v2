#!/usr/bin/env python3
"""
AOJUAI Skill Script: scaffold_backend_tests.py

Scaffold backend/tests from templates.
Defaults to dry-run; use --write to create files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    raise SystemExit("Could not locate repo root (missing .git in parents).")


def _read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Scaffold backend/tests (dry-run by default).")
    parser.add_argument("--write", action="store_true", help="write files")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    templates_dir = repo_root / "docs" / "dev" / "skills" / "aojuai-backend-testing" / "templates"
    backend_tests_dir = repo_root / "backend" / "tests"

    mapping = {
        templates_dir / "conftest.py": backend_tests_dir / "conftest.py",
        templates_dir / "test_health.py": backend_tests_dir / "test_health.py",
    }

    if not args.write:
        print("Dry-run. Would scaffold:")
        for src, dst in mapping.items():
            print(f"  - {dst.relative_to(repo_root)} (from {src.relative_to(repo_root)})")
        return 0

    for src, dst in mapping.items():
        _write(dst, _read_template(src), force=args.force)
        print(f"✓ Wrote {dst.relative_to(repo_root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
