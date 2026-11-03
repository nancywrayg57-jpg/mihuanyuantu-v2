"""Minimal Feishu/Lark OpenAPI client for built-in message gateway."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

FEISHU_BASE_URL = "https://open.feishu.cn"
LARK_BASE_URL = "https://open.larksuite.com"


def resolve_feishu_base_url(domain: str | None = None) -> str:
    normalized = str(domain or "feishu").strip().lower()
    if normalized == "lark":
        return LARK_BASE_URL
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized.rstrip("/")
    return FEISHU_BASE_URL


def resolve_feishu_accounts_base_url(domain: str | None = None) -> str:
    normalized = str(domain or "feishu").strip().lower()
    if normalized == "lark":
        return "https://accounts.larksuite.com"
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized.rstrip("/").replace("://open.", "://accounts.", 1)
    return "https://accounts.feishu.cn"


def resolve_feishu_applink_base_url(domain: str | None = None) -> str:
    normalized = str(domain or "feishu").strip().lower()
    if normalized == "lark":
        return "https://applink.larksuite.com"
    return "https://applink.feishu.cn"


def build_feishu_bot_open_url(*, app_id: str, domain: str | None = None) -> str:
    return f"{resolve_feishu_applink_base_url(domain)}/client/bot/open?appId={app_id}"


async def init_feishu_app_registration(*, domain: str | None = None, timeout: float = 10.0) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{resolve_feishu_accounts_base_url(domain)}/oauth/v1/app/registration",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"action": "init"},
        )
        response.raise_for_status()
        return response.json()


async def begin_feishu_app_registration(*, domain: str | None = None, timeout: float = 10.0) -> dict[str, Any]:
    init_data = await init_feishu_app_registration(domain=domain, timeout=timeout)
    supported_auth_methods = init_data.get("supported_auth_methods") or init_data.get("supportedAuthMethods") or []
    if supported_auth_methods and "client_secret" not in supported_auth_methods:
        raise RuntimeError("current Feishu registration endpoint does not support client_secret auth")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{resolve_feishu_accounts_base_url(domain)}/oauth/v1/app/registration",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "action": "begin",
                "archetype": "PersonalAgent",
                "auth_method": "client_secret",
                "request_user_info": "open_id",
            },
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("device_code"):
        raise RuntimeError(f"Feishu app registration device_code missing: {data}")
    return data


async def poll_feishu_app_registration(
    *,
    device_code: str,
    domain: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{resolve_feishu_accounts_base_url(domain)}/oauth/v1/app/registration",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"action": "poll", "device_code": device_code},
        )
        if response.status_code >= 400:
            try:
                return response.json()
            except Exception:
                response.raise_for_status()
        return response.json()


class FeishuClient:
    def __init__(self, *, app_id: str, app_secret: str, domain: str | None = None, timeout: float = 10.0):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = resolve_feishu_base_url(domain)
        self.timeout = timeout

    async def get_tenant_access_token(self) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            response.raise_for_status()
            data = response.json()
        token = data.get("tenant_access_token")
        if not token:
            raise RuntimeError(f"Feishu tenant_access_token missing: {data}")
        return str(token)

    async def request_device_authorization(self, *, scope: str = "offline_access") -> dict[str, Any]:
        normalized_scope = str(scope or "").strip()
        if "offline_access" not in normalized_scope.split():
            normalized_scope = f"{normalized_scope} offline_access".strip()
        basic_auth = base64.b64encode(f"{self.app_id}:{self.app_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{resolve_feishu_accounts_base_url(self.base_url)}/oauth/v1/device_authorization",
                headers={
                    "Authorization": f"Basic {basic_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"client_id": self.app_id, "scope": normalized_scope},
            )
            response.raise_for_status()
            return response.json()

    async def send_text(
        self,
        *,
        open_id: str | None = None,
        receive_id: str | None = None,
        receive_id_type: str = "open_id",
        text: str,
    ) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        target = str(receive_id or open_id or "").strip()
        if not target:
            raise ValueError("Feishu receive_id is required")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/open-apis/im/v1/messages",
                params={"receive_id_type": receive_id_type},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"receive_id": target, "msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)},
            )
            response.raise_for_status()
            return response.json()

    async def add_message_reaction(self, *, message_id: str, emoji_type: str = "Typing") -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        normalized_message_id = str(message_id or "").split(":", 1)[0].strip()
        if not normalized_message_id:
            raise ValueError("Feishu message_id is required")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/open-apis/im/v1/messages/{normalized_message_id}/reactions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"reaction_type": {"emoji_type": str(emoji_type or "Typing").strip() or "Typing"}},
            )
            response.raise_for_status()
            return response.json()

    async def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        normalized_message_id = str(message_id or "").split(":", 1)[0].strip()
        normalized_reaction_id = str(reaction_id or "").strip()
        if not normalized_message_id or not normalized_reaction_id:
            raise ValueError("Feishu message_id and reaction_id are required")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.base_url}/open-apis/im/v1/messages/{normalized_message_id}/reactions/{normalized_reaction_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()
