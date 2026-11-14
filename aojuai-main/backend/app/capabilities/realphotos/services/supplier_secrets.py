"""Duty-scoped upstream secrets. Never log plaintext. Never commit the store file.

Search order for reads:
1. ``生产物料/realphotos-duty-secrets.json`` (repo-local or sibling)
2. ``.secrets/realphotos-duty-secrets.json`` (gitignored)
3. Legacy material markdown sections / GEMINI_API_KEY for bootstrap fallback

Store shape (backward compatible):
- Flat ``duty → string`` is one enabled credential (legacy).
- ``duty → list[{id, secret, provider, modelId, baseUrl, enabled, createdAt}]``
  holds coexisting keys. Registering appends. At most one entry per duty is enabled.
  No weight-based rotation.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.capabilities.realphotos.services.supplier_material import read_material_secret
from app.core.config import settings

_STORE_NAME = "realphotos-duty-secrets.json"
_DUTIES = frozenset({"generation", "prompt_opt", "pre_review", "final_detection"})


def secret_store_paths() -> list[Path]:
    """Prefer 生产物料 over sparse worktree ``.secrets`` so parallel checkouts still see duty keys."""
    here = Path(__file__).resolve()
    repo = here.parents[6]
    parent = repo.parent
    return [
        repo / "生产物料" / _STORE_NAME,
        parent / "生产物料" / _STORE_NAME,
        # Primary checkout when this process runs from a sibling git worktree.
        parent / "mihuanyuantu-v2" / "生产物料" / _STORE_NAME,
        repo / ".secrets" / _STORE_NAME,
        Path(str(settings.REALPHOTOS_STORAGE_ROOT or "").strip() or "/tmp") / _STORE_NAME,
    ]


def _active_store_path() -> Path | None:
    for path in secret_store_paths():
        if path.is_file():
            return path
    return None


def _load_store() -> dict[str, Any]:
    path = _active_store_path()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return dict(data)


def _write_store(data: dict[str, Any]) -> Path:
    existing = _active_store_path()
    if existing is not None:
        target = existing
    else:
        candidates = secret_store_paths()[:3]
        target = candidates[-1]
        for path in candidates:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                target = path
                break
            except OSError:
                continue
    payload: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            if value.strip():
                payload[str(key)] = value
            continue
        if isinstance(value, list):
            if value:
                payload[str(key)] = value
            continue
        if value is not None:
            payload[str(key)] = value
    target.parent.mkdir(parents=True, exist_ok=True)
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


def _new_id() -> str:
    return "c" + uuid.uuid4().hex[:12]


def _entry_from_secret(secret: str, *, enabled: bool = True) -> dict[str, Any]:
    return {
        "id": "legacy",
        "secret": str(secret).strip(),
        "provider": "",
        "modelId": "",
        "baseUrl": "",
        "enabled": bool(enabled),
        "createdAt": "",
    }


def _normalize_entry(raw: Any, *, fallback_enabled: bool) -> dict[str, Any] | None:
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return _entry_from_secret(text, enabled=fallback_enabled)
    if not isinstance(raw, dict):
        return None
    secret = str(raw.get("secret") or "").strip()
    if not secret:
        return None
    entry_id = str(raw.get("id") or "").strip() or _new_id()
    return {
        "id": entry_id,
        "secret": secret,
        "provider": str(raw.get("provider") or "").strip(),
        "modelId": str(raw.get("modelId") or raw.get("model_id") or "").strip(),
        "baseUrl": str(raw.get("baseUrl") or raw.get("base_url") or "").strip(),
        "enabled": bool(raw.get("enabled", fallback_enabled)),
        "createdAt": str(raw.get("createdAt") or ""),
    }


def entries_for_duty(store: dict[str, Any], duty: str) -> list[dict[str, Any]] | None:
    """Return credential entries, or None when the duty is absent (caller may fall back)."""
    if duty not in store:
        return None
    raw = store.get(duty)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        return [_entry_from_secret(text, enabled=True)]
    if isinstance(raw, list):
        entries: list[dict[str, Any]] = []
        for item in raw:
            normalized = _normalize_entry(item, fallback_enabled=False)
            if normalized is not None:
                entries.append(normalized)
        return entries
    return []


def _public_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id") or ""),
        "masked": mask_secret(str(entry.get("secret") or "")),
        "provider": str(entry.get("provider") or ""),
        "modelId": str(entry.get("modelId") or ""),
        "baseUrl": str(entry.get("baseUrl") or ""),
        "enabled": bool(entry.get("enabled")),
        "createdAt": str(entry.get("createdAt") or ""),
    }


def _persist_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id") or ""),
        "secret": str(entry.get("secret") or ""),
        "provider": str(entry.get("provider") or ""),
        "modelId": str(entry.get("modelId") or ""),
        "baseUrl": str(entry.get("baseUrl") or ""),
        "enabled": bool(entry.get("enabled")),
        "createdAt": str(entry.get("createdAt") or ""),
    }


def list_duty_credentials(duty: str) -> list[dict[str, Any]]:
    label = str(duty or "").strip()
    if label not in _DUTIES:
        return []
    entries = entries_for_duty(_load_store(), label)
    if not entries:
        return []
    return [_public_entry(item) for item in entries]


def _enabled_entry(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for item in entries:
        if item.get("enabled") and str(item.get("secret") or "").strip():
            chosen = item
    return chosen


def read_duty_secret(duty: str) -> str:
    """Return the single enabled secret. Absent store falls back to material/env.

    A present duty with no enabled entry does not fall through to another key.
    """
    label = str(duty or "").strip()
    if label not in _DUTIES:
        return ""
    entries = entries_for_duty(_load_store(), label)
    if entries is not None:
        chosen = _enabled_entry(entries)
        return str(chosen.get("secret") or "").strip() if chosen else ""
    if label == "final_detection":
        env = str(settings.GEMINI_API_KEY or "").strip()
        if env:
            return env
    return read_material_secret(label)


def append_duty_credential(
    duty: str,
    secret: str,
    *,
    provider: str = "",
    model_id: str = "",
    base_url: str = "",
    enabled: bool = True,
) -> dict[str, Any]:
    """Append a credential. Does not overwrite existing entries.

    When ``enabled`` is true, every other entry for the duty is disabled.
    Returns a masked public view (no plaintext).
    """
    label = str(duty or "").strip()
    if label not in _DUTIES:
        raise ValueError(f"unsupported duty for secret: {label}")
    value = str(secret or "").strip()
    if not value:
        raise ValueError("empty secret")
    store = _load_store()
    entries = entries_for_duty(store, label) or []
    want_enabled = bool(enabled)
    if want_enabled:
        for item in entries:
            item["enabled"] = False
    created = {
        "id": _new_id(),
        "secret": value,
        "provider": str(provider or "").strip(),
        "modelId": str(model_id or "").strip(),
        "baseUrl": str(base_url or "").strip(),
        "enabled": want_enabled,
        "createdAt": datetime.now(UTC).isoformat(),
    }
    entries.append(created)
    store[label] = [_persist_entry(item) for item in entries]
    _write_store(store)
    return _public_entry(created)


def write_duty_secret(duty: str, secret: str) -> str:
    """Append and enable a secret. Legacy callers still receive the mask.

    Existing entries for the duty are kept and disabled. Flat ``duty → string``
    files are upgraded to a list on write.
    """
    public = append_duty_credential(duty, secret, enabled=True)
    return str(public.get("masked") or "")


def set_credential_enabled(duty: str, credential_id: str, enabled: bool) -> dict[str, Any]:
    """Enable or disable one entry. Enabling disables the duty's other entries."""
    label = str(duty or "").strip()
    if label not in _DUTIES:
        raise ValueError(f"unsupported duty for secret: {label}")
    target_id = str(credential_id or "").strip()
    if not target_id:
        raise ValueError("missing credential id")
    store = _load_store()
    entries = entries_for_duty(store, label)
    if not entries:
        raise ValueError("credential not found")
    found: dict[str, Any] | None = None
    for item in entries:
        if str(item.get("id") or "") == target_id:
            found = item
            break
    if found is None:
        raise ValueError("credential not found")
    if enabled:
        for item in entries:
            item["enabled"] = str(item.get("id") or "") == target_id
    else:
        found["enabled"] = False
    store[label] = [_persist_entry(item) for item in entries]
    _write_store(store)
    return _public_entry(found)


def sync_enabled_credential_meta(
    duty: str,
    *,
    provider: str,
    model_id: str,
    base_url: str,
) -> None:
    """Copy contract fields onto the enabled entry so a later re-enable stays aligned."""
    label = str(duty or "").strip()
    if label not in _DUTIES:
        return
    store = _load_store()
    entries = entries_for_duty(store, label)
    if not entries:
        return
    changed = False
    for item in entries:
        if not item.get("enabled"):
            continue
        item["provider"] = str(provider or "").strip()
        item["modelId"] = str(model_id or "").strip()
        item["baseUrl"] = str(base_url or "").strip()
        changed = True
    if not changed:
        return
    store[label] = [_persist_entry(item) for item in entries]
    _write_store(store)


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
