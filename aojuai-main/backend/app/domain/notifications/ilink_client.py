"""Minimal Tencent WeChat iLink Bot HTTP client."""

from __future__ import annotations

import base64
import random
import uuid
from typing import Any

import httpx

from app.core.config import settings

ILINK_DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "2.0.0"
ILINK_APP_ID = "bot"


def _client_version() -> str:
    parts = [int(part) for part in CHANNEL_VERSION.split(".")]
    major = parts[0] if len(parts) > 0 else 0
    minor = parts[1] if len(parts) > 1 else 0
    patch = parts[2] if len(parts) > 2 else 0
    return str(((major & 0xFF) << 16) | ((minor & 0xFF) << 8) | (patch & 0xFF))


def _common_headers() -> dict[str, str]:
    return {
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": _client_version(),
    }


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-WECHAT-UIN": base64.b64encode(str(random.randint(100000, 999999999)).encode()).decode(),
        **_common_headers(),
    }
    if token:
        headers["AuthorizationType"] = "ilink_bot_token"
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _base_info() -> dict[str, str]:
    return {"channel_version": CHANNEL_VERSION}


def _default_get_updates_timeout() -> float:
    configured_timeout = float(settings.MESSAGE_GATEWAY_WECHAT_GET_UPDATES_TIMEOUT_SECONDS or 0)
    poll_interval = float(settings.MESSAGE_GATEWAY_POLL_INTERVAL_SECONDS or 0)
    safe_timeout = configured_timeout if configured_timeout > 0 else 12.0
    if poll_interval > 3.0:
        safe_timeout = min(safe_timeout, poll_interval - 2.0)
    return max(5.0, safe_timeout)


def _raise_for_ilink_error(payload: dict[str, Any], *, operation: str) -> None:
    ret = payload.get("ret")
    if ret in (None, 0, "0"):
        return
    message = str(
        payload.get("msg")
        or payload.get("message")
        or payload.get("errmsg")
        or payload.get("error")
        or payload
    )
    raise RuntimeError(f"iLink {operation} failed: ret={ret}, message={message}")


def _is_retryable_sendmessage_context_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "sendmessage failed" not in message:
        return False
    return "ret=-2" in message or "ret': -2" in message or "ret\": -2" in message


class WechatIlinkClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or ILINK_DEFAULT_BASE_URL).rstrip("/")
        self.token = token
        self.timeout = timeout

    async def get_bot_qrcode(self, *, bot_type: int = 3) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{ILINK_DEFAULT_BASE_URL}/ilink/bot/get_bot_qrcode",
                params={"bot_type": bot_type},
                headers=_common_headers(),
            )
            response.raise_for_status()
            payload = response.json()
            _raise_for_ilink_error(payload, operation="get_bot_qrcode")
            return payload

    async def get_qrcode_status(self, *, qrcode: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=max(self.timeout, 38.0)) as client:
            response = await client.get(
                f"{self.base_url}/ilink/bot/get_qrcode_status",
                params={"qrcode": qrcode},
                headers=_common_headers(),
            )
            response.raise_for_status()
            payload = response.json()
            _raise_for_ilink_error(payload, operation="get_qrcode_status")
            return payload

    async def get_updates(self, *, get_updates_buf: str | None = None, timeout: float | None = None) -> dict[str, Any]:
        effective_timeout = float(timeout) if timeout is not None else _default_get_updates_timeout()
        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            response = await client.post(
                f"{self.base_url}/ilink/bot/getupdates",
                json={"get_updates_buf": get_updates_buf or "", "base_info": _base_info()},
                headers=_headers(self.token),
            )
            response.raise_for_status()
            payload = response.json()
            _raise_for_ilink_error(payload, operation="getupdates")
            return payload

    async def get_config(self, *, to_user_id: str, context_token: str | None = None, timeout: float = 5.0) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/ilink/bot/getconfig",
                json={
                    "ilink_user_id": to_user_id,
                    "context_token": context_token or "",
                    "base_info": _base_info(),
                },
                headers=_headers(self.token),
            )
            response.raise_for_status()
            payload = response.json()
            _raise_for_ilink_error(payload, operation="getconfig")
            return payload

    async def send_typing(
        self,
        *,
        to_user_id: str,
        typing_ticket: str,
        status: int = 1,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/ilink/bot/sendtyping",
                json={
                    "ilink_user_id": to_user_id,
                    "typing_ticket": typing_ticket,
                    "status": status,
                    "base_info": _base_info(),
                },
                headers=_headers(self.token),
            )
            response.raise_for_status()
            payload = response.json()
            _raise_for_ilink_error(payload, operation="sendtyping")
            return payload

    async def send_typing_indicator(
        self,
        *,
        to_user_id: str,
        context_token: str | None = None,
        status: int = 1,
    ) -> bool:
        config = await self.get_config(to_user_id=to_user_id, context_token=context_token)
        typing_ticket = str(config.get("typing_ticket") or config.get("typingTicket") or "").strip()
        if not typing_ticket:
            return False
        await self.send_typing(to_user_id=to_user_id, typing_ticket=typing_ticket, status=status)
        return True

    async def send_text(self, *, to_user_id: str, text: str, context_token: str | None = None) -> str:
        client_id = f"aoju-{uuid.uuid4()}"
        payload = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "client_id": client_id,
                "message_type": 2,
                "message_state": 2,
                "context_token": context_token or "",
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            },
            "base_info": _base_info(),
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/ilink/bot/sendmessage",
                    json=payload,
                    headers=_headers(self.token),
                )
                response.raise_for_status()
                response_payload = response.json()
                _raise_for_ilink_error(response_payload, operation="sendmessage")
            except Exception as exc:
                if context_token and _is_retryable_sendmessage_context_error(exc):
                    retry_payload = {
                        "msg": {
                            **payload["msg"],
                            "context_token": "",
                        },
                        "base_info": payload["base_info"],
                    }
                    response = await client.post(
                        f"{self.base_url}/ilink/bot/sendmessage",
                        json=retry_payload,
                        headers=_headers(self.token),
                    )
                    response.raise_for_status()
                    response_payload = response.json()
                    _raise_for_ilink_error(response_payload, operation="sendmessage")
                else:
                    raise
        return client_id
