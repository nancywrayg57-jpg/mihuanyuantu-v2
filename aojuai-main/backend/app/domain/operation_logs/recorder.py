"""
AOJU Backend - Operation Log Helper

Provides a convenience function to persist critical operation logs with:
- multi-tenant isolation
- structured logging via structlog
- sensitive data masking
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.domain.operation_logs.models import OperationLog
from app.domain.operation_logs.service import OperationLogService

logger = get_logger(__name__)


_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "pwd",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "secret",
    "client_secret",
    "cookie",
)


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(fragment in key_lower for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _sanitize_value(value: Any, *, depth: int = 0, max_depth: int = 6) -> Any:
    if depth > max_depth:
        return "***"

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return str(value)

    # Pydantic models / dataclasses-like objects
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _sanitize_value(model_dump(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            return str(value)

    if isinstance(value, Mapping):
        return _sanitize_mapping(value, depth=depth + 1, max_depth=max_depth)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_value(item, depth=depth + 1, max_depth=max_depth) for item in value]

    # Fallback: stringification to ensure JSONB serializable
    return str(value)


def _sanitize_mapping(mapping: Mapping[Any, Any], *, depth: int, max_depth: int) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in mapping.items():
        key_str = str(key)
        if _is_sensitive_key(key_str):
            sanitized[key_str] = "***"
            continue
        sanitized[key_str] = _sanitize_value(value, depth=depth, max_depth=max_depth)
    return sanitized


def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sanitize payload for safe persistence (mask sensitive fields)."""
    if payload is None:
        return None
    return _sanitize_mapping(payload, depth=0, max_depth=6)


async def log_operation(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int | None = None,
    username: str | None = None,
    module: str,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    method: str | None = None,
    path: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    status: str = "success",
    status_code: int | None = None,
    error_message: str | None = None,
    request_data: dict[str, Any] | None = None,
    response_data: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    extra: dict[str, Any] | None = None,
) -> OperationLog:
    """记录操作日志"""

    safe_request_data = sanitize_payload(request_data)
    safe_response_data = sanitize_payload(response_data)
    safe_extra = sanitize_payload(extra) or {}

    data: dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "username": username,
        "module": module,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "method": method,
        "path": path,
        "ip": ip,
        "user_agent": user_agent,
        "status": status,
        "status_code": status_code,
        "error_message": error_message,
        "request_data": safe_request_data,
        "response_data": safe_response_data,
        "duration_ms": duration_ms,
        "extra": safe_extra,
    }

    service = OperationLogService(db)
    try:
        async with db.begin_nested():
            log = await service.create(data)
    except Exception:
        # Never block business flow due to logging failures.
        logger.exception(
            "operation_log_write_failed",
            tenant_id=tenant_id,
            module=module,
            action=action,
            user_id=user_id,
            status=status,
        )
        return OperationLog(**data)  # type: ignore[arg-type]

    logger.info(
        "operation_log_created",
        tenant_id=tenant_id,
        module=module,
        action=action,
        status=status,
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
    )
    return log

