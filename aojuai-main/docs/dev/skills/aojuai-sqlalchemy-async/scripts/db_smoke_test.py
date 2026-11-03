#!/usr/bin/env python3
"""
AOJUAI Skill Script: db_smoke_test.py

Read-only database connectivity smoke test:
  - loads backend/.env (simple parser)
  - imports backend app settings
  - runs: SELECT 1
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import text


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    raise SystemExit("Could not locate repo root (missing .git in parents).")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


async def _run() -> None:
    repo_root = _repo_root()
    backend_dir = repo_root / "backend"
    _load_env_file(backend_dir / ".env")

    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.infrastructure.database import get_db_context  # noqa: PLC0415

    async with get_db_context() as db:
        result = await db.execute(text("SELECT 1"))
        value = result.scalar()
        print(f"✓ DB OK, SELECT 1 -> {value}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
