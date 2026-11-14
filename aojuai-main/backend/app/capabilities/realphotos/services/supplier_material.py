"""Read supplier secrets from the gitignored material file. Never log the value."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings

_SECTIONS = {
    "generation": "ChatGPT IMAGE 2",
    "prompt_opt": "Deepseek API",
    "pre_review": "阿里百炼大模型",
    # Material file title is misspelled; keep exact heading match.
    "final_detection": "Gemin Vision API",
}


def supplier_live_enabled() -> bool:
    return str(settings.REALPHOTOS_SUPPLIER_LIVE or "").strip().lower() in {"1", "true", "yes", "on"}


def import_staging_enabled() -> bool:
    """Admin work-order gate for temporary image-host联调. Not ND-012 formal closure."""
    return str(settings.REALPHOTOS_IMPORT_STAGING or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def material_paths() -> list[Path]:
    """Prefer 生产物料 markdown beside this checkout, then sibling primary repo.

    Parallel git worktrees often lack a local ``生产物料/`` copy; keys still live
    under the primary ``mihuanyuantu-v2/生产物料/蜜獾原图v2-生产物料.md``.
    """
    here = Path(__file__).resolve()
    repo = here.parents[6]
    parent = repo.parent
    name = "蜜獾原图v2-生产物料.md"
    return [
        repo / "生产物料" / name,
        parent / "生产物料" / name,
        parent / "mihuanyuantu-v2" / "生产物料" / name,
    ]


def read_material_secret(duty: str) -> str:
    title = _SECTIONS.get(duty)
    if not title:
        return ""
    text = ""
    for path in material_paths():
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            break
    if not text:
        return ""
    pattern = rf"^##\s+{re.escape(title)}\s*$"
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(pattern, line.strip()):
            start = index + 1
            break
    if start is None:
        return ""
    chunk: list[str] = []
    for line in lines[start:]:
        if line.startswith("#"):
            break
        chunk.append(line)
    fenced = re.findall(r"```(?:[^\n]*)\n(.*?)```", "\n".join(chunk), flags=re.S)
    raw = fenced[0] if fenced else "\n".join(chunk)
    secret = ""
    for line in raw.splitlines():
        cleaned = line.strip().strip("`")
        if cleaned:
            secret = cleaned
            break
    return secret
