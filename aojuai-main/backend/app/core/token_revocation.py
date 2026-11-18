"""SEC-A03：JWT 登出/轮换吊销（进程内 + Redis runtime_cache）。"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from app.core.security import decode_token
from app.infrastructure.cache.runtime_cache import get_json, set_json

_REVOKED_PREFIX = "auth:revoked:jti:"


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _ttl_from_payload(payload: dict[str, Any]) -> int:
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return 0
    remaining = int(exp) - int(datetime.now(UTC).timestamp())
    return max(0, remaining)


async def revoke_token(token: str | None) -> None:
    raw = str(token or "").strip()
    if not raw:
        return
    try:
        payload = decode_token(raw)
    except Exception:
        return
    ttl = _ttl_from_payload(payload)
    if ttl <= 0:
        return
    jti = str(payload.get("jti") or "").strip() or token_fingerprint(raw)
    await set_json(f"{_REVOKED_PREFIX}{jti}", {"revoked": True}, ttl_seconds=ttl)


async def is_token_revoked(token: str | None = None, *, payload: dict[str, Any] | None = None) -> bool:
    data = payload
    raw = str(token or "").strip()
    if data is None:
        if not raw:
            return False
        try:
            data = decode_token(raw)
        except Exception:
            return False
    jti = str(data.get("jti") or "").strip()
    if not jti and raw:
        jti = token_fingerprint(raw)
    if not jti:
        return False
    cached = await get_json(f"{_REVOKED_PREFIX}{jti}")
    return bool(cached)
