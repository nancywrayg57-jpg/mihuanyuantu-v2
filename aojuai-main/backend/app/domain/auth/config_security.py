"""
AOJU Backend - Tenant Config Security Helpers

Keeps tenant-scoped config secrets out of response payloads while preserving
stored values in the DB.
"""

from __future__ import annotations

from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _looks_like_removed_knowledge_base_config(value: Any) -> bool:
    source = _as_dict(value)
    if not source:
        return False
    return any(key in source for key in ("provider", "apiUrl", "api_url", "apiKey", "api_key"))


def _sanitize_smtp_configs(value: Any) -> Any:
    """Deep-copy config while replacing every SMTP password with one boolean."""
    if isinstance(value, list):
        return [_sanitize_smtp_configs(child) for child in value]
    if not isinstance(value, dict):
        return value

    sanitized: dict[str, Any] = {}
    for key, child in value.items():
        if key.lower() != "smtp" or not isinstance(child, dict):
            sanitized[key] = _sanitize_smtp_configs(child)
            continue

        secret_keys = {"password", "passwordEncrypted", "password_encrypted"}
        password_set = bool(child.get("passwordSet")) or any(
            bool(child.get(secret_key)) for secret_key in secret_keys
        )
        sanitized_smtp = {
            smtp_key: _sanitize_smtp_configs(smtp_value)
            for smtp_key, smtp_value in child.items()
            if smtp_key not in secret_keys and smtp_key != "passwordSet"
        }
        sanitized_smtp["passwordSet"] = password_set
        sanitized[key] = sanitized_smtp
    return sanitized


def sanitize_tenant_config(raw_config: Any) -> dict[str, Any]:
    config = _as_dict(_sanitize_smtp_configs(raw_config))
    sanitized = {
        key: value
        for key, value in config.items()
        if key not in {"knowledge_base", "knowledgeBase"}
    }

    if _looks_like_removed_knowledge_base_config(sanitized.get("ai")):
        sanitized.pop("ai", None)
    return sanitized
