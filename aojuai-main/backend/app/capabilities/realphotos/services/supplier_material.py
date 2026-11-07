"""Read supplier secrets from the gitignored material file. Never log the value."""

from __future__ import annotations

import os
import re
from pathlib import Path

_SECTIONS = {
    "generation": "ChatGPT IMAGE 2",
    "prompt_opt": "Deepseek API",
    "pre_review": "阿里百炼大模型",
}


def supplier_live_enabled() -> bool:
    return os.environ.get("REALPHOTOS_SUPPLIER_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}


def material_paths() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[6]
    name = "蜜獾原图v2-生产物料.md"
    return [
        repo / "生产物料" / name,
        repo.parent / "生产物料" / name,
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
