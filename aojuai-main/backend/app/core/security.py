"""
AOJU Backend - Security Utilities
"""
import hashlib
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# 公开分享轮询等热路径每次请求都验密；bcrypt 是 ~100-300ms 的纯 CPU 同步调用会阻塞事件循环。
# 仅缓存成功结果（失败不缓存，不会加速爆破），进程内短 TTL。
_VERIFY_CACHE: dict[tuple[str, str], float] = {}
_VERIFY_CACHE_TTL = 300.0
_VERIFY_CACHE_MAX = 2048


def verify_password_cached(plain_password: str, hashed_password: str) -> bool:
    """verify_password with a short-lived success cache for hot polled paths."""
    key = (hashlib.sha256(plain_password.encode("utf-8")).hexdigest(), hashed_password)
    now = time.monotonic()
    expires = _VERIFY_CACHE.get(key)
    if expires is not None and expires > now:
        return True
    ok = verify_password(plain_password, hashed_password)
    if ok:
        if len(_VERIFY_CACHE) >= _VERIFY_CACHE_MAX:
            stale = [k for k, exp in _VERIFY_CACHE.items() if exp <= now]
            for k in stale:
                _VERIFY_CACHE.pop(k, None)
            if len(_VERIFY_CACHE) >= _VERIFY_CACHE_MAX:
                _VERIFY_CACHE.clear()
        _VERIFY_CACHE[key] = now + _VERIFY_CACHE_TTL
    return ok


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    extra_data: dict[str, Any] | None = None,
) -> str:
    """Create JWT access token"""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
    }

    if extra_data:
        to_encode.update(extra_data)

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create JWT refresh token"""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
    }

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise UnauthorizedError(message="Invalid token", details=str(e))


def get_token_expiry(token: str) -> datetime:
    """Get token expiry time"""
    payload = decode_token(token)
    exp = payload.get("exp")
    if exp:
        return datetime.fromtimestamp(exp, tz=UTC)
    raise UnauthorizedError(message="Token has no expiry")


# ==================== 邀请码加密/解密 ====================

import base64
import hmac
import json


def create_invite_code(tenant_code: str, expires_days: int = 30) -> str:
    """
    创建加密邀请码
    格式: base64(json({tenant_code, exp, sig}))
    """
    expire = datetime.now(UTC) + timedelta(days=expires_days)

    # 创建签名
    payload = {
        "t": tenant_code,  # tenant_code
        "e": int(expire.timestamp()),  # expiry timestamp
    }

    # 使用 HMAC 签名
    payload_str = json.dumps(payload, sort_keys=True)
    sig = hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()[:16]  # 取前16位

    payload["s"] = sig

    # Base64 编码 (URL safe)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode().rstrip("=")

    return encoded


def decode_invite_code(invite_code: str) -> str | None:
    """
    解密邀请码，返回租户代码
    如果无效或过期，返回 None
    """
    try:
        # 添加回 padding
        padding = 4 - len(invite_code) % 4
        if padding != 4:
            invite_code += "=" * padding

        # Base64 解码
        decoded = base64.urlsafe_b64decode(invite_code.encode()).decode()
        payload = json.loads(decoded)

        tenant_code = payload.get("t")
        exp = payload.get("e")
        sig = payload.get("s")

        if not all([tenant_code, exp, sig]):
            return None

        # 验证签名
        verify_payload = {"t": tenant_code, "e": exp}
        payload_str = json.dumps(verify_payload, sort_keys=True)
        expected_sig = hmac.new(
            settings.JWT_SECRET_KEY.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()[:16]

        if not hmac.compare_digest(sig, expected_sig):
            return None

        # 检查过期
        if datetime.now(UTC).timestamp() > exp:
            return None

        return tenant_code

    except Exception:
        return None
