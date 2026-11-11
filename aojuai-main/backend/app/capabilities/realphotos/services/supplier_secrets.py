"""Duty-scoped upstream secrets. Never log plaintext. Never commit the store file.

Search order for reads:
1. ``生产物料/realphotos-duty-secrets.json`` (repo-local or sibling)
2. ``.secrets/realphotos-duty-secrets.json`` (gitignored)
3. Legacy material markdown sections / GEMINI_API_KEY for bootstrap fallback
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.capabilities.realphotos.services.supplier_material import read_material_secret
from app.core.config import settings

_STORE_NAME = "realphotos-duty-secrets.json"
_DUTIES = frozenset({"generation", "prompt_opt", "pre_review", "final_detection"})


def secret_store_paths() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[6]
    return [
        repo / "生产物料" / _STORE_NAME,
        repo.parent / "生产物料" / _STORE_NAME,
        repo / ".secrets" / _STORE_NAME,
        Path(str(settings.REALPHOTOS_STORAGE_ROOT or "").strip() or "/tmp") / _STORE_NAME,
    ]


def _load_store() -> dict[str, str]:
    for path in secret_store_paths():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if str(v).strip()}
    return {}


def _write_store(data: dict[str, str]) -> Path:
    # Prefer sibling/repo 生产物料; fall back to .secrets under repo.
    candidates = [
        secret_store_paths()[0],
        secret_store_paths()[1],
        secret_store_paths()[2],
    ]
    target = candidates[2]
    for path in candidates:
        parent = path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            target = path
            break
        except OSError:
            continue
    payload = {k: v for k, v in data.items() if str(v).strip()}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def mask_secret(secret: str) -> str:
    text = str(secret or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return text[:2] + "••••"
    return text[:4] + "••••" + text[-2:]


def read_duty_secret(duty: str) -> str:
    label = str(duty or "").strip()
    if label not in _DUTIES:
        return ""
    store = _load_store()
    if store.get(label):
        return str(store[label]).strip()
    if label == "final_detection":
        env = str(settings.GEMINI_API_KEY or "").strip()
        if env:
            return env
    return read_material_secret(label)


def write_duty_secret(duty: str, secret: str) -> str:
    """Persist plaintext secret; return mask for contract display."""
    label = str(duty or "").strip()
    if label not in _DUTIES:
        raise ValueError(f"unsupported duty for secret: {label}")
    value = str(secret or "").strip()
    if not value:
        raise ValueError("empty secret")
    store = _load_store()
    store[label] = value
    _write_store(store)
    return mask_secret(value)


def clear_duty_secret(duty: str) -> None:
    label = str(duty or "").strip()
    store = _load_store()
    if label in store:
        del store[label]
        _write_store(store)


def has_duty_secret(duty: str) -> bool:
    return bool(read_duty_secret(duty))


def redact_for_log(text: str) -> str:
    cleaned = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "sk-redacted", text or "")
    cleaned = re.sub(r"AIza[A-Za-z0-9_\-]{10,}", "gemini-redacted", cleaned)
    cleaned = re.sub(r"Bearer\s+\S+", "Bearer redacted", cleaned)
    return cleaned[:180]
