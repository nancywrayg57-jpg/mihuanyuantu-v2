"""System message gateway account service and polling runtime."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AOJUException, BusinessError, FeatureDisabledError, ForbiddenError, UnauthorizedError
from app.core.logger import get_logger
from app.core.provider_secrets import decrypt_provider_secret_or_plain, encrypt_provider_secret, mask_provider_secret
from app.domain.auth.models import Tenant
from app.domain.notifications.feishu_client import FeishuClient, poll_feishu_app_registration
from app.domain.notifications.gateway_models import MessageGatewayAccount, MessageGatewayInboundNonce
from app.domain.notifications.ilink_client import ILINK_DEFAULT_BASE_URL, WechatIlinkClient
from app.domain.notifications.message_channels import UserMessageChannelService, select_unambiguous_inbound_channel
from app.domain.notifications.models import UserMessageChannel
from app.domain.users.models import User
from app.infrastructure.database.portable_sql import dialect_insert, escalate_to_write_lock
from app.infrastructure.database.session import get_db_context
from app.infrastructure.repository import RepositoryBase

logger = get_logger(__name__)


def _normalize_site_brand(value: Any = None) -> str:
    return str(value or "").strip() or "平台"


async def _resolve_tenant_site_brand(db: AsyncSession, tenant_id: int | None) -> str:
    normalized_tenant_id = _safe_int(tenant_id)
    if normalized_tenant_id <= 0:
        return _normalize_site_brand()
    try:
        result = await db.execute(
            select(Tenant).where(
                Tenant.id == normalized_tenant_id,
                Tenant.deleted_at.is_(None),
            )
        )
        tenant = result.scalar_one_or_none()
    except Exception:
        return _normalize_site_brand()
    config = dict(getattr(tenant, "config", {}) or {}) if tenant else {}
    seo = config.get("seo") if isinstance(config.get("seo"), dict) else {}
    return _normalize_site_brand((seo or {}).get("title") or getattr(tenant, "name", None))


async def _resolve_user_site_brand(db: AsyncSession, user_id: int | None) -> str:
    normalized_user_id = _safe_int(user_id)
    if normalized_user_id <= 0:
        return _normalize_site_brand()
    try:
        result = await db.execute(
            select(User.tenant_id).where(
                User.id == normalized_user_id,
                User.deleted_at.is_(None),
            )
        )
        tenant_id = _safe_int(result.scalar_one_or_none())
    except Exception:
        return _normalize_site_brand()
    return await _resolve_tenant_site_brand(db, tenant_id)


async def _resolve_channel_site_brand(db: AsyncSession, channel: UserMessageChannel | None) -> str:
    return await _resolve_user_site_brand(db, getattr(channel, "user_id", None))


def _channel_bind_prompt_text(site_brand: Any = None) -> str:
    brand = _normalize_site_brand(site_brand)
    return f"{brand} Channel 已连接。\n请回到 {brand} 个人设置页面，将页面显示的八位关联码发送到这里。"


def _channel_bound_reply(channel_label: str, site_brand: Any = None) -> str:
    brand = _normalize_site_brand(site_brand)
    return f"{brand} 账号已完成{channel_label} Channel 绑定。后续消息将由 AI 助手接管。"


def _channel_invalid_bind_reply(channel_label: str, site_brand: Any = None) -> str:
    brand = _normalize_site_brand(site_brand)
    return f"关联码无效或已过期，请在 {brand} 个人设置中重新获取{channel_label}二维码。"


def _channel_assistant_disabled_reply(site_brand: Any = None) -> str:
    brand = _normalize_site_brand(site_brand)
    return f"{brand} Channel 已连接，我已收到你的消息。\n当前 AI 助手能力尚未启用，请联系管理员启用后再使用。"


def _channel_assistant_error_reply(exc: Exception, site_brand: Any = None) -> str:
    brand = _normalize_site_brand(site_brand)
    prefix = f"{brand} Channel 已连接，我已收到你的消息。\n"
    code = str(getattr(exc, "code", "") or "").strip().upper()
    if isinstance(exc, FeatureDisabledError) or code == "FEATURE_DISABLED":
        return prefix + "当前 AI 助手能力尚未启用，请联系管理员启用后再使用。"
    if code == "INSUFFICIENT_CREDITS":
        return prefix + "AI 助手暂时无法处理：当前账号积分不足，请充值或联系管理员调整额度。"
    if isinstance(exc, ForbiddenError) or code in {"FORBIDDEN", "PERMISSION_DENIED"}:
        return prefix + "AI 助手暂时无法处理：当前账号没有执行该能力的权限。"
    if isinstance(exc, UnauthorizedError) or code in {"UNAUTHORIZED", "AUTH_REQUIRED"}:
        return prefix + "AI 助手暂时无法处理：账号登录或 Channel 绑定状态已失效，请重新登录或重新绑定。"
    if isinstance(exc, AOJUException) and code:
        return prefix + f"AI 助手暂时无法处理：{getattr(exc, 'message', '') or '业务状态异常'}。"
    return prefix + "AI 助手暂时不可用，请稍后重试；如果持续出现，请联系管理员查看后端日志。"


MESSAGE_CHANNEL_ASSISTANT_ROUTE = "/message-channel"
_MESSAGE_CHANNEL_RECENT_CONTEXT_KEY = "recentInboundContextTokens"
_MESSAGE_CHANNEL_PENDING_INBOUND_KEY = "pendingInboundMessages"
_MESSAGE_CHANNEL_PENDING_INBOUND_LIMIT = 8
_MESSAGE_CHANNEL_ACTIVE_CHANNEL_IDS: set[int] = set()
_MESSAGE_CHANNEL_RETRY_DEDUPE_KEY = "retryInboundDedupeToken"
_MESSAGE_CHANNEL_RETRY_REASON_KEY = "retryInboundReason"
_WECHAT_TYPING_WATCHDOG_SECONDS = 20.0
_WECHAT_TYPING_FINAL_RENEW_AFTER_SECONDS = 2.5
_MESSAGE_CHANNEL_PENDING_AUTO_MERGE_MAX_MESSAGES = 3
_MESSAGE_CHANNEL_PENDING_AUTO_MERGE_MAX_CHARS = 600
_GATEWAY_SIGNATURE_VERSION = "aoju-gateway-v1"
_GATEWAY_NONCE_PATTERN = re.compile(r"[A-Za-z0-9._~-]{16,128}")


@dataclass(frozen=True)
class InboundGatewayAuthContext:
    """Authentication result passed to background handlers without any secret."""

    gateway_account_id: int | None
    signed: bool


def build_gateway_inbound_signature(
    *,
    secret: str,
    channel_type: str,
    account_id: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    """Build the v1 HMAC over routing fields and the exact HTTP request body."""
    canonical = b"\n".join(
        (
            _GATEWAY_SIGNATURE_VERSION.encode(),
            str(channel_type).encode(),
            str(account_id).encode(),
            str(timestamp).encode(),
            str(nonce).encode(),
            body,
        )
    )
    return hmac.new(str(secret).encode(), canonical, hashlib.sha256).hexdigest()


async def authenticate_inbound_gateway_request(
    db: AsyncSession,
    *,
    channel_type: str,
    account_id: str | None,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
    body: bytes,
    allow_unsigned: bool | None = None,
    now: datetime | None = None,
) -> InboundGatewayAuthContext:
    """Fail-closed HMAC authentication plus a database-backed nonce guard."""
    normalized_account_id = str(account_id or "").strip()
    normalized_timestamp = str(timestamp or "").strip()
    normalized_nonce = str(nonce or "").strip()
    normalized_signature = str(signature or "").strip().lower()
    supplied = (
        bool(normalized_account_id),
        bool(normalized_timestamp),
        bool(normalized_nonce),
        bool(normalized_signature),
    )
    unsigned_allowed = (
        settings.MESSAGE_GATEWAY_ALLOW_UNSIGNED_INBOUND
        if allow_unsigned is None
        else bool(allow_unsigned)
    )

    if not any(supplied):
        if unsigned_allowed:
            logger.critical(
                "message_gateway_unsigned_inbound_accepted",
                security_event="gateway_authentication_bypass",
                auth_result="transition_unsigned_accepted",
                migration_mode=True,
                channel_type=channel_type,
                action_required="upgrade_gateway_runtime_and_disable_transition",
            )
            return InboundGatewayAuthContext(gateway_account_id=None, signed=False)
        logger.warning(
            "message_gateway_inbound_auth_rejected",
            security_event="gateway_authentication_failed",
            auth_result="rejected",
            reason="unsigned_request",
            channel_type=channel_type,
        )
        raise UnauthorizedError(message="消息网关请求鉴权失败")

    # The transition is deliberately not a general bypass: partially populated
    # auth headers always indicate a broken or downgraded signer and are denied.
    if not all(supplied):
        logger.warning(
            "message_gateway_inbound_auth_rejected",
            security_event="gateway_authentication_failed",
            auth_result="rejected",
            reason="incomplete_auth_headers",
            channel_type=channel_type,
        )
        raise UnauthorizedError(message="消息网关请求鉴权失败")

    if len(normalized_account_id) > 200 or "\n" in normalized_account_id or "\r" in normalized_account_id:
        raise UnauthorizedError(message="消息网关请求鉴权失败")
    if not _GATEWAY_NONCE_PATTERN.fullmatch(normalized_nonce):
        raise UnauthorizedError(message="消息网关请求鉴权失败")
    try:
        request_timestamp = int(normalized_timestamp)
    except ValueError as exc:
        raise UnauthorizedError(message="消息网关请求鉴权失败") from exc

    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    ttl_seconds = max(30, min(int(settings.MESSAGE_GATEWAY_SIGNATURE_TTL_SECONDS or 300), 900))
    if abs(int(current_time.timestamp()) - request_timestamp) > ttl_seconds:
        logger.warning(
            "message_gateway_inbound_auth_rejected",
            security_event="gateway_authentication_failed",
            auth_result="rejected",
            reason="timestamp_outside_window",
            channel_type=channel_type,
        )
        raise UnauthorizedError(message="消息网关请求鉴权失败")

    service = MessageGatewayAccountService(db)
    account = await service.get_active_by_account_id(channel_type, normalized_account_id)
    try:
        secret = decrypt_provider_secret_or_plain(account.token_encrypted) if account else ""
    except Exception:  # A corrupt encrypted value is an auth failure, never a 500 with details.
        secret = ""
    if not account or not secret:
        logger.warning(
            "message_gateway_inbound_auth_rejected",
            security_event="gateway_authentication_failed",
            auth_result="rejected",
            reason="account_or_secret_unavailable",
            channel_type=channel_type,
        )
        raise UnauthorizedError(message="消息网关请求鉴权失败")

    expected_signature = build_gateway_inbound_signature(
        secret=secret,
        channel_type=channel_type,
        account_id=normalized_account_id,
        timestamp=normalized_timestamp,
        nonce=normalized_nonce,
        body=body,
    )
    if not hmac.compare_digest(expected_signature, normalized_signature):
        logger.warning(
            "message_gateway_inbound_auth_rejected",
            security_event="gateway_authentication_failed",
            auth_result="rejected",
            reason="signature_mismatch",
            channel_type=channel_type,
            gateway_account_id=account.id,
        )
        raise UnauthorizedError(message="消息网关请求鉴权失败")

    expires_at = current_time + timedelta(seconds=ttl_seconds)
    nonce_digest = hashlib.sha256(normalized_nonce.encode()).hexdigest()
    await db.execute(delete(MessageGatewayInboundNonce).where(MessageGatewayInboundNonce.expires_at <= current_time))
    nonce_insert = (
        dialect_insert(MessageGatewayInboundNonce)
        .values(
            gateway_account_id=account.id,
            nonce_digest=nonce_digest,
            expires_at=expires_at,
        )
        .on_conflict_do_nothing(
            index_elements=[
                MessageGatewayInboundNonce.gateway_account_id,
                MessageGatewayInboundNonce.nonce_digest,
            ],
            index_where=MessageGatewayInboundNonce.deleted_at.is_(None),
        )
        .returning(MessageGatewayInboundNonce.id)
    )
    inserted = (await db.execute(nonce_insert)).scalar_one_or_none()
    if inserted is None:
        logger.warning(
            "message_gateway_inbound_auth_rejected",
            security_event="gateway_replay_detected",
            auth_result="rejected",
            reason="nonce_reused",
            channel_type=channel_type,
            gateway_account_id=account.id,
        )
        raise UnauthorizedError(message="消息网关请求鉴权失败")

    return InboundGatewayAuthContext(gateway_account_id=account.id, signed=True)


def _inbound_message_dedupe_token(
    *,
    channel_type: str,
    raw_payload: dict[str, Any] | None,
    context_token: str | None,
) -> str | None:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    normalized_channel_type = str(channel_type or "").strip().lower()
    if normalized_channel_type == "wechat":
        for key in ("message_id", "client_id"):
            value = str(payload.get(key) or "").strip()
            if value:
                return f"wechat:{key}:{value}"
        item_list = payload.get("item_list")
        if isinstance(item_list, list) and item_list:
            first_item = item_list[0] if isinstance(item_list[0], dict) else {}
            item_time = str(first_item.get("create_time_ms") or "").strip()
            item_text = extract_text_from_ilink_message(payload)
            from_user_id = str(payload.get("from_user_id") or "").strip()
            if from_user_id and item_time and item_text:
                return f"wechat:item:{from_user_id}:{item_time}:{item_text[:80]}"
    if normalized_channel_type == "feishu":
        for key in ("message_id", "open_message_id"):
            value = str(payload.get(key) or "").strip()
            if value:
                return f"feishu:{key}:{value}"
        header = payload.get("header")
        if isinstance(header, dict):
            value = str(header.get("event_id") or "").strip()
            if value:
                return f"feishu:event:{value}"
    if normalized_channel_type == "wecom":
        body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
        for key in ("message_id", "msgid", "msg_id", "open_message_id"):
            value = str(payload.get(key) or body.get(key) or "").strip()
            if value:
                return f"wecom:{key}:{value}"
        headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
        value = str(payload.get("event_id") or payload.get("eventId") or headers.get("req_id") or "").strip()
        if value:
            return f"wecom:event:{value}"
    normalized_context = str(context_token or "").strip()
    return normalized_context or None


def _is_duplicate_inbound_context(channel: UserMessageChannel, context_token: str | None) -> bool:
    normalized = str(context_token or "").strip()
    if not normalized:
        return False
    extra = channel.extra if isinstance(channel.extra, dict) else {}
    if str(extra.get(_MESSAGE_CHANNEL_RETRY_DEDUPE_KEY) or "").strip() == normalized:
        return False
    if normalized == str(channel.context_token or "").strip():
        return True
    recent_tokens = extra.get(_MESSAGE_CHANNEL_RECENT_CONTEXT_KEY)
    if not isinstance(recent_tokens, list):
        return False
    return normalized in {str(item or "").strip() for item in recent_tokens}


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _trim_channel_text(value: Any, *, limit: int = 1200) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _normalize_channel_control_text(value: Any) -> str:
    return re.sub(r"[\s，。,.!！?？、]+", "", str(value or "").strip().lower())


def _resolve_channel_control_command(value: Any) -> str | None:
    normalized = _normalize_channel_control_text(value)
    if not normalized:
        return None
    new_session_commands = {
        "新对话",
        "开始新对话",
        "重新开始",
        "重开对话",
        "新会话",
        "开启新会话",
    }
    clear_commands = {
        "清空上下文",
        "清除上下文",
        "清空会话",
        "清除会话",
        "忘记刚才",
        "忘记前面",
    }
    cancel_commands = {
        "取消",
        "取消操作",
        "取消当前操作",
        "不做了",
        "不新建了",
        "先不做了",
    }
    if normalized in new_session_commands:
        return "new_session"
    if normalized in clear_commands:
        return "clear_session"
    if normalized in cancel_commands:
        return "cancel_pending"
    return None


class _WechatTypingRuntime:
    def __init__(
        self,
        client: WechatIlinkClient,
        *,
        to_user_id: str,
        context_token: str | None,
    ) -> None:
        self.client = client
        self.to_user_id = to_user_id
        self.context_token = context_token
        self.started = False
        self.started_at = 0.0
        self.last_signal_at = 0.0
        self.watchdog: asyncio.Task[None] | None = None

    async def signal(self) -> bool:
        if not str(self.to_user_id or "").strip():
            return False
        await self.client.send_typing_indicator(
            to_user_id=self.to_user_id,
            context_token=self.context_token,
            status=1,
        )
        loop_time = asyncio.get_running_loop().time()
        self.started = True
        if self.started_at <= 0:
            self.started_at = loop_time
        self.last_signal_at = loop_time
        return True

    async def start(self) -> bool:
        ok = await self.signal()
        if not ok:
            return False
        self.watchdog = asyncio.create_task(self._watchdog())
        return True

    async def touch(self, _stage: str | None = None) -> None:
        if not self.started:
            return
        with suppress(Exception):
            await self.signal()

    async def final_signal(self) -> None:
        if not self.started:
            return
        elapsed_since_signal = asyncio.get_running_loop().time() - self.last_signal_at
        if elapsed_since_signal >= _WECHAT_TYPING_FINAL_RENEW_AFTER_SECONDS:
            with suppress(Exception):
                await self.signal()

    async def stop(self) -> bool:
        if self.watchdog:
            self.watchdog.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self.watchdog
        if not self.started or not str(self.to_user_id or "").strip():
            return False
        await self.client.send_typing_indicator(
            to_user_id=self.to_user_id,
            context_token=self.context_token,
            status=2,
        )
        return True

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(_WECHAT_TYPING_WATCHDOG_SECONDS)
            try:
                await self.signal()
            except Exception as exc:
                logger.debug("message_channel_wechat_typing_watchdog_failed", error=str(exc))


def _inbound_message_reference(
    *,
    text: str,
    context_token: str | None,
    dedupe_token: str | None,
    raw_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    return {
        "text": _trim_channel_text(text, limit=900),
        "contextToken": str(context_token or "").strip() or None,
        "dedupeToken": str(dedupe_token or "").strip() or None,
        "messageId": str(payload.get("message_id") or payload.get("open_message_id") or "").strip() or None,
        "clientId": str(payload.get("client_id") or "").strip() or None,
        "receivedAt": datetime.now(UTC).isoformat(),
    }


def _pending_inbound_messages(extra: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(extra, dict):
        return []
    pending = extra.get(_MESSAGE_CHANNEL_PENDING_INBOUND_KEY)
    if not isinstance(pending, list):
        return []
    items: list[dict[str, Any]] = []
    for item in pending:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        items.append(dict(item))
        if len(items) >= _MESSAGE_CHANNEL_PENDING_INBOUND_LIMIT:
            break
    return items


def _append_pending_inbound_message(extra: dict[str, Any] | None, message: dict[str, Any]) -> dict[str, Any]:
    payload = dict(extra or {})
    pending = _pending_inbound_messages(payload)
    dedupe_token = str(message.get("dedupeToken") or "").strip()
    if dedupe_token and any(str(item.get("dedupeToken") or "").strip() == dedupe_token for item in pending):
        return payload
    payload[_MESSAGE_CHANNEL_PENDING_INBOUND_KEY] = [*pending, message][-_MESSAGE_CHANNEL_PENDING_INBOUND_LIMIT:]
    payload["lastPendingInboundAt"] = datetime.now(UTC).isoformat()
    return payload


async def _mark_inbound_retry(
    channel_service: UserMessageChannelService,
    channel: UserMessageChannel,
    *,
    dedupe_token: str | None,
    reason: str,
) -> None:
    normalized_token = str(dedupe_token or "").strip()
    if not normalized_token:
        await channel_service.set_delivery_result(channel, ok=False, error=reason)
        return
    extra = dict(channel.extra or {})
    extra[_MESSAGE_CHANNEL_RETRY_DEDUPE_KEY] = normalized_token
    extra[_MESSAGE_CHANNEL_RETRY_REASON_KEY] = str(reason or "回复发送失败，等待重试").strip()[:500]
    await channel_service.update(channel, {"extra": extra, "last_error": str(reason or "回复发送失败")[:2000]})


async def _drain_pending_inbound_messages(
    db: AsyncSession,
    channel_service: UserMessageChannelService,
    channel_id: int,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(UserMessageChannel).where(
            UserMessageChannel.id == channel_id,
            UserMessageChannel.deleted_at.is_(None),
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        return []
    extra = dict(channel.extra or {})
    pending = _pending_inbound_messages(extra)
    if not pending:
        return []
    extra.pop(_MESSAGE_CHANNEL_PENDING_INBOUND_KEY, None)
    extra.pop("lastPendingInboundAt", None)
    await channel_service.update(channel, {"extra": extra})
    await db.commit()
    return pending


def _build_pending_followup_message(pending_messages: list[dict[str, Any]]) -> str:
    lines = [
        "用户在上一条消息处理期间继续发送了补充内容。请把这些补充与刚才的问题合并理解；"
        "如果需要引用，请使用“补充 1 / 补充 2”的说法，不要暴露内部 Channel 字段。",
    ]
    for index, item in enumerate(pending_messages, start=1):
        lines.append(f"补充 {index}: {_trim_channel_text(item.get('text'), limit=700)}")
    return "\n".join(lines)


def _should_auto_merge_pending_followup(pending_messages: list[dict[str, Any]]) -> bool:
    texts = [str(item.get("text") or "").strip() for item in pending_messages if isinstance(item, dict)]
    texts = [text for text in texts if text]
    if not texts:
        return False
    if len(texts) > _MESSAGE_CHANNEL_PENDING_AUTO_MERGE_MAX_MESSAGES:
        return False
    total_chars = sum(len(text) for text in texts)
    return total_chars <= _MESSAGE_CHANNEL_PENDING_AUTO_MERGE_MAX_CHARS


def _build_deferred_pending_notice(pending_messages: list[dict[str, Any]]) -> str:
    count = len([item for item in pending_messages if isinstance(item, dict) and str(item.get("text") or "").strip()])
    if count <= 0:
        return ""
    lines = [
        f"另外收到 {count} 条补充内容。为避免连续输入造成理解偏差和额外消耗，我没有自动合并重跑；"
        "请先看完本次回复，如仍需处理补充，直接继续说明下一步。"
    ]
    for index, item in enumerate(pending_messages[:3], start=1):
        text = _trim_channel_text(item.get("text"), limit=160)
        if text:
            lines.append(f"补充 {index}: {text}")
    return "\n".join(lines)


def _same_context_value(left: Any, right: Any) -> bool:
    return str(left or "").strip() == str(right or "").strip()


def _message_channel_assistant_session_matches(
    *,
    route_path: Any,
    context_data: Any,
    channel: UserMessageChannel,
    channel_type: str,
    external_user_id: str,
    conversation_id: str | None,
    tenant_id: int,
) -> bool:
    if str(route_path or "").strip() != MESSAGE_CHANNEL_ASSISTANT_ROUTE:
        return False
    if not isinstance(context_data, dict):
        return False
    if str(context_data.get("source") or "").strip() != "message_channel":
        return False
    required_pairs = {
        "channelType": channel_type,
        "channelId": channel.id,
        "externalUserId": external_user_id,
        "boundUserId": channel.user_id,
        "boundTenantId": tenant_id,
    }
    for key, expected in required_pairs.items():
        if not _same_context_value(context_data.get(key), expected):
            return False
    normalized_conversation_id = str(conversation_id or "").strip()
    return not normalized_conversation_id or _same_context_value(
        context_data.get("conversationId"),
        normalized_conversation_id,
    )


async def _handle_channel_control_command(
    db: AsyncSession,
    channel_service: UserMessageChannelService,
    channel: UserMessageChannel,
    *,
    command: str | None,
    tenant_id: int,
    site_brand: str,
) -> str | None:
    if not command:
        return None
    from app.domain.assistant.service import AssistantService

    extra = dict(channel.extra or {})
    assistant_session_id = _safe_int(extra.get("assistantSessionId"))
    assistant_service = AssistantService(db)

    if command in {"new_session", "clear_session"}:
        messages_deleted = 0
        if command == "clear_session" and assistant_session_id > 0:
            with suppress(Exception):
                result = await assistant_service.delete_session(
                    session_id=assistant_session_id,
                    tenant_id=tenant_id,
                    user_id=int(channel.user_id),
                )
                messages_deleted = int(result.messages_deleted or 0)
        extra.pop("assistantSessionId", None)
        extra.pop(_MESSAGE_CHANNEL_PENDING_INBOUND_KEY, None)
        extra.pop("lastPendingInboundAt", None)
        await channel_service.update(channel, {"extra": extra})
        await db.commit()
        if command == "new_session":
            return f"{_normalize_site_brand(site_brand)} 已开启新对话。你可以直接提出新的问题或任务。"
        suffix = f"，已清理 {messages_deleted} 条消息记录" if messages_deleted > 0 else ""
        return f"{_normalize_site_brand(site_brand)} 已清空当前 Channel 助手上下文{suffix}。"

    if command == "cancel_pending":
        if assistant_session_id > 0:
            with suppress(Exception):
                await assistant_service.clear_pending_mutation(
                    session_id=assistant_session_id,
                    tenant_id=tenant_id,
                    user_id=int(channel.user_id),
                )
        extra.pop(_MESSAGE_CHANNEL_PENDING_INBOUND_KEY, None)
        extra.pop("lastPendingInboundAt", None)
        await channel_service.update(channel, {"extra": extra})
        await db.commit()
        return "已取消当前待确认操作。上下文仍会保留，你可以继续提出新的问题。"
    return None


def _is_feishu_message_receive_event(payload: dict[str, Any], header: dict[str, Any], event: dict[str, Any]) -> bool:
    event_type = str(
        header.get("event_type")
        or header.get("eventType")
        or payload.get("type")
        or event.get("type")
        or ""
    ).strip()
    if not event_type:
        return True
    return "message.receive" in event_type or event_type == "p2_im_message_receive_v1"


def _sanitized_feishu_event_header(header: dict[str, Any]) -> dict[str, Any]:
    sensitive_keys = {"authorization", "encryptkey", "signature", "token", "verificationtoken"}
    return {
        key: value
        for key, value in header.items()
        if str(key).replace("_", "").strip().lower() not in sensitive_keys
    }


async def _find_active_inbound_channel_for_update(
    db: AsyncSession,
    *,
    channel_type: str,
    external_user_id: str,
    conversation_id: str | None = None,
    gateway_account_id: int | None = None,
) -> UserMessageChannel | None:
    normalized_external_user_id = str(external_user_id or "").strip()
    if not normalized_external_user_id:
        return None
    where = [
        UserMessageChannel.channel_type == channel_type,
        UserMessageChannel.external_user_id == normalized_external_user_id,
        UserMessageChannel.status == "active",
        UserMessageChannel.deleted_at.is_(None),
    ]
    # 与 `find_active_inbound_channel` 同一套归属限定。
    # **这条路径尤其要紧**：它后面接的是"注入用户的 AI 助手"，
    # 是整条链路里后果最重的一段。
    if gateway_account_id is not None:
        where.append(
            (UserMessageChannel.gateway_account_id == gateway_account_id)
            | UserMessageChannel.gateway_account_id.is_(None)
        )
    normalized_conversation_id = str(conversation_id or "").strip()
    if normalized_conversation_id:
        where.append(
            (UserMessageChannel.conversation_id == normalized_conversation_id)
            | UserMessageChannel.conversation_id.is_(None)
        )
    await escalate_to_write_lock(db)
    result = await db.execute(
        select(UserMessageChannel)
        .where(*where)
        .order_by(UserMessageChannel.last_inbound_at.desc(), UserMessageChannel.id.desc())
        .limit(3)
        .with_for_update()
    )
    return select_unambiguous_inbound_channel(list(result.scalars().all()), conversation_id=normalized_conversation_id)


class MessageGatewayAccountService(RepositoryBase[MessageGatewayAccount]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, MessageGatewayAccount)

    async def list_accounts(self) -> list[MessageGatewayAccount]:
        accounts, _ = await self.get_list(page=1, page_size=100, order_by="id", order_desc=False, return_total=True)
        return accounts

    async def get_account(self, account_id: int) -> MessageGatewayAccount | None:
        return await self.get_by_id(account_id, raise_not_found=False)

    async def resolve_for_channel(
        self, channel_type: str, *, gateway_account_id: int | None
    ) -> MessageGatewayAccount | None:
        """外发时该用哪个网关账号。

        **优先用渠道绑定的那个账号**，而不是当前默认账号。渠道是被账号 B 绑上的，
        却拿账号 A 的凭据外发——飞书的 open_id 是应用级作用域，直接失败；
        微信在管理员切换默认账号后也会立刻用错凭据。（codex 复核发现）

        绑定账号不可用（被停用/删除）时按渠道类型分流（codex 终审 #14）：

        - **飞书不回落，直接失败。** open_id 是应用级作用域——换一个账号（应用）
          之后这个 open_id 根本指不到同一个人，回落发出去要么报错要么发给
          错误的接收方。明确失败并提示重绑，比"看似发了"的静默错投诚实得多。
        - 微信/企微回落到默认账号：用户 ID 全局有效，换账号仍指同一个人，
          这是运维换账号的正常路径。存量渠道（NULL）同样走回落。
        """
        if gateway_account_id:
            account = await self.get_account(int(gateway_account_id))
            if account is not None and account.status == "active":
                return account
            if channel_type == "feishu":
                logger.warning(
                    "gateway_bound_account_unavailable_no_fallback",
                    channel_type=channel_type,
                    gateway_account_id=int(gateway_account_id),
                )
                return None
        return await self.get_default_active(channel_type)

    async def get_default_active(self, channel_type: str) -> MessageGatewayAccount | None:
        return await self.get_one(
            where=[
                MessageGatewayAccount.channel_type == channel_type,
                MessageGatewayAccount.status == "active",
                MessageGatewayAccount.is_default.is_(True),
            ]
        ) or await self.get_one(
            where=[MessageGatewayAccount.channel_type == channel_type, MessageGatewayAccount.status == "active"]
        )

    async def get_active_by_account_id(
        self,
        channel_type: str,
        account_id: str,
    ) -> MessageGatewayAccount | None:
        """Resolve exactly the account named by a signed inbound request."""
        return await self.get_one(
            where=[
                MessageGatewayAccount.channel_type == channel_type,
                MessageGatewayAccount.account_id == account_id,
                MessageGatewayAccount.status == "active",
            ]
        )

    async def get_active_accounts(self, channel_type: str | None = None) -> list[MessageGatewayAccount]:
        where = [MessageGatewayAccount.status == "active"]
        if channel_type:
            where.append(MessageGatewayAccount.channel_type == channel_type)
        accounts, _ = await self.get_list(page=1, page_size=100, where=where, order_by="id", return_total=True)
        return accounts

    async def upsert_wechat_account(
        self,
        *,
        name: str,
        account_id: str | None,
        base_url: str,
        token: str,
        is_default: bool = True,
    ) -> MessageGatewayAccount:
        if is_default:
            await self._clear_defaults("wechat")
        existing = await self.get_one(where=[MessageGatewayAccount.channel_type == "wechat", MessageGatewayAccount.account_id == account_id]) if account_id else None
        data = {
            "channel_type": "wechat",
            "name": name,
            "account_id": account_id,
            "base_url": base_url,
            "token_encrypted": encrypt_provider_secret(token),
            "status": "active",
            "is_default": is_default,
            "last_error": None,
        }
        if existing:
            return await self.update(existing, data)
        return await self.create(data)

    async def upsert_feishu_account(
        self,
        *,
        name: str,
        app_id: str,
        app_secret: str,
        domain: str = "feishu",
        bot_qr_url: str | None = None,
        is_default: bool = True,
    ) -> MessageGatewayAccount:
        if is_default:
            await self._clear_defaults("feishu")
        existing = await self.get_one(
            where=[MessageGatewayAccount.channel_type == "feishu", MessageGatewayAccount.account_id == app_id]
        )
        extra = dict(existing.extra or {}) if existing else {}
        # Legacy HTTP callback secrets were once stored as plain JSON.  The
        # signed gateway protocol uses token_encrypted; never retain those keys.
        extra.pop("verificationToken", None)
        extra.pop("encryptKey", None)
        extra.update(
            {
                "domain": domain,
                "botQrUrl": bot_qr_url,
            }
        )
        data = {
            "channel_type": "feishu",
            "name": name,
            "account_id": app_id,
            "base_url": domain,
            "token_encrypted": encrypt_provider_secret(app_secret),
            "status": "active",
            "is_default": is_default,
            "last_error": None,
            "extra": extra,
        }
        if existing:
            return await self.update(existing, data)
        return await self.create(data)

    async def upsert_wecom_account(
        self,
        *,
        name: str,
        bot_id: str,
        bot_secret: str | None,
        gateway_url: str | None = None,
        bot_qr_url: str | None = None,
        bot_open_url: str | None = None,
        is_default: bool = True,
    ) -> MessageGatewayAccount:
        if is_default:
            await self._clear_defaults("wecom")
        existing = await self.get_one(
            where=[MessageGatewayAccount.channel_type == "wecom", MessageGatewayAccount.account_id == bot_id]
        )
        normalized_secret = str(bot_secret or "").strip()
        if not normalized_secret and not existing:
            raise BusinessError(message="企业微信 Channel 网关 Bot Secret 不能为空")
        data = {
            "channel_type": "wecom",
            "name": name,
            "account_id": bot_id,
            "base_url": gateway_url,
            "status": "active",
            "is_default": is_default,
            "last_error": None,
            "extra": {
                "gatewayMode": "wecom_bot",
                "gatewayUrl": gateway_url,
                "botQrUrl": bot_qr_url,
                "botOpenUrl": bot_open_url,
                "openclaw": {
                    "channel": "wecom",
                    "botId": bot_id,
                    "connectionMode": "websocket",
                    "websocketUrl": "wss://openws.work.weixin.qq.com",
                },
            },
        }
        if normalized_secret:
            data["token_encrypted"] = encrypt_provider_secret(normalized_secret)
        if existing:
            return await self.update(existing, data)
        return await self.create(data)

    async def update_poll_state(self, account: MessageGatewayAccount, *, buf: str | None = None, error: str | None = None) -> None:
        values: dict[str, Any] = {"last_poll_at": datetime.now(UTC), "last_error": error}
        if buf is not None:
            values["get_updates_buf"] = buf
        await self.update(account, values)

    async def _clear_defaults(self, channel_type: str) -> None:
        stmt = (
            update(MessageGatewayAccount)
            .where(
                and_(
                    MessageGatewayAccount.channel_type == channel_type,
                    MessageGatewayAccount.is_default.is_(True),
                    MessageGatewayAccount.deleted_at.is_(None),
                )
            )
            .values(is_default=False)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    @staticmethod
    def to_item(account: MessageGatewayAccount) -> dict[str, Any]:
        extra = account.extra if isinstance(account.extra, dict) else {}
        return {
            "id": account.id,
            "channelType": account.channel_type,
            "name": account.name,
            "accountId": account.account_id,
            "baseUrl": account.base_url,
            "gatewayUrl": extra.get("gatewayUrl") or extra.get("gateway_url") or account.base_url,
            "botQrUrl": extra.get("botQrUrl"),
            "botOpenUrl": extra.get("botOpenUrl"),
            "domain": extra.get("domain") or account.base_url,
            "status": account.status,
            "isDefault": account.is_default,
            "tokenConfigured": bool(account.token_encrypted),
            "tokenMasked": mask_provider_secret(decrypt_provider_secret_or_plain(account.token_encrypted)),
            "lastPollAt": account.last_poll_at,
            "lastError": account.last_error,
            "createdAt": account.created_at,
            "updatedAt": account.updated_at,
        }


def extract_text_from_ilink_message(message: dict[str, Any]) -> str:
    for item in message.get("item_list") or []:
        if item.get("type") == 1:
            text = ((item.get("text_item") or {}).get("text") or "").strip()
            if text:
                return text
    return ""


def extract_text_from_feishu_message(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        try:
            parsed = json.loads(content or "{}")
            if isinstance(parsed, dict):
                return str(parsed.get("text") or "").strip()
        except Exception:
            return str(content or "").strip()
    return extract_text_from_ilink_message(message)


def extract_bind_token(text: str) -> str | None:
    normalized = " ".join(str(text or "").strip().split())
    prefix = "BIND "
    if normalized.upper().startswith(prefix):
        return normalized[len(prefix) :].strip()
    # Keep already-issued six-digit codes usable for their remaining 10-minute
    # lifetime while every newly generated code has eight digits.
    if re.fullmatch(r"(?:\d{6}|\d{8})", normalized):
        return normalized
    return None


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _payload_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def extract_wecom_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    body = _payload_dict(payload.get("body"))
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    source = body or event or message or data or payload
    sender = _payload_dict(source.get("sender"))
    conversation = _payload_dict(source.get("conversation"))
    from_payload = _payload_dict(source.get("from"))
    text_payload = _payload_dict(source.get("text"))
    chat_id = _first_text(
        source.get("conversationId"),
        source.get("chatId"),
        source.get("chatid"),
        source.get("chat_id"),
        source.get("roomId"),
        source.get("room_id"),
        conversation.get("id"),
        from_payload.get("chat_id"),
    )
    external_user_id = _first_text(
        source.get("externalUserId"),
        source.get("fromUserId"),
        source.get("from_user_id"),
        source.get("userid"),
        from_payload.get("userid"),
        sender.get("userId"),
        sender.get("userid"),
        sender.get("id"),
    )
    conversation_id = chat_id or external_user_id
    return {
        "text": _first_text(text_payload.get("content"), source.get("text"), source.get("content"), source.get("messageText")),
        "externalUserId": external_user_id,
        "conversationId": conversation_id or None,
        "contextToken": _first_text(
            source.get("contextToken"),
            source.get("msgid"),
            source.get("msg_id"),
            source.get("messageId"),
            _payload_dict(payload.get("headers")).get("req_id"),
        )
        or None,
        "displayName": _first_text(sender.get("name"), sender.get("displayName"), source.get("displayName"), from_payload.get("name"))
        or None,
        "avatar": _first_text(sender.get("avatar"), source.get("avatar")) or None,
    }


async def handle_wecom_event_payload(
    db: AsyncSession,
    payload: dict[str, Any],
    *,
    gateway_account_id: int | None = None,
    bind_attempt_source: str | None = None,
) -> str | None:
    parsed = extract_wecom_event_payload(payload)
    text = str(parsed["text"] or "").strip()
    external_user_id = str(parsed["externalUserId"] or "").strip()
    conversation_id = str(parsed["conversationId"] or "").strip() or None
    context_token = str(parsed["contextToken"] or "").strip() or None
    if not text or not external_user_id:
        logger.info(
            "message_channel_wecom_event_ignored",
            has_text=bool(text),
            has_external_user_id=bool(external_user_id),
            cmd=str(payload.get("cmd") or ""),
        )
        return None

    channel_service = UserMessageChannelService(db)
    bind_token = extract_bind_token(text)
    if bind_token:
        channel = await channel_service.bind_inbound_message(
            gateway_account_id=gateway_account_id,
            bind_token=bind_token,
            channel_type="wecom",
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            context_token=context_token,
            display_name=parsed["displayName"],
            avatar=parsed["avatar"],
            raw_payload=payload,
            attempt_source=bind_attempt_source or (
                f"gateway-account:{gateway_account_id}" if gateway_account_id else None
            ),
        )
        if channel:
            await db.commit()
            site_brand = await _resolve_channel_site_brand(db, channel)
            logger.info(
                "message_channel_wecom_bound",
                channel_id=channel.id,
                external_user_id=external_user_id,
                conversation_id=conversation_id,
            )
            return _channel_bound_reply("企业微信", site_brand)

        active_channel = await channel_service.find_active_inbound_channel(
            gateway_account_id=gateway_account_id,
            channel_type="wecom",
            external_user_id=external_user_id,
            conversation_id=conversation_id,
        )
        site_brand = await _resolve_channel_site_brand(db, active_channel) if active_channel else _normalize_site_brand()
        return (
            _channel_bound_reply("企业微信", site_brand)
            if active_channel
            else _channel_invalid_bind_reply("企业微信", site_brand)
        )

    logger.info(
        "message_channel_wecom_inbound_text",
        external_user_id=external_user_id,
        conversation_id=conversation_id,
        context_token=context_token,
        text_preview=text[:120],
    )
    reply = await relay_inbound_to_assistant(
        db,
        gateway_account_id=gateway_account_id,
        channel_type="wecom",
        external_user_id=external_user_id,
        conversation_id=conversation_id,
        context_token=context_token,
        text=text,
        raw_payload=payload,
    )
    if reply:
        return reply

    active_channel = await channel_service.find_active_inbound_channel(
        gateway_account_id=gateway_account_id,
        channel_type="wecom",
        external_user_id=external_user_id,
        conversation_id=conversation_id,
    )
    if active_channel:
        return None
    return _channel_bind_prompt_text()


def _resolve_wechat_login(extra: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve current and legacy WeChat QR login state from channel extra."""
    login = extra.get("wechatLogin") if isinstance(extra.get("wechatLogin"), dict) else None
    if login and str(login.get("qrcode") or "").strip():
        return dict(login)

    qr = extra.get("qr") if isinstance(extra.get("qr"), dict) else {}
    if bool(qr.get("gatewayReady")):
        return None
    provider_raw = qr.get("providerRaw") if isinstance(qr.get("providerRaw"), dict) else {}
    qrcode = str(provider_raw.get("qrcode") or provider_raw.get("qrCode") or qr.get("qrPayload") or "").strip()
    if not qrcode:
        return None
    return {
        "qrcode": qrcode,
        "expiresAt": extra.get("expiresAt") or qr.get("expiresAt"),
        "lastStatus": "created",
    }


def _wechat_pending_waits_for_bind_code(extra: dict[str, Any]) -> bool:
    qr = extra.get("qr") if isinstance(extra.get("qr"), dict) else {}
    return bool(qr.get("gatewayReady"))


def _wechat_poll_base_url(login: dict[str, Any]) -> str:
    raw_value = str(login.get("pollBaseUrl") or ILINK_DEFAULT_BASE_URL).strip()
    if raw_value.startswith("http://") or raw_value.startswith("https://"):
        return raw_value.rstrip("/")
    return f"https://{raw_value}".rstrip("/")


def _wechat_qr_status(data: dict[str, Any]) -> str:
    return str(data.get("status") or data.get("qrcode_status") or "").strip().lower()


def _wechat_qr_redirect_base_url(data: dict[str, Any]) -> str | None:
    redirect_host = str(data.get("redirect_host") or data.get("redirectHost") or "").strip()
    if not redirect_host:
        return None
    if redirect_host.startswith("http://") or redirect_host.startswith("https://"):
        return redirect_host.rstrip("/")
    return f"https://{redirect_host}".rstrip("/")


async def _safe_send_wechat_text(
    client: WechatIlinkClient,
    *,
    to_user_id: str,
    text: str,
    context_token: str | None = None,
) -> bool:
    if not str(to_user_id or "").strip():
        return False
    try:
        await client.send_text(to_user_id=to_user_id, text=text, context_token=context_token)
    except Exception as exc:
        logger.warning(
            "message_channel_wechat_send_text_failed",
            to_user_id=str(to_user_id or "")[:80],
            context_token=str(context_token or "")[:120],
            text_preview=str(text or "")[:160],
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return False
    return True


async def _safe_send_wechat_processing(
    client: WechatIlinkClient,
    *,
    to_user_id: str,
    context_token: str | None = None,
) -> Any:
    if not str(to_user_id or "").strip():
        return False
    try:
        runtime = _WechatTypingRuntime(client, to_user_id=to_user_id, context_token=context_token)
        if not await runtime.start():
            return False
        return runtime
    except Exception as exc:
        logger.debug("message_channel_wechat_typing_start_failed", error=str(exc))
        return False


async def _safe_stop_wechat_processing(
    client: WechatIlinkClient,
    *,
    to_user_id: str,
    context_token: str | None = None,
    started: Any = None,
) -> bool:
    if isinstance(started, _WechatTypingRuntime):
        try:
            return await started.stop()
        except Exception as exc:
            logger.debug("message_channel_wechat_typing_stop_failed", error=str(exc))
            return False
    if isinstance(started, dict):
        heartbeat = started.get("heartbeat")
        if heartbeat and hasattr(heartbeat, "cancel"):
            heartbeat.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await heartbeat
        started = started.get("started")
    if not started or not str(to_user_id or "").strip():
        return False
    try:
        return await client.send_typing_indicator(
            to_user_id=to_user_id,
            context_token=context_token,
            status=2,
        )
    except Exception as exc:
        logger.debug("message_channel_wechat_typing_stop_failed", error=str(exc))
        return False


async def _send_feishu_text(
    account: MessageGatewayAccount | None,
    *,
    open_id: str,
    text: str,
) -> bool:
    if not account or not account.account_id or not str(open_id or "").strip():
        return False
    app_secret = decrypt_provider_secret_or_plain(account.token_encrypted)
    if not app_secret:
        return False
    try:
        await FeishuClient(
            app_id=account.account_id,
            app_secret=app_secret,
            domain=str((account.extra or {}).get("domain") or account.base_url or "feishu"),
        ).send_text(open_id=open_id, text=text)
    except Exception as exc:
        logger.warning(
            "message_channel_feishu_send_text_failed",
            account_id=getattr(account, "id", None),
            open_id=str(open_id or "")[:80],
            text_preview=str(text or "")[:160],
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return False
    return True


async def _safe_add_feishu_typing_reaction(
    account: MessageGatewayAccount | None,
    *,
    message_id: str,
) -> dict[str, str] | None:
    if not account or not account.account_id or not str(message_id or "").strip():
        return None
    app_secret = decrypt_provider_secret_or_plain(account.token_encrypted)
    if not app_secret:
        return None
    normalized_message_id = str(message_id or "").split(":", 1)[0].strip()
    try:
        data = await FeishuClient(
            app_id=account.account_id,
            app_secret=app_secret,
            domain=str((account.extra or {}).get("domain") or account.base_url or "feishu"),
        ).add_message_reaction(message_id=normalized_message_id, emoji_type="Typing")
    except Exception:
        return None
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    reaction_id = str((payload or {}).get("reaction_id") or (payload or {}).get("reactionId") or "").strip()
    if not reaction_id:
        return None
    return {"message_id": normalized_message_id, "reaction_id": reaction_id}


async def _safe_remove_feishu_typing_reaction(
    account: MessageGatewayAccount | None,
    *,
    state: Any,
) -> bool:
    if not isinstance(state, dict) or not account or not account.account_id:
        return False
    message_id = str(state.get("message_id") or "").strip()
    reaction_id = str(state.get("reaction_id") or "").strip()
    if not message_id or not reaction_id:
        return False
    app_secret = decrypt_provider_secret_or_plain(account.token_encrypted)
    if not app_secret:
        return False
    try:
        await FeishuClient(
            app_id=account.account_id,
            app_secret=app_secret,
            domain=str((account.extra or {}).get("domain") or account.base_url or "feishu"),
        ).delete_message_reaction(message_id=message_id, reaction_id=reaction_id)
    except Exception:
        return False
    return True


async def handle_feishu_event_payload(
    db: AsyncSession,
    payload: dict[str, Any],
    *,
    gateway_account_id: int | None = None,
    bind_attempt_source: str | None = None,
) -> int:
    """Handle a Feishu/Lark event from either HTTP callback or WebSocket long connection."""
    service = MessageGatewayAccountService(db)
    account = await service.get_account(gateway_account_id) if gateway_account_id else None
    if not account:
        account = await service.get_default_active("feishu")
    event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
    header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
    stored_payload = {"event": event, "header": _sanitized_feishu_event_header(header)}
    if not _is_feishu_message_receive_event(payload, header, event):
        return 0
    message = event.get("message") if isinstance(event.get("message"), dict) else event
    sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
    sender_type = str(sender.get("sender_type") or sender.get("senderType") or "").strip().lower()
    if sender_type and sender_type not in {"user"}:
        return 0
    sender_id = sender.get("sender_id") or sender.get("senderId") or {}
    if not isinstance(sender_id, dict):
        sender_id = {}
    operator_id = event.get("operator_id") if isinstance(event.get("operator_id"), dict) else {}

    open_id = str(
        sender_id.get("open_id") or sender.get("open_id") or event.get("open_id") or operator_id.get("open_id") or ""
    ).strip()
    chat_id = str(message.get("chat_id") or event.get("chat_id") or "").strip()
    message_id = str(message.get("message_id") or event.get("message_id") or "").strip()
    text = extract_text_from_feishu_message(message)
    bind_token = extract_bind_token(text)

    channel_service = UserMessageChannelService(db)
    if not text and open_id:
        # 预绑定匹配必须按**当前网关账号**限定（codex 终审 #7）：
        # open_id 是应用级作用域，账号 A 收到的事件按全局匹配会把 open_id
        # 写进账号 B（可能是另一租户）的 pending 渠道，并用那个租户的品牌回复。
        # NULL（创建时未指定账号）只允许默认账号命中——与存量认领同一条规则。
        account_scope = UserMessageChannel.gateway_account_id == int(account.id)
        if await channel_service._is_default_gateway_account(  # noqa: SLF001 - 同域内共享规则
            channel_type="feishu", gateway_account_id=int(account.id)
        ):
            account_scope = account_scope | UserMessageChannel.gateway_account_id.is_(None)
        pending_channels, _ = await channel_service.get_list(
            page=1,
            page_size=2,
            where=[
                UserMessageChannel.channel_type == "feishu",
                UserMessageChannel.status == "pending",
                or_(UserMessageChannel.external_user_id == open_id, UserMessageChannel.external_user_id.is_(None)),
                account_scope,
            ],
            order_by="id",
            order_desc=True,
            return_total=True,
        )
        if len(pending_channels) == 1 and pending_channels[0].bind_token:
            pending_channel = pending_channels[0]
            site_brand = await _resolve_channel_site_brand(db, pending_channel)
            await channel_service.update(
                pending_channel,
                {"external_user_id": open_id, "conversation_id": chat_id or pending_channel.conversation_id},
            )
            await db.commit()
            await _send_feishu_text(
                account,
                open_id=open_id,
                text=f"{_channel_bind_prompt_text(site_brand)}\n系统收到关联码后会完成账号绑定。",
            )
            return 1

    if bind_token:
        channel = await channel_service.bind_inbound_message(
            gateway_account_id=gateway_account_id,
            bind_token=bind_token,
            channel_type="feishu",
            external_user_id=open_id,
            conversation_id=chat_id or None,
            context_token=message_id or None,
            raw_payload=stored_payload,
            attempt_source=bind_attempt_source or (
                f"gateway-account:{gateway_account_id}" if gateway_account_id else None
            ),
        )
        if channel:
            await db.commit()
            site_brand = await _resolve_channel_site_brand(db, channel)
            await _send_feishu_text(
                account,
                open_id=channel.external_user_id or open_id,
                text=_channel_bound_reply("飞书", site_brand),
            )
            return 1

        active_channel = await channel_service.find_active_inbound_channel(
            gateway_account_id=gateway_account_id,
            channel_type="feishu",
            external_user_id=open_id,
            conversation_id=chat_id or None,
        )
        if active_channel and _is_duplicate_inbound_context(active_channel, message_id):
            return 1
        site_brand = await _resolve_channel_site_brand(db, active_channel) if active_channel else _normalize_site_brand()
        await _send_feishu_text(
            account,
            open_id=open_id,
            text=(
                _channel_bound_reply("飞书", site_brand)
                if active_channel
                else _channel_invalid_bind_reply("飞书", site_brand)
            ),
        )
        return 1

    if not open_id:
        return 0

    reply = await relay_inbound_to_assistant(
        db,
        gateway_account_id=gateway_account_id,
        channel_type="feishu",
        external_user_id=open_id,
        conversation_id=chat_id or None,
        context_token=message_id or None,
        text=text,
        raw_payload=stored_payload,
        processing_callback=lambda: _safe_add_feishu_typing_reaction(
            account,
            message_id=message_id,
        ),
        processing_cleanup_callback=lambda state: _safe_remove_feishu_typing_reaction(
            account,
            state=state,
        ),
    )
    if reply:
        sent = await _send_feishu_text(account, open_id=open_id, text=reply)
        active_channel = await channel_service.find_active_inbound_channel(
            gateway_account_id=gateway_account_id,
            channel_type="feishu",
            external_user_id=open_id,
            conversation_id=chat_id or None,
        )
        if active_channel:
            await channel_service.set_delivery_result(
                active_channel,
                ok=sent,
                error=None if sent else "飞书 Channel 回复发送失败",
            )
            await db.commit()
        return 1
    if text:
        active_channel = await channel_service.find_active_inbound_channel(
            gateway_account_id=gateway_account_id,
            channel_type="feishu",
            external_user_id=open_id,
            conversation_id=chat_id or None,
        )
        if not active_channel:
            await _send_feishu_text(account, open_id=open_id, text=_channel_bind_prompt_text())
        return 1
    return 0


async def relay_inbound_to_assistant(
    db: AsyncSession,
    *,
    gateway_account_id: int | None = None,
    channel_type: str,
    external_user_id: str,
    conversation_id: str | None,
    context_token: str | None,
    text: str,
    raw_payload: dict[str, Any],
    inbound_dedupe_token: str | None = None,
    processing_callback: Callable[[], Awaitable[Any]] | None = None,
    processing_cleanup_callback: Callable[[Any], Awaitable[Any]] | None = None,
) -> str | None:
    """Relay an already-bound channel message to the default AI assistant."""
    normalized_text = str(text or "").strip()
    if not normalized_text:
        return None

    channel_service = UserMessageChannelService(db)
    channel = await _find_active_inbound_channel_for_update(
        db,
        gateway_account_id=gateway_account_id,
        channel_type=channel_type,
        external_user_id=external_user_id,
        conversation_id=conversation_id,
    )
    if not channel:
        return None
    dedupe_token = inbound_dedupe_token or _inbound_message_dedupe_token(
        channel_type=channel_type,
        raw_payload=raw_payload,
        context_token=context_token,
    )
    if _is_duplicate_inbound_context(channel, dedupe_token):
        return None
    inbound_reference = _inbound_message_reference(
        text=normalized_text,
        context_token=context_token,
        dedupe_token=dedupe_token,
        raw_payload=raw_payload,
    )

    channel = await channel_service.record_inbound_message(
        channel,
        gateway_account_id=gateway_account_id,
        context_token=context_token,
        inbound_dedupe_token=dedupe_token,
        conversation_id=conversation_id,
        raw_payload=raw_payload,
    )
    await db.commit()

    try:
        from app.core.data_permission import get_user_data_scope
        from app.domain.assistant.config_service import AssistantConfigService
        from app.domain.assistant.service import AssistantService

        result = await db.execute(select(User).where(User.id == channel.user_id, User.deleted_at.is_(None)))
        user = result.scalar_one_or_none()
        tenant_id = int(getattr(user, "tenant_id", 0) or 0) if user else 0
        site_brand = await _resolve_tenant_site_brand(db, tenant_id)
        if tenant_id <= 0:
            await channel_service.set_delivery_result(channel, ok=False, error="无法解析绑定用户的租户")
            return f"{_normalize_site_brand(site_brand)} 已收到消息，但暂时无法解析你的账号租户。"

        if not await AssistantConfigService(db).is_enabled(tenant_id):
            return _channel_assistant_disabled_reply(site_brand)

        control_reply = await _handle_channel_control_command(
            db,
            channel_service,
            channel,
            command=_resolve_channel_control_command(normalized_text),
            tenant_id=tenant_id,
            site_brand=site_brand,
        )
        if control_reply:
            return control_reply

        await db.commit()

        active_channel_id = int(channel.id)
        if active_channel_id in _MESSAGE_CHANNEL_ACTIVE_CHANNEL_IDS:
            extra = _append_pending_inbound_message(dict(channel.extra or {}), inbound_reference)
            await channel_service.update(channel, {"extra": extra})
            await db.commit()
            return (
                f"{_normalize_site_brand(site_brand)} Channel 已收到你的补充内容。"
                "我会把它合并到正在处理的回复里，请稍等。"
            )

        processing_state: Any = None
        processing_started = False
        _MESSAGE_CHANNEL_ACTIVE_CHANNEL_IDS.add(active_channel_id)
        if processing_callback:
            try:
                processing_state = await processing_callback()
                processing_started = True
            except Exception:
                pass

        try:
            assistant_service = AssistantService(db)
            extra = dict(channel.extra or {})
            assistant_session_id = _safe_int(extra.get("assistantSessionId"))
            data_scope = await get_user_data_scope(db, user)
            read_team_ids = (
                None
                if data_scope.has_all_read_access
                else [int(item) for item in data_scope.read_team_ids if isinstance(item, int)]
            )
            context_params = {
                "source": "message_channel",
                "channelType": channel_type,
                "channelId": channel.id,
                "externalUserId": external_user_id,
                "conversationId": conversation_id,
                "boundUserId": channel.user_id,
                "boundTenantId": tenant_id,
                "dataScope": {
                    "hasAllReadAccess": data_scope.has_all_read_access,
                    "readTeamIds": [] if read_team_ids is None else read_team_ids,
                },
                "recentInboundMessages": [inbound_reference],
            }
            if isinstance(processing_state, _WechatTypingRuntime):
                await processing_state.touch("assistant_session")
            if assistant_session_id > 0:
                try:
                    existing_session = await assistant_service.get_session(
                        session_id=assistant_session_id,
                        tenant_id=tenant_id,
                        user_id=channel.user_id,
                    )
                except Exception:
                    assistant_session_id = 0
                    extra.pop("assistantSessionId", None)
                else:
                    if not _message_channel_assistant_session_matches(
                        route_path=existing_session.route_path,
                        context_data=existing_session.context_data,
                        channel=channel,
                        channel_type=channel_type,
                        external_user_id=external_user_id,
                        conversation_id=conversation_id,
                        tenant_id=tenant_id,
                    ):
                        assistant_session_id = 0
                        extra.pop("assistantSessionId", None)
            if assistant_session_id <= 0:
                session = await assistant_service.create_session(
                    tenant_id=tenant_id,
                    user_id=channel.user_id,
                    module_code="default",
                    route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
                    context_params=context_params,
                )
                assistant_session_id = int(session.id)
                extra["assistantSessionId"] = assistant_session_id
                channel = await channel_service.update(channel, {"extra": extra})

            if isinstance(processing_state, _WechatTypingRuntime):
                await processing_state.touch("assistant_call")
            result = await assistant_service.chat_reply(
                session_id=assistant_session_id,
                message=normalized_text,
                tenant_id=tenant_id,
                user_id=channel.user_id,
                team_ids=read_team_ids,
                route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
                context_params=context_params,
            )
            reply = str(result.reply or "").strip() or "已收到。"
            if isinstance(processing_state, _WechatTypingRuntime):
                await processing_state.touch("assistant_replied")
            pending_messages = await _drain_pending_inbound_messages(db, channel_service, active_channel_id)
            if pending_messages:
                if isinstance(processing_state, _WechatTypingRuntime):
                    await processing_state.touch("pending_messages")
                if _should_auto_merge_pending_followup(pending_messages):
                    followup_context_params = {
                        **context_params,
                        "recentInboundMessages": [inbound_reference, *pending_messages][
                            -_MESSAGE_CHANNEL_PENDING_INBOUND_LIMIT:
                        ],
                    }
                    followup_result = await assistant_service.chat_reply(
                        session_id=assistant_session_id,
                        message=_build_pending_followup_message(pending_messages),
                        tenant_id=tenant_id,
                        user_id=channel.user_id,
                        team_ids=read_team_ids,
                        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
                        context_params=followup_context_params,
                    )
                    if isinstance(processing_state, _WechatTypingRuntime):
                        await processing_state.touch("followup_replied")
                    followup_reply = str(followup_result.reply or "").strip()
                    if followup_reply:
                        reply = f"{reply}\n\n{followup_reply}" if reply else followup_reply
                else:
                    deferred_notice = _build_deferred_pending_notice(pending_messages)
                    if deferred_notice:
                        reply = f"{reply}\n\n{deferred_notice}" if reply else deferred_notice
            await db.commit()
            return reply
        finally:
            if processing_cleanup_callback and processing_started:
                with suppress(Exception):
                    await processing_cleanup_callback(processing_state)
            _MESSAGE_CHANNEL_ACTIVE_CHANNEL_IDS.discard(active_channel_id)
    except FeatureDisabledError:
        return _channel_assistant_disabled_reply(locals().get("site_brand"))
    except Exception as exc:  # noqa: BLE001
        await channel_service.set_delivery_result(channel, ok=False, error=str(exc))
        await db.commit()
        return _channel_assistant_error_reply(exc, locals().get("site_brand"))


async def poll_wechat_gateway_account(db: AsyncSession, account: MessageGatewayAccount) -> int:
    token = decrypt_provider_secret_or_plain(account.token_encrypted)
    if not token or not account.base_url:
        await MessageGatewayAccountService(db).update_poll_state(account, error="微信网关账号缺少 token 或 baseUrl")
        await db.commit()
        return 0

    client = WechatIlinkClient(base_url=account.base_url, token=token)
    service = MessageGatewayAccountService(db)
    channel_service = UserMessageChannelService(db)
    await db.commit()
    try:
        response = await client.get_updates(get_updates_buf=account.get_updates_buf)
    except Exception as exc:  # noqa: BLE001
        await service.update_poll_state(account, error=str(exc))
        await db.commit()
        return 0

    if response.get("ret") not in (None, 0):
        await service.update_poll_state(account, buf=response.get("get_updates_buf"), error=str(response))
        await db.commit()
        return 0

    processed = 0
    messages = response.get("msgs") or []
    should_advance_buf = True
    if messages:
        logger.info(
            "message_channel_wechat_updates_received",
            account_id=account.id,
            bot_account_id=account.account_id,
            message_count=len(messages),
            message_types=[message.get("message_type") for message in messages[:10] if isinstance(message, dict)],
            message_ids=[str(message.get("message_id") or "") for message in messages[:10] if isinstance(message, dict)],
            from_user_ids=[str(message.get("from_user_id") or "") for message in messages[:10] if isinstance(message, dict)],
        )
    for message in messages:
        if message.get("message_type") != 1:
            logger.debug(
                "message_channel_wechat_message_skipped_type",
                account_id=account.id,
                message_type=message.get("message_type"),
                message_id=message.get("message_id"),
                from_user_id=message.get("from_user_id"),
            )
            continue
        text = extract_text_from_ilink_message(message)
        bind_token = extract_bind_token(text)
        if not bind_token:
            from_user_id = str(message.get("from_user_id") or "")
            context_token = message.get("context_token")
            conversation_id = str(message.get("session_id") or "") or None
            dedupe_token = _inbound_message_dedupe_token(
                channel_type="wechat",
                raw_payload=message,
                context_token=context_token,
            )
            logger.info(
                "message_channel_wechat_inbound_text",
                account_id=account.id,
                message_id=message.get("message_id"),
                client_id=message.get("client_id"),
                from_user_id=from_user_id,
                session_id=message.get("session_id"),
                text_preview=text[:120],
            )
            reply = await relay_inbound_to_assistant(
                db,
                gateway_account_id=int(account.id),
                channel_type="wechat",
                external_user_id=from_user_id,
                conversation_id=conversation_id,
                context_token=context_token,
                text=text,
                raw_payload=message,
                inbound_dedupe_token=dedupe_token,
                processing_callback=(
                    lambda from_user_id=from_user_id, context_token=context_token: _safe_send_wechat_processing(
                        client,
                        to_user_id=from_user_id,
                        context_token=context_token,
                    )
                ),
                processing_cleanup_callback=(
                    lambda started, from_user_id=from_user_id, context_token=context_token: _safe_stop_wechat_processing(
                        client,
                        to_user_id=from_user_id,
                        context_token=context_token,
                        started=started,
                    )
                ),
            )
            if reply:
                with suppress(Exception):
                    await client.send_typing_indicator(
                        to_user_id=from_user_id,
                        context_token=context_token,
                        status=1,
                    )
                sent = await _safe_send_wechat_text(
                    client,
                    to_user_id=from_user_id,
                    text=reply,
                    context_token=context_token,
                )
                active_channel = await channel_service.find_active_inbound_channel(
                    channel_type="wechat",
                    gateway_account_id=int(account.id),
                    external_user_id=from_user_id,
                    conversation_id=conversation_id,
                )
                if sent:
                    if active_channel:
                        await channel_service.set_delivery_result(active_channel, ok=True)
                        await db.commit()
                    processed += 1
                else:
                    should_advance_buf = False
                    if active_channel:
                        await _mark_inbound_retry(
                            channel_service,
                            active_channel,
                            dedupe_token=dedupe_token,
                            reason="微信 Channel 回复发送失败，保留本条消息等待下次轮询重试",
                        )
                        await db.commit()
                    logger.warning(
                        "message_channel_wechat_reply_send_failed_retry_scheduled",
                        account_id=account.id,
                        message_id=message.get("message_id"),
                        from_user_id=from_user_id,
                        dedupe_token=str(dedupe_token or "")[:120],
                    )
                    break
            elif text:
                active_channel = await channel_service.find_active_inbound_channel(
                    channel_type="wechat",
                    gateway_account_id=int(account.id),
                    external_user_id=from_user_id,
                    conversation_id=conversation_id,
                )
                await db.commit()
                if active_channel:
                    processed += 1
                else:
                    await _safe_send_wechat_text(
                        client,
                        to_user_id=from_user_id,
                        text=_channel_bind_prompt_text(),
                        context_token=context_token,
                    )
                    processed += 1
            continue
        channel = await channel_service.bind_inbound_message(
            gateway_account_id=int(account.id),
            bind_token=bind_token,
            channel_type="wechat",
            external_user_id=str(message.get("from_user_id") or ""),
            conversation_id=str(message.get("session_id") or "") or None,
            context_token=message.get("context_token"),
            raw_payload=message,
        )
        if channel:
            site_brand = await _resolve_channel_site_brand(db, channel)
            await db.commit()
            await _safe_send_wechat_text(
                client,
                to_user_id=channel.external_user_id or "",
                text=_channel_bound_reply("微信", site_brand),
                context_token=channel.context_token,
            )
            processed += 1
        else:
            active_channel = await channel_service.find_active_inbound_channel(
                channel_type="wechat",
                gateway_account_id=int(account.id),
                external_user_id=str(message.get("from_user_id") or ""),
                conversation_id=str(message.get("session_id") or "") or None,
            )
            await db.commit()
            if active_channel:
                if not _is_duplicate_inbound_context(active_channel, message.get("context_token")):
                    await channel_service.record_inbound_message(
                        active_channel,
                        gateway_account_id=int(account.id),
                        context_token=message.get("context_token"),
                        conversation_id=str(message.get("session_id") or "") or None,
                        raw_payload=message,
                    )
                    await db.commit()
                    logger.info(
                        "message_channel_wechat_bind_code_ignored_active",
                        channel_id=active_channel.id,
                    )
                processed += 1
                continue
            site_brand = _normalize_site_brand()
            await db.commit()
            await _safe_send_wechat_text(
                client,
                to_user_id=str(message.get("from_user_id") or ""),
                text=_channel_invalid_bind_reply("微信", site_brand),
                context_token=message.get("context_token"),
            )
            processed += 1

    if should_advance_buf:
        await service.update_poll_state(account, buf=response.get("get_updates_buf"), error=None)
    else:
        await service.update_poll_state(account, error="微信 Channel 回复发送失败，已保留轮询游标等待重试")
    await db.commit()
    return processed


async def poll_wechat_gateway_account_isolated(account_id: int) -> int:
    normalized_account_id = _safe_int(account_id)
    if normalized_account_id <= 0:
        return 0

    async with get_db_context() as db:
        account = await MessageGatewayAccountService(db).get_account(normalized_account_id)
        if not account or str(account.status or "").strip().lower() != "active":
            return 0
        return await poll_wechat_gateway_account(db, account)


async def poll_pending_wechat_logins(db: AsyncSession) -> int:
    """Poll WeChat iLink QR login flows started from personal settings."""
    channel_service = UserMessageChannelService(db)
    channels, _ = await channel_service.get_list(
        page=1,
        page_size=50,
        where=[
            UserMessageChannel.channel_type == "wechat",
            UserMessageChannel.status == "pending",
        ],
        order_by="id",
        order_desc=False,
        return_total=True,
    )
    await db.commit()
    processed = 0
    gateway_service = MessageGatewayAccountService(db)
    for channel in channels:
        extra = dict(channel.extra or {})
        login = _resolve_wechat_login(extra)
        if not login:
            if _wechat_pending_waits_for_bind_code(extra):
                if _is_iso_expired(str(extra.get("expiresAt") or "")):
                    await channel_service.update(channel, {"status": "disabled", "last_error": "绑定码已过期"})
                    await db.commit()
                    processed += 1
                continue
            await channel_service.delete(channel)
            await db.commit()
            processed += 1
            continue
        qrcode = str(login.get("qrcode") or "").strip()
        if not qrcode:
            continue
        poll_base_url = _wechat_poll_base_url(login)

        try:
            status = await WechatIlinkClient(base_url=poll_base_url).get_qrcode_status(qrcode=qrcode)
        except Exception as exc:  # noqa: BLE001
            extra["wechatLogin"] = {**login, "lastError": str(exc), "lastPollAt": datetime.now(UTC).isoformat()}
            await channel_service.update(channel, {"extra": extra})
            await db.commit()
            continue

        qr_status = _wechat_qr_status(status)
        token = status.get("bot_token") or status.get("botToken")
        if qr_status == "scaned_but_redirect":
            redirected_base_url = _wechat_qr_redirect_base_url(status)
            extra["wechatLogin"] = {
                **login,
                "lastStatus": qr_status,
                "pollBaseUrl": redirected_base_url or poll_base_url,
                "lastRaw": status,
                "lastPollAt": datetime.now(UTC).isoformat(),
            }
            await channel_service.update(channel, {"extra": extra})
            await db.commit()
            continue
        if qr_status in {"wait", "scaned", "scanned", ""} and not token:
            extra["wechatLogin"] = {
                **login,
                "lastStatus": qr_status or "wait",
                "pollBaseUrl": poll_base_url,
                "lastPollAt": datetime.now(UTC).isoformat(),
            }
            await channel_service.update(channel, {"extra": extra})
            await db.commit()
            continue
        if qr_status == "expired":
            await channel_service.delete(channel)
            await db.commit()
            processed += 1
            continue

        base_url = status.get("baseurl") or status.get("baseUrl") or poll_base_url or ILINK_DEFAULT_BASE_URL
        account_id = (
            status.get("account_id")
            or status.get("accountId")
            or status.get("ilink_bot_id")
            or status.get("bot_id")
            or status.get("botId")
        )
        external_user_id = (
            status.get("ilink_user_id")
            or status.get("user_id")
            or status.get("userId")
            or status.get("openid")
            or account_id
        )
        if not token or not base_url:
            last_error = "微信扫码已确认，但网关未返回 bot_token/baseurl" if qr_status == "confirmed" else None
            extra["wechatLogin"] = {
                **login,
                "lastStatus": qr_status or "unknown",
                "pollBaseUrl": poll_base_url,
                "lastRaw": status,
                "lastPollAt": datetime.now(UTC).isoformat(),
            }
            await channel_service.update(channel, {"extra": extra, "last_error": last_error})
            await db.commit()
            continue

        await gateway_service.upsert_wechat_account(
            name="微信 Channel 网关",
            account_id=str(account_id or external_user_id or ""),
            base_url=str(base_url),
            token=str(token),
            is_default=True,
        )
        extra.pop("wechatLogin", None)
        bind_code_expires_at = datetime.now(UTC) + timedelta(minutes=10)
        extra["expiresAt"] = bind_code_expires_at.isoformat()
        qr = dict(extra.get("qr") or {})
        qr["gatewayReady"] = True
        qr["expiresAt"] = bind_code_expires_at.isoformat()
        qr["providerRaw"] = {**dict(qr.get("providerRaw") or {}), "loginStatus": status}
        extra["qr"] = qr
        update_values: dict[str, Any] = {
            "extra": extra,
            "last_error": "微信扫码已确认，请向机器人发送八位关联码完成绑定",
        }
        if external_user_id:
            update_values["external_user_id"] = str(external_user_id)
        await channel_service.update(channel, update_values)
        await db.commit()
        logger.info(
            "message_channel_wechat_gateway_ready_wait_bind_code",
            channel_id=channel.id,
            has_external_user=bool(external_user_id),
        )
        processed += 1
    return processed


def _is_iso_expired(value: str | None) -> bool:
    raw_value = str(value or "").strip()
    if not raw_value:
        return False
    try:
        expires_at = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return datetime.now(UTC) > expires_at


async def poll_pending_feishu_registrations(db: AsyncSession) -> int:
    """Poll Feishu no-credential QR registration flows started from personal settings."""
    channel_service = UserMessageChannelService(db)
    channels, _ = await channel_service.get_list(
        page=1,
        page_size=50,
        where=[
            UserMessageChannel.channel_type == "feishu",
            UserMessageChannel.status == "pending",
        ],
        order_by="id",
        order_desc=False,
        return_total=True,
    )
    await db.commit()
    processed = 0
    for channel in channels:
        extra = dict(channel.extra or {})
        registration = extra.get("feishuRegistration") if isinstance(extra.get("feishuRegistration"), dict) else None
        if not registration:
            continue
        device_code = str(registration.get("deviceCode") or "").strip()
        domain = str(registration.get("domain") or "feishu").strip() or "feishu"
        if not device_code:
            continue
        if _is_iso_expired(registration.get("expiresAt")):
            await channel_service.delete(channel)
            await db.commit()
            processed += 1
            continue

        try:
            data = await poll_feishu_app_registration(device_code=device_code, domain=domain)
        except Exception as exc:  # noqa: BLE001
            extra["feishuRegistration"] = {**registration, "lastError": str(exc), "lastPollAt": datetime.now(UTC).isoformat()}
            await channel_service.update(channel, {"extra": extra})
            await db.commit()
            continue

        error = str(data.get("error") or "").strip()
        if error in {"authorization_pending", "slow_down", ""} and not data.get("client_id"):
            if error:
                extra["feishuRegistration"] = {**registration, "lastError": error, "lastPollAt": datetime.now(UTC).isoformat()}
                await channel_service.update(channel, {"extra": extra})
                await db.commit()
            continue
        if error in {"access_denied", "expired_token"}:
            await channel_service.delete(channel)
            await db.commit()
            processed += 1
            continue
        if error:
            extra["feishuRegistration"] = {**registration, "lastError": error, "lastPollAt": datetime.now(UTC).isoformat()}
            await channel_service.update(channel, {"extra": extra})
            await db.commit()
            continue

        app_id = str(data.get("client_id") or "").strip()
        app_secret = str(data.get("client_secret") or "").strip()
        if not app_id or not app_secret:
            continue
        user_info = data.get("user_info") if isinstance(data.get("user_info"), dict) else {}
        tenant_brand = str(user_info.get("tenant_brand") or "").strip().lower()
        resolved_domain = "lark" if tenant_brand == "lark" else domain
        open_id = str(user_info.get("open_id") or "").strip()

        account = await MessageGatewayAccountService(db).upsert_feishu_account(
            name="飞书 Channel 网关",
            app_id=app_id,
            app_secret=app_secret,
            domain=resolved_domain,
            is_default=True,
        )
        extra.pop("feishuRegistration", None)
        qr = dict(extra.get("qr") or {})
        qr["gatewayReady"] = True
        qr["providerRaw"] = {**dict(qr.get("providerRaw") or {}), "appId": app_id, "domain": resolved_domain}
        extra["qr"] = qr
        if open_id:
            extra["feishuPairing"] = {
                "openId": open_id,
                "appId": app_id,
                "domain": resolved_domain,
                "promptSentAt": datetime.now(UTC).isoformat(),
            }
        channel = await channel_service.update(
            channel,
            {
                "external_user_id": open_id or channel.external_user_id,
                "extra": extra,
                "last_error": None if open_id else "飞书扫码授权已完成，但未返回 open_id，无法发送关联码提示",
            },
        )

        if open_id and channel.bind_token:
            site_brand = await _resolve_channel_site_brand(db, channel)
            await db.commit()
            try:
                from app.domain.notifications.feishu_ws_client import start_feishu_gateway_ws_account

                await start_feishu_gateway_ws_account(
                    account_id=int(account.id),
                    app_id=account.account_id or app_id,
                    app_secret=app_secret,
                    domain=resolved_domain,
                )
            except Exception:
                pass
            try:
                await FeishuClient(
                    app_id=account.account_id or app_id,
                    app_secret=app_secret,
                    domain=resolved_domain,
                ).send_text(
                    open_id=open_id,
                    text=f"{_channel_bind_prompt_text(site_brand)}\n系统收到关联码后会完成账号绑定，后续消息由 AI 助手接管。",
                )
            except Exception as exc:  # noqa: BLE001
                await channel_service.update(channel, {"last_error": f"飞书授权成功，但关联码提示发送失败: {exc}"})
                await db.commit()
        else:
            await db.commit()
        processed += 1
    return processed
