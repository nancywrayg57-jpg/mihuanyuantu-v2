"""Enterprise WeChat QR onboarding helpers for personal channels."""

from __future__ import annotations

import copy
import platform
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.exceptions import BusinessError

WECOM_QR_GENERATE_BASE_URL = "https://work.weixin.qq.com/ai/qc/generate"
WECOM_QR_QUERY_URL = "https://work.weixin.qq.com/ai/qc/query_result"
WECOM_QR_PAGE_BASE_URL = "https://work.weixin.qq.com/ai/qc/gen?source=wecom-cli&scode="
WECOM_BOT_WS_URL = "wss://openws.work.weixin.qq.com"
WECOM_QR_SOURCE = "wecom-cli"
WECOM_QR_EXPIRE_SECONDS = 300

_SECRET_KEYS = {"secret", "bot_secret", "botSecret"}


def _platform_code() -> int:
    system = platform.system().lower()
    if system == "darwin":
        return 1
    if system == "windows":
        return 2
    if system == "linux":
        return 3
    return 0


def build_wecom_qr_page_url(scode: str) -> str:
    return f"{WECOM_QR_PAGE_BASE_URL}{scode}"


def _redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "***" if str(key) in _SECRET_KEYS else _redact_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def parse_wecom_qr_start(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    scode = str(data.get("scode") or "").strip()
    auth_url = str(data.get("auth_url") or data.get("authUrl") or "").strip()
    if not scode or not auth_url:
        raise BusinessError(message="企业微信二维码接口未返回 scode/auth_url")
    expires_at = datetime.now(UTC) + timedelta(seconds=WECOM_QR_EXPIRE_SECONDS)
    return {
        "scode": scode,
        "authUrl": auth_url,
        "qrPageUrl": build_wecom_qr_page_url(scode),
        "qrPayload": auth_url,
        "expiresAt": expires_at.isoformat(),
        "raw": _redact_secrets(copy.deepcopy(payload)),
    }


def parse_wecom_qr_status(scode: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    status = str(data.get("status") or "pending").strip() or "pending"
    bot_info = data.get("bot_info") if isinstance(data.get("bot_info"), dict) else {}
    bot_id = str(bot_info.get("botid") or bot_info.get("botId") or "").strip()
    secret = str(bot_info.get("secret") or "").strip()
    if status == "success" and (not bot_id or not secret):
        raise BusinessError(message="企业微信扫码成功但未返回 Bot ID/Secret")
    return {
        "scode": str(scode or "").strip(),
        "status": status,
        "connected": status == "success",
        "botId": bot_id or None,
        "secret": secret or None,
        "raw": _redact_secrets(copy.deepcopy(payload)),
    }


async def fetch_wecom_qrcode(*, timeout: float = 10.0) -> dict[str, Any]:
    params = {"source": WECOM_QR_SOURCE, "plat": _platform_code()}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(WECOM_QR_GENERATE_BASE_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except BusinessError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(message=f"企业微信二维码获取失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise BusinessError(message="企业微信二维码接口返回格式异常")
    return parse_wecom_qr_start(payload)


async def query_wecom_qrcode_status(scode: str, *, timeout: float = 10.0) -> dict[str, Any]:
    normalized_scode = str(scode or "").strip()
    if not normalized_scode:
        raise BusinessError(message="企业微信二维码 scode 不能为空")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(WECOM_QR_QUERY_URL, params={"scode": normalized_scode})
            response.raise_for_status()
            payload = response.json()
    except BusinessError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(message=f"企业微信扫码状态查询失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise BusinessError(message="企业微信扫码状态接口返回格式异常")
    return parse_wecom_qr_status(normalized_scode, payload)
