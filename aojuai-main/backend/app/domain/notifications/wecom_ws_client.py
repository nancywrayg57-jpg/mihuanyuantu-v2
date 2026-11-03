"""Enterprise WeChat personal bot WebSocket receiver."""

from __future__ import annotations

import asyncio
import json
import secrets
import ssl
import time
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

import certifi
import httpx
import websockets
from sqlalchemy import select

from app.core.logger import get_logger
from app.core.provider_secrets import decrypt_provider_secret_or_plain
from app.domain.notifications.models import UserMessageChannel
from app.domain.notifications.wecom_qrcode import WECOM_BOT_WS_URL
from app.infrastructure.database.session import get_db_context

logger = get_logger(__name__)

_WS_TASKS: dict[int, asyncio.Task[None]] = {}
_WS_RUNNERS: dict[int, _WecomWsRunner] = {}
_WS_SIGNATURES: dict[int, tuple[str, str, str]] = {}
_WS_EVENT_TASKS: set[asyncio.Task[None]] = set()
_BIND_CODE_READY_MINUTES = 10

_CMD_SUBSCRIBE = "aibot_subscribe"
_CMD_HEARTBEAT = "ping"
_CMD_CALLBACK = "aibot_msg_callback"
_CMD_LEGACY_CALLBACK = "aibot_callback"
_CMD_EVENT_CALLBACK = "aibot_event_callback"
_CMD_RESPONSE = "aibot_respond_msg"
_CMD_RESPONSE_WELCOME = "aibot_respond_welcome_msg"
_CMD_SEND_MSG = "aibot_send_msg"
_FINAL_REPLY_ACK_TIMEOUT_SECONDS = 6.0
_RESPONSE_URL_TIMEOUT_SECONDS = 8.0


def _wecom_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _generate_req_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}-{secrets.token_hex(4)}"


def _headers(frame: dict[str, Any]) -> dict[str, Any]:
    return frame.get("headers") if isinstance(frame.get("headers"), dict) else {}


def _frame_req_id(frame: dict[str, Any]) -> str:
    return str(_headers(frame).get("req_id") or "").strip()


def _trim_message_text(value: str, *, max_chars: int = 18000) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n\n...（内容过长，已截断）"


def _error_message(exc: BaseException | None) -> str:
    if exc is None:
        return "unknown error"
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _response_url_from_frame(frame: dict[str, Any]) -> str:
    body = frame.get("body") if isinstance(frame.get("body"), dict) else {}
    return str(body.get("response_url") or body.get("responseUrl") or "").strip()


class _WecomWsRunner:
    def __init__(self, *, channel_id: int, bot_id: str, secret: str, ws_url: str):
        self.channel_id = channel_id
        self.bot_id = bot_id
        self.secret = secret
        self.ws_url = ws_url or WECOM_BOT_WS_URL
        self.stop_event = asyncio.Event()
        self.authenticated = asyncio.Event()
        self.websocket: Any = None
        self.send_lock = asyncio.Lock()
        self.pending_acks: dict[str, asyncio.Future[dict[str, Any]]] = {}

    async def run_forever(self) -> None:
        backoff = 1.0
        while not self.stop_event.is_set():
            try:
                await self._run_once()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                if self.stop_event.is_set():
                    break
                self.authenticated.clear()
                error = _error_message(exc)
                logger.warning("wecom_ws_disconnected", channel_id=self.channel_id, error=error)
                await self._record_runtime_state("disconnected", error=error)
                await asyncio.sleep(min(backoff, 30.0))
                backoff = min(backoff * 2, 30.0)

    async def _run_once(self) -> None:
        logger.info("wecom_ws_connecting", channel_id=self.channel_id, bot_id=self.bot_id[:12])
        async with websockets.connect(self.ws_url, ping_interval=None, ssl=_wecom_ssl_context()) as websocket:
            self.websocket = websocket
            self.authenticated.clear()
            await self._send_auth()
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            try:
                async for message in websocket:
                    await self._handle_raw_message(message)
                    if self.stop_event.is_set():
                        break
            finally:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task
                self.websocket = None
                self.authenticated.clear()
                self._fail_pending(RuntimeError("WeCom WebSocket disconnected"))

    async def _send_auth(self) -> None:
        req_id = _generate_req_id(_CMD_SUBSCRIBE)
        await self._send_frame(
            {
                "cmd": _CMD_SUBSCRIBE,
                "headers": {"req_id": req_id},
                "body": {"bot_id": self.bot_id, "secret": self.secret},
            }
        )

    async def _heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(30)
            if not self.authenticated.is_set():
                continue
            with suppress(Exception):
                await self._send_frame({"cmd": _CMD_HEARTBEAT, "headers": {"req_id": _generate_req_id(_CMD_HEARTBEAT)}})

    async def _handle_raw_message(self, message: Any) -> None:
        raw = message.decode() if isinstance(message, bytes) else str(message)
        try:
            frame = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("wecom_ws_frame_parse_failed", channel_id=self.channel_id, error=_error_message(exc))
            return
        if not isinstance(frame, dict):
            return
        await self._handle_frame(frame)

    async def _handle_frame(self, frame: dict[str, Any]) -> None:
        cmd = str(frame.get("cmd") or "")
        req_id = _frame_req_id(frame)
        if req_id.startswith(_CMD_SUBSCRIBE):
            if frame.get("errcode") == 0:
                self.authenticated.set()
                logger.info("wecom_ws_authenticated", channel_id=self.channel_id, bot_id=self.bot_id[:12])
                await self._record_runtime_state("authenticated")
            else:
                error = f"{frame.get('errcode')}: {frame.get('errmsg')}"
                await self._record_runtime_state("auth_failed", error=error)
                raise RuntimeError(f"WeCom auth failed: {error}")
            return
        if req_id.startswith(_CMD_HEARTBEAT):
            return
        pending = self.pending_acks.pop(req_id, None)
        if pending and not pending.done():
            if frame.get("errcode") not in (None, 0):
                pending.set_exception(RuntimeError(f"{frame.get('errcode')}: {frame.get('errmsg')}"))
            else:
                pending.set_result(frame)
            return
        if cmd in {_CMD_CALLBACK, _CMD_LEGACY_CALLBACK}:
            task = asyncio.create_task(self._process_message_callback(frame))
            _WS_EVENT_TASKS.add(task)
            task.add_done_callback(_WS_EVENT_TASKS.discard)
            return
        if cmd == _CMD_EVENT_CALLBACK:
            task = asyncio.create_task(self._process_event_callback(frame))
            _WS_EVENT_TASKS.add(task)
            task.add_done_callback(_WS_EVENT_TASKS.discard)
            return
        if req_id:
            logger.debug(
                "wecom_ws_frame_unhandled",
                channel_id=self.channel_id,
                cmd=cmd,
                req_id=req_id[:80],
                errcode=frame.get("errcode"),
                errmsg=frame.get("errmsg"),
            )

    async def _process_message_callback(self, frame: dict[str, Any]) -> None:
        from app.domain.notifications.gateway_service import (
            extract_bind_token,
            extract_wecom_event_payload,
            handle_wecom_event_payload,
        )

        parsed = extract_wecom_event_payload(frame)
        text = str(parsed.get("text") or "").strip()
        stream_id = _generate_req_id("stream")
        is_bind_message = bool(extract_bind_token(text))
        try:
            async with get_db_context() as db:
                reply = await handle_wecom_event_payload(db, frame)
        except Exception as exc:  # noqa: BLE001
            logger.warning("wecom_ws_event_failed", channel_id=self.channel_id, error=_error_message(exc))
            reply = "企业微信 Channel 已收到消息，但后端处理失败，请稍后重试。"
        if reply:
            sent, error = await self._send_callback_reply(
                frame,
                reply,
                stream_id=stream_id,
                prefer_response_url=bool(text and not is_bind_message),
                chat_id=str(parsed.get("conversationId") or parsed.get("externalUserId") or "").strip(),
            )
            await self._record_delivery_result(ok=sent, error=error)

    async def _process_event_callback(self, frame: dict[str, Any]) -> None:
        body = frame.get("body") if isinstance(frame.get("body"), dict) else {}
        event = body.get("event") if isinstance(body.get("event"), dict) else {}
        if str(event.get("eventtype") or "") != "enter_chat":
            return
        prompt = await self._build_pending_bind_prompt()
        if not prompt:
            return
        with suppress(Exception):
            await self.reply_welcome(frame, prompt)

    async def _build_pending_bind_prompt(self) -> str | None:
        from app.domain.notifications.gateway_service import _channel_bind_prompt_text, _resolve_channel_site_brand

        async with get_db_context() as db:
            channel = await db.get(UserMessageChannel, self.channel_id)
            if not channel or channel.status != "pending":
                return None
            site_brand = await _resolve_channel_site_brand(db, channel)
        return f"{_channel_bind_prompt_text(site_brand)}\n系统收到关联码后会完成账号绑定，后续消息由 AI 助手接管。"

    async def reply_stream(
        self,
        frame: dict[str, Any],
        text: str,
        *,
        finish: bool,
        stream_id: str,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        req_id = _frame_req_id(frame)
        if not req_id:
            raise RuntimeError("missing WeCom callback req_id")
        return await self._send_and_wait(
            req_id,
            {
                "cmd": _CMD_RESPONSE,
                "headers": {"req_id": req_id},
                "body": {
                    "msgtype": "stream",
                    "stream": {
                        "id": stream_id,
                        "finish": bool(finish),
                        "content": _trim_message_text(text),
                    },
                },
            },
            timeout=timeout,
        )

    async def reply_welcome(self, frame: dict[str, Any], text: str) -> dict[str, Any]:
        req_id = _frame_req_id(frame)
        if not req_id:
            raise RuntimeError("missing WeCom event req_id")
        return await self._send_and_wait(
            req_id,
            {
                "cmd": _CMD_RESPONSE_WELCOME,
                "headers": {"req_id": req_id},
                "body": {"msgtype": "text", "text": {"content": _trim_message_text(text)}},
            },
            timeout=5,
        )

    async def send_message(self, chat_id: str, text: str) -> dict[str, Any]:
        normalized_chat_id = str(chat_id or "").strip()
        if not normalized_chat_id:
            raise RuntimeError("missing WeCom chat id")
        req_id = _generate_req_id(_CMD_SEND_MSG)
        return await self._send_and_wait(
            req_id,
            {
                "cmd": _CMD_SEND_MSG,
                "headers": {"req_id": req_id},
                "body": {
                    "chatid": normalized_chat_id,
                    "msgtype": "markdown",
                    "markdown": {"content": _trim_message_text(text)},
                },
            },
        )

    async def send_message_no_ack(self, chat_id: str, text: str) -> str:
        normalized_chat_id = str(chat_id or "").strip()
        if not normalized_chat_id:
            raise RuntimeError("missing WeCom chat id")
        req_id = _generate_req_id(_CMD_SEND_MSG)
        await self._send_frame(
            {
                "cmd": _CMD_SEND_MSG,
                "headers": {"req_id": req_id},
                "body": {
                    "chatid": normalized_chat_id,
                    "msgtype": "markdown",
                    "markdown": {"content": _trim_message_text(text)},
                },
            }
        )
        return req_id

    async def reply_via_response_url(self, frame: dict[str, Any], text: str, *, stream_id: str) -> dict[str, Any]:
        response_url = _response_url_from_frame(frame)
        if not response_url:
            raise RuntimeError("missing WeCom response_url")
        payload = {
            "msgtype": "stream",
            "stream": {
                "id": stream_id,
                "finish": True,
                "content": _trim_message_text(text),
            },
        }
        async with httpx.AsyncClient(timeout=_RESPONSE_URL_TIMEOUT_SECONDS) as client:
            response = await client.post(response_url, json=payload)
            response.raise_for_status()
            if response.content:
                data: Any = None
                with suppress(Exception):
                    data = response.json()
                if isinstance(data, dict) and data.get("errcode") not in (None, 0):
                    raise RuntimeError(f"{data.get('errcode')}: {data.get('errmsg')}")
                if isinstance(data, dict):
                    return data if isinstance(data, dict) else {"status": response.status_code}
        return {"status": response.status_code}

    async def _send_callback_reply(
        self,
        frame: dict[str, Any],
        text: str,
        *,
        stream_id: str,
        prefer_response_url: bool,
        chat_id: str,
    ) -> tuple[bool, str | None]:
        errors: list[str] = []
        if prefer_response_url and _response_url_from_frame(frame):
            try:
                await self.reply_via_response_url(frame, text, stream_id=stream_id)
                logger.info("wecom_ws_response_url_reply_sent", channel_id=self.channel_id)
                return True, None
            except Exception as exc:  # noqa: BLE001
                error = _error_message(exc)
                errors.append(f"response_url: {error}")
                logger.warning("wecom_ws_response_url_reply_failed", channel_id=self.channel_id, error=error)
        try:
            await self.reply_stream(
                frame,
                text,
                finish=True,
                stream_id=stream_id,
                timeout=_FINAL_REPLY_ACK_TIMEOUT_SECONDS,
            )
            logger.info("wecom_ws_passive_reply_sent", channel_id=self.channel_id)
            return True, None
        except Exception as exc:  # noqa: BLE001
            error = _error_message(exc)
            errors.append(f"passive: {error}")
            logger.warning("wecom_ws_reply_failed", channel_id=self.channel_id, error=error)
        if chat_id:
            try:
                await self.send_message_no_ack(chat_id, text)
                logger.info("wecom_ws_active_reply_queued", channel_id=self.channel_id, chat_id=chat_id[:80])
                return True, None
            except Exception as exc:  # noqa: BLE001
                error = _error_message(exc)
                errors.append(f"active: {error}")
                logger.warning("wecom_ws_active_reply_failed", channel_id=self.channel_id, error=error)
        return False, "；".join(errors) or "企业微信回复发送失败"

    async def _send_and_wait(self, req_id: str, frame: dict[str, Any], *, timeout: float = 15.0) -> dict[str, Any]:
        if not self.websocket:
            raise RuntimeError("WeCom WebSocket is not connected")
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pending_acks[req_id] = future
        try:
            await self._send_frame(frame)
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            if self.pending_acks.get(req_id) is future:
                self.pending_acks.pop(req_id, None)

    async def _send_frame(self, frame: dict[str, Any]) -> None:
        if not self.websocket:
            raise RuntimeError("WeCom WebSocket is not connected")
        async with self.send_lock:
            await self.websocket.send(json.dumps(frame, ensure_ascii=False))

    def _fail_pending(self, exc: Exception) -> None:
        for future in list(self.pending_acks.values()):
            if not future.done():
                future.set_exception(exc)
        self.pending_acks.clear()

    async def _record_runtime_state(self, status: str, *, error: str | None = None) -> None:
        from app.domain.notifications.message_channels import UserMessageChannelService

        try:
            async with get_db_context() as db:
                channel = await db.get(UserMessageChannel, self.channel_id)
                if not channel:
                    return
                extra = dict(channel.extra or {})
                wecom_bot = dict(extra.get("wecomBot") or {})
                now = datetime.now(UTC)
                now_iso = now.isoformat()
                wecom_bot.update(
                    {
                        "runtimeStatus": status,
                        "runtimeLastAt": now_iso,
                        "websocketUrl": self.ws_url,
                    }
                )
                if status == "authenticated":
                    wecom_bot["connected"] = True
                    wecom_bot.setdefault("connectedAt", now_iso)
                    if channel.status == "pending" and not str(wecom_bot.get("bindCodeReadyAt") or "").strip():
                        expires_at = now + timedelta(minutes=_BIND_CODE_READY_MINUTES)
                        wecom_bot["bindCodeReadyAt"] = now_iso
                        wecom_bot["bindCodeExpiresAt"] = expires_at.isoformat()
                        extra["expiresAt"] = expires_at.isoformat()
                        qr = dict(extra.get("qr") or {})
                        qr["gatewayReady"] = True
                        extra["qr"] = qr
                if error:
                    wecom_bot["runtimeError"] = error[:500]
                else:
                    wecom_bot.pop("runtimeError", None)
                extra["wecomBot"] = wecom_bot
                values: dict[str, Any] = {"extra": extra}
                if error:
                    values["last_error"] = error[:2000]
                elif status == "authenticated":
                    values["last_error"] = None
                await UserMessageChannelService(db).update(channel, values)
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("wecom_ws_runtime_state_update_failed", channel_id=self.channel_id, error=_error_message(exc))

    async def _record_delivery_result(self, *, ok: bool, error: str | None = None) -> None:
        from app.domain.notifications.message_channels import UserMessageChannelService

        try:
            async with get_db_context() as db:
                channel = await db.get(UserMessageChannel, self.channel_id)
                if not channel:
                    return
                await UserMessageChannelService(db).set_delivery_result(
                    channel,
                    ok=ok,
                    error=None if ok else (error or "企业微信回复发送失败"),
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("wecom_ws_delivery_result_update_failed", channel_id=self.channel_id, error=_error_message(exc))


async def start_wecom_channel_ws_account(*, channel_id: int, bot_id: str, bot_secret: str, ws_url: str | None = None) -> None:
    normalized_bot_id = str(bot_id or "").strip()
    normalized_secret = str(bot_secret or "").strip()
    normalized_ws_url = str(ws_url or WECOM_BOT_WS_URL).strip() or WECOM_BOT_WS_URL
    if not normalized_bot_id or not normalized_secret:
        return
    signature = (normalized_bot_id, normalized_secret, normalized_ws_url)
    current_task = _WS_TASKS.get(channel_id)
    if current_task and not current_task.done() and _WS_SIGNATURES.get(channel_id) == signature:
        return
    await stop_wecom_channel_ws_account(channel_id)
    runner = _WecomWsRunner(
        channel_id=channel_id,
        bot_id=normalized_bot_id,
        secret=normalized_secret,
        ws_url=normalized_ws_url,
    )
    _WS_RUNNERS[channel_id] = runner
    _WS_SIGNATURES[channel_id] = signature
    _WS_TASKS[channel_id] = asyncio.create_task(runner.run_forever())


async def stop_wecom_channel_ws_account(channel_id: int) -> None:
    runner = _WS_RUNNERS.pop(channel_id, None)
    if runner:
        runner.stop_event.set()
        if runner.websocket:
            with suppress(Exception):
                await runner.websocket.close()
    task = _WS_TASKS.pop(channel_id, None)
    _WS_SIGNATURES.pop(channel_id, None)
    if task and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def ensure_wecom_channel_ws() -> None:
    async with get_db_context() as db:
        result = await db.execute(
            select(UserMessageChannel).where(
                UserMessageChannel.channel_type == "wecom",
                UserMessageChannel.status.in_(["pending", "active"]),
                UserMessageChannel.secret.is_not(None),
                UserMessageChannel.deleted_at.is_(None),
            )
        )
        channels = list(result.scalars().all())

    active_ids: set[int] = set()
    for channel in channels:
        extra = dict(channel.extra or {})
        wecom_bot = dict(extra.get("wecomBot") or {})
        bot_id = str(wecom_bot.get("botId") or "").strip()
        bot_secret = decrypt_provider_secret_or_plain(channel.secret)
        if not bot_id or not bot_secret:
            continue
        active_ids.add(int(channel.id))
        ws_url = str(((channel.extra or {}).get("wecomBot") or {}).get("websocketUrl") or WECOM_BOT_WS_URL).strip()
        await start_wecom_channel_ws_account(
            channel_id=int(channel.id),
            bot_id=bot_id,
            bot_secret=bot_secret,
            ws_url=ws_url,
        )
    for channel_id in list(_WS_TASKS):
        if channel_id not in active_ids:
            await stop_wecom_channel_ws_account(channel_id)


async def send_wecom_channel_text(*, channel_id: int, chat_id: str, text: str) -> tuple[bool, str]:
    runner = _WS_RUNNERS.get(channel_id)
    if not runner:
        await ensure_wecom_channel_ws()
        runner = _WS_RUNNERS.get(channel_id)
    if not runner:
        return False, "企业微信 Channel 长连接尚未启动"
    try:
        await asyncio.wait_for(runner.authenticated.wait(), timeout=15)
        await runner.send_message_no_ack(chat_id, text)
    except Exception as exc:  # noqa: BLE001
        error = _error_message(exc)
        logger.warning("wecom_ws_send_failed", channel_id=channel_id, error=error)
        return False, error
    return True, "发送成功"


async def stop_wecom_channel_ws() -> None:
    for channel_id in list(_WS_TASKS):
        await stop_wecom_channel_ws_account(channel_id)
