"""
Shared secret-at-rest helpers for OpenAI-compatible provider settings.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import settings


def _provider_secret_key() -> bytes:
    key_source = settings.PROVIDER_SECRET_KEY or settings.JWT_SECRET_KEY
    key = hashlib.sha256(key_source.encode()).digest()
    return base64.urlsafe_b64encode(key)


def normalize_provider_secret_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def encrypt_provider_secret(value: str) -> str:
    normalized = normalize_provider_secret_text(value)
    if not normalized:
        raise ValueError("provider secret must not be blank")
    return Fernet(_provider_secret_key()).encrypt(normalized.encode()).decode()


def decrypt_provider_secret(value: str) -> str:
    normalized = normalize_provider_secret_text(value)
    if not normalized:
        raise ValueError("provider secret must not be blank")
    return Fernet(_provider_secret_key()).decrypt(normalized.encode()).decode()


def decrypt_provider_secret_or_plain(value: Any) -> str | None:
    normalized = normalize_provider_secret_text(value)
    if not normalized:
        return None
    try:
        return decrypt_provider_secret(normalized)
    except Exception:
        if normalized.startswith("gAAAAA"):
            return None
        return normalized


def mask_provider_secret(value: str | None) -> str | None:
    normalized = normalize_provider_secret_text(value)
    if not normalized:
        return None
    if len(normalized) <= 8:
        return "*" * len(normalized)
    return normalized[:4] + "*" * (len(normalized) - 8) + normalized[-4:]
