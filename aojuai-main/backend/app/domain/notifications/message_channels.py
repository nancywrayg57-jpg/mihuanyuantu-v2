"""System-level per-user message channels."""

from __future__ import annotations

import re

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import and_, case, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TooManyRequestsError, ValidationError
from app.core.logger import get_logger
from app.domain.notifications.gateway_models import MessageChannelBindGuard
from app.domain.notifications.models import UserMessageChannel
from app.domain.notifications.schemas import UserMessageChannelItem
from app.infrastructure.repository import RepositoryBase
from app.infrastructure.database.portable_sql import dialect_insert, escalate_to_write_lock
from app.infrastructure.database.types import json_array_contains, json_merge_patch

logger = get_logger(__name__)

_ALLOWED_CHANNEL_TYPES = {"wechat", "feishu", "wecom", "webhook"}
_ALLOWED_CHANNEL_STATUS = {"pending", "active", "disabled"}
_GATEWAY_TYPES = {"wechat", "feishu", "wecom"}
_RECENT_INBOUND_CONTEXT_LIMIT = 30
_BIND_FAILURE_LIMIT = 5
_BIND_FAILURE_WINDOW = timedelta(minutes=10)


def _bind_guard_key(
    *, channel_type: str, subject_type: str, subject: str, gateway_account_id: int | None = None
) -> str:
    """绑定限流的键。**必须带网关账号维度。**

    飞书 open_id 是应用级作用域：不同网关账号（不同应用）下同一个人的
    open_id 各不相同，但恶意方可以拿账号 A 的失败尝试去撞账号 B 的限流——
    键里不含账号时，A 账号刷 5 次失败就能把 B 账号下无辜用户的绑定封 10 分钟。
    （codex 终审 #2）account 为空（未知账号）时保持旧键形态，限流退化为
    跨账号共享——宁可误伤也不放行。
    """
    account_part = str(int(gateway_account_id)) if gateway_account_id else "-"
    normalized = f"{channel_type.strip().lower()}\n{account_part}\n{subject_type}\n{subject.strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()


def _channel_delivery_error(exc: Exception, *, provider: str) -> tuple[bool, str]:
    message = str(exc).strip() or f"{provider} Channel 发送失败"
    if provider == "wechat":
        message = _wechat_delivery_error_message(exc, for_test=False)
    logger.warning(
        "message_channel_gateway_delivery_failed",
        provider=provider,
        error_type=type(exc).__name__,
        error=message,
    )
    return False, message


def _is_wechat_stale_context_error(exc: Exception) -> bool:
    lowered = str(exc).strip().lower()
    return "sendmessage failed" in lowered and (
        "ret=-2" in lowered or "ret': -2" in lowered or 'ret": -2' in lowered
    )


def _wechat_delivery_error_message(exc: Exception, *, for_test: bool) -> str:
    message = str(exc).strip()
    if _is_wechat_stale_context_error(exc):
        suffix = "，再点击测试" if for_test else "后重试"
        return f"微信会话已过期，请先在微信 Channel 中发送一条新消息刷新会话{suffix}。"
    return message or ("微信 Channel 测试发送失败" if for_test else "微信 Channel 发送失败")


def _wechat_test_delivery_error_message(exc: Exception) -> str:
    return _wechat_delivery_error_message(exc, for_test=True)


def _is_wechat_dedupe_token(value: Any) -> bool:
    return str(value or "").strip().lower().startswith("wechat:")


def _normalize_wechat_context_token(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized or _is_wechat_dedupe_token(normalized):
        return ""
    return normalized


def _append_wechat_context_token(tokens: list[str], value: Any) -> None:
    normalized = _normalize_wechat_context_token(value)
    if normalized and normalized not in tokens:
        tokens.append(normalized)


def _wechat_send_context_tokens(channel: UserMessageChannel) -> list[str]:
    channel_extra = getattr(channel, "extra", None)
    extra = channel_extra if isinstance(channel_extra, dict) else {}
    last_inbound = extra.get("lastInbound") if isinstance(extra.get("lastInbound"), dict) else {}
    preferred_tokens: list[str] = []
    _append_wechat_context_token(preferred_tokens, last_inbound.get("context_token"))
    _append_wechat_context_token(preferred_tokens, last_inbound.get("contextToken"))
    _append_wechat_context_token(preferred_tokens, extra.get("lastInboundContextToken"))
    for value in _recent_context_tokens(extra):
        _append_wechat_context_token(preferred_tokens, value)
    _append_wechat_context_token(preferred_tokens, getattr(channel, "context_token", None))
    if "" not in preferred_tokens:
        preferred_tokens.append("")
    return preferred_tokens


def select_unambiguous_inbound_channel(
    channels: list[UserMessageChannel],
    *,
    conversation_id: str | None = None,
) -> UserMessageChannel | None:
    """Pick a bound channel only when the external conversation maps unambiguously."""
    if not channels:
        return None
    normalized_conversation_id = str(conversation_id or "").strip()
    if not normalized_conversation_id:
        return channels[0] if len(channels) == 1 else None

    exact_matches = [
        channel
        for channel in channels
        if str(channel.conversation_id or "").strip() == normalized_conversation_id
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return None

    null_matches = [
        channel
        for channel in channels
        if not str(channel.conversation_id or "").strip()
    ]
    return null_matches[0] if len(null_matches) == 1 and len(channels) == 1 else None


def _recent_context_tokens(extra: dict[str, Any]) -> list[str]:
    values = extra.get("recentInboundContextTokens")
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item or "").strip()]


def _record_context_token(extra: dict[str, Any], context_token: str | None) -> dict[str, Any]:
    normalized = str(context_token or "").strip()
    if not normalized:
        return extra
    tokens = [token for token in _recent_context_tokens(extra) if token != normalized]
    extra["recentInboundContextTokens"] = [normalized, *tokens][:_RECENT_INBOUND_CONTEXT_LIMIT]
    extra["lastInboundContextToken"] = normalized
    if str(extra.get("retryInboundDedupeToken") or "").strip() == normalized:
        extra.pop("retryInboundDedupeToken", None)
        extra.pop("retryInboundReason", None)
    return extra


def _extract_inbound_origin_time(payload: dict[str, Any] | None) -> datetime | None:
    """从入站载荷里取消息的真实发生时间。取不到返回 None。

    微信（iLink）把它放在 `item_list[0].create_time_ms`（毫秒）——
    这个字段本来就在载荷里，此前只被用来构造去重键。
    其它渠道暂无对应字段；返回 None 时调用方回落到处理时间。
    """
    if not isinstance(payload, dict):
        return None
    item_list = payload.get("item_list")
    if isinstance(item_list, list) and item_list and isinstance(item_list[0], dict):
        raw = item_list[0].get("create_time_ms")
        try:
            millis = int(str(raw).strip())
        except (TypeError, ValueError):
            return None
        if millis <= 0:
            return None
        return datetime.fromtimestamp(millis / 1000, tz=UTC)
    return None


def _scrub_urls(text: str) -> str:
    """把错误文案里的 URL 连同其路径/query 一起抹掉。

    只留下域名之前的部分没有意义——凭据恰恰在路径和 query 里。
    """
    return re.sub(r"https?://\S+", "<url>", str(text or ""))[:500]


class UserMessageChannelService(RepositoryBase[UserMessageChannel]):
    """Manage current user's system-level personal message channels."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, UserMessageChannel)

    async def list_user_channels(self, *, user_id: int) -> list[UserMessageChannel]:
        channels, _ = await self.get_list(
            page=1,
            page_size=100,
            where=[UserMessageChannel.user_id == user_id],
            order_by="id",
            order_desc=False,
            return_total=True,
        )
        return channels

    async def get_user_channel(self, channel_id: int, *, user_id: int) -> UserMessageChannel | None:
        return await self.get_one(where=[UserMessageChannel.id == channel_id, UserMessageChannel.user_id == user_id])

    async def list_user_channels_by_type(
        self,
        *,
        user_id: int,
        channel_type: str,
        statuses: list[str] | None = None,
    ) -> list[UserMessageChannel]:
        where = [
            UserMessageChannel.user_id == user_id,
            UserMessageChannel.channel_type == channel_type,
        ]
        if statuses:
            where.append(UserMessageChannel.status.in_(statuses))
        channels, _ = await self.get_list(
            page=1,
            page_size=20,
            where=where,
            order_by="id",
            order_desc=True,
            return_total=True,
        )
        return channels

    async def get_active_channels(self, *, user_id: int, message_type: str | None = None) -> list[UserMessageChannel]:
        where = [UserMessageChannel.user_id == user_id, UserMessageChannel.status == "active"]
        if message_type:
            where.append(json_array_contains(UserMessageChannel.message_types, message_type))
        channels, _ = await self.get_list(
            page=1,
            page_size=100,
            where=where,
            order_by="is_default",
            order_desc=True,
            return_total=True,
        )
        return channels

    async def create_manual_channel(
        self,
        *,
        user_id: int,
        channel_type: str,
        name: str,
        target: str | None,
        secret: str | None,
        status: str,
        is_default: bool,
        message_types: list[str] | None,
        extra: dict[str, Any] | None,
    ) -> UserMessageChannel:
        self._validate_channel_payload(channel_type=channel_type, status=status, target=target)
        if is_default:
            await self._clear_defaults(user_id=user_id)
        return await self.create(
            {
                "user_id": user_id,
                "channel_type": channel_type,
                "name": name,
                "target": target,
                "secret": secret,
                "status": status,
                "is_default": is_default,
                "message_types": message_types or ["notification"],
                "extra": extra or {},
            }
        )

    async def update_user_channel(
        self,
        channel: UserMessageChannel,
        *,
        name: str,
        status: str,
        is_default: bool,
        message_types: list[str] | None,
        target: str | None = None,
        secret: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> UserMessageChannel:
        self._validate_channel_payload(channel_type=channel.channel_type, status=status, target=target or channel.target)
        if is_default:
            await self._clear_defaults(user_id=channel.user_id, exclude_id=channel.id)
        return await self.update(
            channel,
            {
                "name": name,
                "target": target if target is not None else channel.target,
                "secret": secret if secret is not None else channel.secret,
                "status": status,
                "is_default": is_default,
                "message_types": message_types or channel.message_types or ["notification"],
                "extra": extra if extra is not None else channel.extra,
                "last_error": None if status == "active" else channel.last_error,
            },
        )

    async def bind_inbound_message(
        self,
        *,
        gateway_account_id: int | None = None,
        bind_token: str,
        channel_type: str,
        external_user_id: str,
        conversation_id: str | None,
        context_token: str | None,
        display_name: str | None = None,
        avatar: str | None = None,
        raw_payload: dict[str, Any] | None = None,
        attempt_source: str | None = None,
    ) -> UserMessageChannel | None:
        normalized_external_user_id = str(external_user_id or "").strip()
        subject_guard_key = _bind_guard_key(
            channel_type=channel_type,
            subject_type="external-user",
            subject=normalized_external_user_id or "unknown",
            gateway_account_id=gateway_account_id,
        )
        guard_keys = [subject_guard_key]
        normalized_attempt_source = str(attempt_source or "").strip()
        if normalized_attempt_source:
            guard_keys.append(
                _bind_guard_key(
                    channel_type=channel_type,
                    subject_type="request-source",
                    subject=normalized_attempt_source,
                    gateway_account_id=gateway_account_id,
                )
            )
        await self._enforce_bind_rate_limit(channel_type=channel_type, guard_keys=guard_keys)

        await escalate_to_write_lock(self.db)
        result = await self.db.execute(
            select(UserMessageChannel)
            .where(
                UserMessageChannel.bind_token == bind_token,
                UserMessageChannel.channel_type == channel_type,
                UserMessageChannel.status == "pending",
                UserMessageChannel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        channel = result.scalar_one_or_none()
        if not channel:
            await self._record_failed_bind_attempt(channel_type=channel_type, guard_keys=guard_keys)
            return None
        if self._is_bind_expired(channel):
            await self.update(channel, {"status": "disabled", "last_error": "绑定码已过期"})
            await self._record_failed_bind_attempt(channel_type=channel_type, guard_keys=guard_keys)
            return None
        now = datetime.now(UTC)
        if normalized_external_user_id:
            await self.db.execute(
                update(UserMessageChannel)
                .where(
                    UserMessageChannel.id != channel.id,
                    UserMessageChannel.channel_type == channel_type,
                    UserMessageChannel.external_user_id == normalized_external_user_id,
                    UserMessageChannel.status == "active",
                    UserMessageChannel.deleted_at.is_(None),
                    # 只影响**同一网关账号**下的渠道：飞书 open_id 是应用级
                    # 作用域，账号 A 下的绑定不该禁用账号 B（可能是另一租户）
                    # 下同 ID 的渠道。（codex 终审 #2）存量 NULL 视为"当时的
                    # 默认账号"，与当前账号或 NULL 匹配才禁用。
                    or_(
                        UserMessageChannel.gateway_account_id == gateway_account_id,
                        UserMessageChannel.gateway_account_id.is_(None),
                    )
                    if gateway_account_id is not None
                    else UserMessageChannel.gateway_account_id.is_(None),
                )
                .values(
                    status="disabled",
                    is_default=False,
                    bind_token=None,
                    last_error="同一外部 Channel 身份已重新绑定到其他账号",
                    updated_at=now,
                )
            )
        extra = dict(channel.extra or {})
        extra.pop("bindingCode", None)
        extra.pop("bindCode", None)
        await self.db.execute(
            delete(MessageChannelBindGuard).where(MessageChannelBindGuard.guard_key == subject_guard_key)
        )
        if raw_payload:
            extra["lastInbound"] = raw_payload
            # 上游消息的**发生时间**，不是我们处理它的时间。会话 TTL 从用户
            # 说话那一刻起算；网关停机后补拉旧消息时，用处理时间会把过期时间
            # 高估几小时——提醒发出去时 token 其实已经失效。（codex 复核发现）
            origin_at = _extract_inbound_origin_time(raw_payload)
            if origin_at is not None:
                extra["lastInboundOriginAt"] = origin_at.isoformat()
        wecom_bot = extra.get("wecomBot") if channel_type == "wecom" and isinstance(extra.get("wecomBot"), dict) else None
        if wecom_bot:
            wecom_bot["boundExternalUserId"] = normalized_external_user_id
            wecom_bot["boundConversationId"] = conversation_id
            extra["wecomBot"] = wecom_bot
        extra = _record_context_token(extra, context_token)
        return await self.update(
            channel,
            {
                "bind_token": None,
                "external_user_id": external_user_id,
                "conversation_id": conversation_id,
                "context_token": context_token,
                "display_name": display_name,
                "avatar": avatar,
                "status": "active",
                "bound_at": now,
                "last_inbound_at": now,
                "extra": extra,
                # 记下是哪个网关账号绑的：此后只有它能驱动这条渠道。
                # 不记的话，签名只能证明"某个合法网关"，而网关账号是全局共享的
                # （表上没有 tenant_id），持 A 密钥即可声称任意用户身份。
                "gateway_account_id": int(gateway_account_id) if gateway_account_id else None,
            },
        )

    async def _enforce_bind_rate_limit(self, *, channel_type: str, guard_keys: list[str]) -> None:
        now = datetime.now(UTC)
        await self.db.execute(delete(MessageChannelBindGuard).where(MessageChannelBindGuard.expires_at <= now))
        result = await self.db.execute(
            select(MessageChannelBindGuard).where(
                MessageChannelBindGuard.guard_key.in_(guard_keys),
                MessageChannelBindGuard.blocked_until.is_not(None),
                MessageChannelBindGuard.blocked_until > now,
            )
        )
        blocked = result.scalars().first()
        if not blocked:
            return
        logger.warning(
            "message_channel_bind_rate_limited",
            security_event="binding_code_rate_limit",
            channel_type=channel_type,
            source_fingerprint=blocked.guard_key[:12],
            failure_count=blocked.failure_count,
            rate_limited=True,
        )
        raise TooManyRequestsError(message="关联码尝试过于频繁，请稍后重试")

    async def _record_failed_bind_attempt(self, *, channel_type: str, guard_keys: list[str]) -> None:
        now = datetime.now(UTC)
        expires_at = now + _BIND_FAILURE_WINDOW
        max_failure_count = 0
        for guard_key in guard_keys:
            stmt = (
                dialect_insert(MessageChannelBindGuard)
                .values(
                    guard_key=guard_key,
                    failure_count=1,
                    blocked_until=None,
                    expires_at=expires_at,
                )
                .on_conflict_do_update(
                    index_elements=[MessageChannelBindGuard.guard_key],
                    index_where=MessageChannelBindGuard.deleted_at.is_(None),
                    set_={
                        "failure_count": MessageChannelBindGuard.failure_count + 1,
                        "blocked_until": case(
                            (
                                MessageChannelBindGuard.failure_count + 1 >= _BIND_FAILURE_LIMIT,
                                expires_at,
                            ),
                            else_=MessageChannelBindGuard.blocked_until,
                        ),
                        "expires_at": expires_at,
                    },
                )
                .returning(MessageChannelBindGuard.failure_count)
            )
            failure_count = int((await self.db.execute(stmt)).scalar_one())
            max_failure_count = max(max_failure_count, failure_count)
        logger.warning(
            "message_channel_bind_failed",
            security_event="binding_code_failure",
            channel_type=channel_type,
            source_fingerprint=guard_keys[0][:12],
            failure_count=max_failure_count,
            failure_limit=_BIND_FAILURE_LIMIT,
            rate_limited=max_failure_count >= _BIND_FAILURE_LIMIT,
        )

    async def _is_default_gateway_account(
        self, *, channel_type: str, gateway_account_id: int
    ) -> bool:
        """这个网关账号是不是该渠道类型的默认账号。

        只有默认账号有权认领 `gateway_account_id IS NULL` 的存量渠道。
        """
        from app.domain.notifications.gateway_models import MessageGatewayAccount

        row = await self.db.scalar(
            select(MessageGatewayAccount.id).where(
                MessageGatewayAccount.id == int(gateway_account_id),
                MessageGatewayAccount.channel_type == channel_type,
                MessageGatewayAccount.is_default.is_(True),
                MessageGatewayAccount.deleted_at.is_(None),
            )
        )
        return row is not None

    async def find_active_inbound_channel(
        self,
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
        ]
        # **按网关账号限定归属。**
        #
        # 签名只证明"某个合法网关"，不证明"这个用户所属的网关"。
        # 而网关账号表没有 tenant_id、是全局共享的，同一渠道类型可以有多个 active
        # 账号——所以不限定的话，持有账号 A 密钥的运行时可以声称任意
        # external_user_id，驱动**任何租户**下匹配到的渠道。（codex 复核发现）
        #
        # `gateway_account_id IS NULL` 是存量数据：本次改动之前绑定的渠道没有
        # 这个字段。**存量只允许默认账号认领**——存量渠道本来就是"只有默认账号"
        # 时代绑定的，归属只可能是它。放开给任意合法账号的话，账号 A 可以用
        # 受害者的 external ID 认领账号 B 的存量渠道并驱动其 AI 助手：
        # HMAC 只证明"来自某个合法网关"，不证明"这个用户所属的网关"。
        # （codex 终审 #1）
        if gateway_account_id is not None:
            account_scope = UserMessageChannel.gateway_account_id == gateway_account_id
            if await self._is_default_gateway_account(
                channel_type=channel_type, gateway_account_id=gateway_account_id
            ):
                account_scope = account_scope | UserMessageChannel.gateway_account_id.is_(None)
            where.append(account_scope)
        normalized_conversation_id = str(conversation_id or "").strip()
        if normalized_conversation_id:
            where.append(
                (UserMessageChannel.conversation_id == normalized_conversation_id)
                | UserMessageChannel.conversation_id.is_(None)
            )
        channels, _ = await self.get_list(
            page=1,
            page_size=3,
            where=where,
            order_by="last_inbound_at",
            order_desc=True,
            return_total=True,
        )
        return select_unambiguous_inbound_channel(channels, conversation_id=normalized_conversation_id)

    async def record_inbound_message(
        self,
        channel: UserMessageChannel,
        *,
        gateway_account_id: int | None = None,
        context_token: str | None = None,
        inbound_dedupe_token: str | None = None,
        conversation_id: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> UserMessageChannel:
        extra = dict(channel.extra or {})
        if raw_payload:
            extra["lastInbound"] = raw_payload
            # 上游消息的**发生时间**，不是我们处理它的时间。会话 TTL 从用户
            # 说话那一刻起算；网关停机后补拉旧消息时，用处理时间会把过期时间
            # 高估几小时——提醒发出去时 token 其实已经失效。（codex 复核发现）
            origin_at = _extract_inbound_origin_time(raw_payload)
            if origin_at is not None:
                extra["lastInboundOriginAt"] = origin_at.isoformat()
        if inbound_dedupe_token:
            extra = _record_context_token(extra, inbound_dedupe_token)
        if context_token and context_token != inbound_dedupe_token:
            extra = _record_context_token(extra, context_token)
        values: dict[str, Any] = {
            "conversation_id": conversation_id if conversation_id is not None else channel.conversation_id,
            "context_token": context_token if context_token is not None else channel.context_token,
            "last_inbound_at": datetime.now(UTC),
            "extra": extra,
        }
        if gateway_account_id is not None and channel.gateway_account_id is None:
            # **认领存量渠道。** 本次改动之前绑定的渠道没有这个字段；
            # 第一次经过签名鉴权的入站把它认下来，此后只有同一个账号能驱动它。
            values["gateway_account_id"] = int(gateway_account_id)
        updated = await self.update(channel, values)
        # 会话刷新 → 把这个渠道上"保留"的中转消息放回队列自动补发。
        # 中转模块可被部署关闭；失败只记日志，不影响入站本身。
        try:
            from app.domain.notifications.channel_renewal import hold_enabled

            if hold_enabled(updated):
                from app.domain.message_relay.service import MessageRelayService

                await MessageRelayService(self.db).requeue_held_for_channel(
                    user_id=int(updated.user_id), channel_id=int(updated.id)
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("message_relay_held_requeue_failed", channel_id=int(channel.id), error=str(exc))
        return updated

    async def merge_extra(self, channel: UserMessageChannel, patch: dict[str, Any]) -> None:
        """只改 `extra` 里的这几个键，**不做读-改-写**。

        读-改-写的问题不是窗口大小，是它必然存在：先把 `extra` 读进内存、
        中间做一件耗时的事（比如等外部 HTTP 返回）、再整个写回去——
        期间任何入站写入（新的 context token、`lastInboundOriginAt`、
        助手会话）都会被这份陈旧快照覆盖。"把已有内容一起带上"只是让窗口变窄，
        并不能消除它。（codex 复核发现）

        PostgreSQL 的 `||` 是在数据库里做合并，读到的永远是当前值。
        """
        if not patch:
            return
        await self.db.execute(
            update(UserMessageChannel)
            .where(UserMessageChannel.id == channel.id)
            .values(extra=json_merge_patch(UserMessageChannel.extra, patch))
        )
        # 让内存里的对象跟上，免得同一请求内后续读到旧值
        channel.extra = {**(channel.extra or {}), **patch}

    async def set_delivery_result(self, channel: UserMessageChannel, *, ok: bool, error: str | None = None) -> None:
        values: dict[str, Any] = {"last_error": None if ok else (error or "发送失败")[:2000]}
        if ok:
            values["last_sent_at"] = datetime.now(UTC)
        await self.update(channel, values)

    async def test_channel_delivery(
        self,
        channel: UserMessageChannel,
        *,
        title: str,
        content: str | None,
    ) -> tuple[bool, str]:
        if channel.channel_type == "wechat":
            return await self._test_wechat_delivery(channel, title=title, content=content)
        return await self.deliver_to_channel(
            channel,
            title=title,
            content=content,
            message_type="notification",
            extra={"source": "personal_settings_test"},
        )

    async def deliver_to_channel(
        self,
        channel: UserMessageChannel,
        *,
        title: str,
        content: str | None,
        message_type: str = "notification",
        extra: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        if channel.status != "active":
            return False, "Channel 未激活"
        if message_type and channel.message_types and message_type not in channel.message_types:
            return False, f"Channel 未订阅消息类型: {message_type}"

        if channel.channel_type == "webhook":
            return await self._deliver_webhook(channel, title=title, content=content, message_type=message_type, extra=extra or {})
        if channel.channel_type in _GATEWAY_TYPES:
            return await self._deliver_gateway(channel, title=title, content=content, message_type=message_type, extra=extra or {})
        return False, f"不支持的 Channel 类型: {channel.channel_type}"

    async def _deliver_gateway(
        self,
        channel: UserMessageChannel,
        *,
        title: str,
        content: str | None,
        message_type: str,
        extra: dict[str, Any],
    ) -> tuple[bool, str]:
        if channel.channel_type == "wechat":
            from app.core.provider_secrets import decrypt_provider_secret_or_plain
            from app.domain.notifications.gateway_service import MessageGatewayAccountService
            from app.domain.notifications.ilink_client import WechatIlinkClient

            account = await MessageGatewayAccountService(self.db).resolve_for_channel(
                "wechat", gateway_account_id=getattr(channel, "gateway_account_id", None)
            )
            if not account:
                return False, "系统未配置可用微信网关账号"
            token = decrypt_provider_secret_or_plain(account.token_encrypted)
            if not token or not account.base_url:
                return False, "微信网关账号缺少 token 或 baseUrl"
            if not channel.external_user_id:
                return False, "微信 Channel 尚未完成入站绑定"
            text = f"{title}\n\n{content}" if content else title
            client = WechatIlinkClient(base_url=account.base_url, token=token)
            last_exc: Exception | None = None
            for context_token in _wechat_send_context_tokens(channel):
                try:
                    await client.send_text(
                        to_user_id=channel.external_user_id,
                        text=text,
                        context_token=context_token or None,
                    )
                    return True, "发送成功"
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    logger.warning(
                        "message_channel_wechat_delivery_send_failed",
                        channel_id=getattr(channel, "id", None),
                        context_token_preview=context_token[:120],
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    if _is_wechat_stale_context_error(exc):
                        continue
                    break
            if last_exc:
                return _channel_delivery_error(last_exc, provider="wechat")
            return False, "微信 Channel 发送失败"

        if channel.channel_type == "feishu":
            from app.core.provider_secrets import decrypt_provider_secret_or_plain
            from app.domain.notifications.feishu_client import FeishuClient
            from app.domain.notifications.gateway_service import MessageGatewayAccountService

            account = await MessageGatewayAccountService(self.db).resolve_for_channel(
                "feishu", gateway_account_id=getattr(channel, "gateway_account_id", None)
            )
            if not account:
                # 绑定账号已停用时飞书刻意不回落（open_id 应用级作用域，
                # 换账号必错投），这里把"该重绑"说给用户听
                return False, (
                    "该飞书 Channel 绑定的网关账号已停用或删除，"
                    "请在个人设置里重新绑定后再发送"
                    if getattr(channel, "gateway_account_id", None)
                    else "系统未配置可用飞书网关账号"
                )
            app_secret = decrypt_provider_secret_or_plain(account.token_encrypted)
            if not app_secret or not account.account_id:
                return False, "飞书网关账号缺少 appId 或 appSecret"
            if not channel.external_user_id:
                return False, "飞书 Channel 尚未完成入站绑定"
            text = f"{title}\n\n{content}" if content else title
            try:
                await FeishuClient(
                    app_id=account.account_id,
                    app_secret=app_secret,
                    domain=str((account.extra or {}).get("domain") or account.base_url or "feishu"),
                ).send_text(open_id=channel.external_user_id, text=text)
            except Exception as exc:  # noqa: BLE001
                return _channel_delivery_error(exc, provider="feishu")
            return True, "发送成功"

        if channel.channel_type == "wecom":
            from app.core.provider_secrets import decrypt_provider_secret_or_plain

            if not channel.external_user_id:
                return False, "企业微信 Channel 尚未完成入站绑定"
            extra_config = channel.extra or {}
            wecom_bot = extra_config.get("wecomBot") if isinstance(extra_config.get("wecomBot"), dict) else {}
            bot_id = str(wecom_bot.get("botId") or channel.external_user_id or "").strip()
            bot_secret = decrypt_provider_secret_or_plain(channel.secret)
            gateway_url = str(extra_config.get("gatewayUrl") or extra_config.get("gateway_url") or "").strip()
            target = channel.conversation_id or channel.external_user_id
            if not gateway_url:
                from app.domain.notifications.wecom_ws_client import send_wecom_channel_text

                try:
                    return await send_wecom_channel_text(
                        channel_id=int(channel.id),
                        chat_id=str(target or ""),
                        text=f"{title}\n\n{content}" if content else title,
                    )
                except Exception as exc:  # noqa: BLE001
                    return _channel_delivery_error(exc, provider="wecom")
            payload = self._build_gateway_payload(
                channel,
                title=title,
                content=content,
                message_type=message_type,
                extra={
                    **extra,
                    "accountId": bot_id,
                    "botId": bot_id,
                    "gatewayMode": str(extra_config.get("gatewayMode") or "wecom_bot"),
                },
            )
            payload.update(
                {
                    "channel": "wecom",
                    "to": target,
                    "accountId": bot_id,
                    "delivery": {
                        "mode": "announce",
                        "channel": "wecom",
                        "to": f"wecom:{target}" if target else None,
                        "accountId": bot_id,
                    },
                    "wecomBot": {
                        "channel": "wecom",
                        "target": target,
                        "botId": bot_id,
                        "body": {
                            "msgtype": "markdown",
                            "markdown": {"content": payload.get("text") or ""},
                        },
                    },
                }
            )
            return await self._post_json(gateway_url, payload, bot_secret)

        gateway_url = str((channel.extra or {}).get("gatewayUrl") or (channel.extra or {}).get("gateway_url") or "").strip()
        if not gateway_url:
            return False, "暂未配置该 Channel 类型的内置网关"
        payload = self._build_gateway_payload(channel, title=title, content=content, message_type=message_type, extra=extra)
        return await self._post_json(gateway_url, payload, channel.secret)

    async def _test_wechat_delivery(
        self,
        channel: UserMessageChannel,
        *,
        title: str,
        content: str | None,
    ) -> tuple[bool, str]:
        from app.core.provider_secrets import decrypt_provider_secret_or_plain
        from app.domain.notifications.gateway_service import MessageGatewayAccountService
        from app.domain.notifications.ilink_client import WechatIlinkClient

        if channel.status != "active":
            return False, "Channel 未激活"
        if not channel.external_user_id:
            return False, "微信 Channel 尚未完成入站绑定"

        # 与真实投递同一条解析路径：优先渠道绑定的账号，而不是当前默认账号。
        # 测试用默认、真实用绑定的话，测试通过≠真实能发——测试结果失去意义。
        # （codex 终审 #14）
        account = await MessageGatewayAccountService(self.db).resolve_for_channel(
            "wechat", gateway_account_id=getattr(channel, "gateway_account_id", None)
        )
        if not account:
            return False, "系统未配置可用微信网关账号"
        token = decrypt_provider_secret_or_plain(account.token_encrypted)
        if not token or not account.base_url:
            return False, "微信网关账号缺少 token 或 baseUrl"

        text = f"{title}\n\n{content}" if content else title
        client = WechatIlinkClient(base_url=account.base_url, token=token)
        last_exc: Exception | None = None
        for context_token in _wechat_send_context_tokens(channel):
            try:
                await client.send_text(
                    to_user_id=channel.external_user_id,
                    text=text,
                    context_token=context_token or None,
                )
                return True, "发送成功"
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "message_channel_wechat_test_send_failed",
                    channel_id=getattr(channel, "id", None),
                    context_token_preview=context_token[:120],
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                if _is_wechat_stale_context_error(exc):
                    continue
                break

        return False, _wechat_test_delivery_error_message(last_exc or RuntimeError("微信 Channel 测试发送失败"))

    async def _deliver_webhook(
        self,
        channel: UserMessageChannel,
        *,
        title: str,
        content: str | None,
        message_type: str,
        extra: dict[str, Any],
    ) -> tuple[bool, str]:
        url = (channel.target or "").strip()
        if not url:
            return False, "未配置 Webhook 地址"
        payload = self._build_webhook_payload(channel, title=title, content=content, message_type=message_type, extra=extra)
        return await self._post_json(url, payload, channel.secret)

    async def _post_json(self, url: str, payload: dict[str, Any], secret: str | None) -> tuple[bool, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("message_channel_delivery_failed", error=str(exc))
            # httpx 异常文案通常带完整 URL（用户可能把 secret 放在路径或 query 里），
            # 而这条错误会写进 target_snapshot、再被 relay 状态查询接口返回给
            # 只持 relay scope 的外部应用。落库前把 URL 抹掉。（codex 终审 #6）
            return False, _scrub_urls(str(exc))
        return True, "发送成功"

    @staticmethod
    def _build_gateway_payload(
        channel: UserMessageChannel,
        *,
        title: str,
        content: str | None,
        message_type: str,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        text = f"{title}\n\n{content}" if content else title
        return {
            "channelType": channel.channel_type,
            "messageType": message_type,
            "externalUserId": channel.external_user_id,
            "conversationId": channel.conversation_id,
            "contextToken": channel.context_token,
            "text": text,
            "title": title,
            "content": content or "",
            "extra": extra,
        }

    @staticmethod
    def _build_webhook_payload(
        channel: UserMessageChannel,
        *,
        title: str,
        content: str | None,
        message_type: str,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        text = f"{title}\n\n{content}" if content else title
        if channel.channel_type == "feishu":
            return {"msg_type": "text", "content": {"text": text}}
        return {"messageType": message_type, "title": title, "content": content or "", "text": text, "extra": extra}

    async def _clear_defaults(self, *, user_id: int, exclude_id: int | None = None) -> None:
        conditions = [
            UserMessageChannel.user_id == user_id,
            UserMessageChannel.is_default.is_(True),
            UserMessageChannel.deleted_at.is_(None),
        ]
        if exclude_id is not None:
            conditions.append(UserMessageChannel.id != exclude_id)
        stmt = update(UserMessageChannel).where(and_(*conditions)).values(is_default=False)
        await self.db.execute(stmt)
        await self.db.flush()

    @staticmethod
    def _validate_channel_payload(*, channel_type: str, status: str, target: str | None) -> None:
        if channel_type not in _ALLOWED_CHANNEL_TYPES:
            raise ValidationError(message="不支持的 Channel 类型")
        if status not in _ALLOWED_CHANNEL_STATUS:
            raise ValidationError(message="不支持的 Channel 状态")
        if channel_type == "webhook" and not str(target or "").strip():
            raise ValidationError(message="Webhook Channel 必须填写目标地址")

    @staticmethod
    def _is_bind_expired(channel: UserMessageChannel) -> bool:
        raw_expires_at = str((channel.extra or {}).get("expiresAt") or "").strip()
        if not raw_expires_at:
            return False
        try:
            expires_at = datetime.fromisoformat(raw_expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return datetime.now(UTC) > expires_at

    @staticmethod
    def to_item(channel: UserMessageChannel) -> dict[str, Any]:
        data = UserMessageChannelItem.model_validate(channel).model_dump(by_alias=True, exclude_none=False)
        if channel.secret:
            data["secretConfigured"] = True
        return data


async def deliver_notification_to_user_channels(
    db: AsyncSession,
    *,
    user_id: int,
    title: str,
    content: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Best-effort fan-out from persisted site notification to user-bound message channels."""
    service = UserMessageChannelService(db)
    channels = await service.get_active_channels(user_id=user_id, message_type="notification")
    for channel in channels:
        ok, message = await service.deliver_to_channel(
            channel,
            title=title,
            content=content,
            message_type="notification",
            extra=extra,
        )
        await service.set_delivery_result(channel, ok=ok, error=None if ok else message)
