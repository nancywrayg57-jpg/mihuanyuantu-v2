"""Feishu/Lark WebSocket event receiver for personal message channels."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import websockets

from app.core.logger import get_logger
from app.core.provider_secrets import decrypt_provider_secret_or_plain
from app.domain.notifications.feishu_client import resolve_feishu_base_url
from app.infrastructure.database.session import get_db_context

logger = get_logger(__name__)

_WS_TASKS: dict[int, asyncio.Task[None]] = {}
_WS_SIGNATURES: dict[int, tuple[str, str, str]] = {}
_WS_STOP_EVENTS: dict[int, asyncio.Event] = {}
_WS_EVENT_TASKS: set[asyncio.Task[None]] = set()


def _encode_varint(value: int) -> bytes:
    normalized = int(value or 0)
    if normalized < 0:
        normalized += 1 << 64
    parts: list[int] = []
    while normalized >= 0x80:
        parts.append((normalized & 0x7F) | 0x80)
        normalized >>= 7
    parts.append(normalized & 0x7F)
    return bytes(parts)


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    shift = 0
    result = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
    raise ValueError("unterminated protobuf varint")


def _field_key(field: int, wire_type: int) -> bytes:
    return _encode_varint((field << 3) | wire_type)


def _bytes_field(field: int, value: bytes) -> bytes:
    return _field_key(field, 2) + _encode_varint(len(value)) + value


def _string_field(field: int, value: str) -> bytes:
    return _bytes_field(field, str(value or "").encode())


def _varint_field(field: int, value: int) -> bytes:
    return _field_key(field, 0) + _encode_varint(value)


def _skip_field(data: bytes, pos: int, wire_type: int) -> int:
    if wire_type == 0:
        _, pos = _decode_varint(data, pos)
        return pos
    if wire_type == 1:
        return pos + 8
    if wire_type == 2:
        length, pos = _decode_varint(data, pos)
        return pos + length
    if wire_type == 5:
        return pos + 4
    raise ValueError(f"unsupported protobuf wire type: {wire_type}")


def _encode_header(header: dict[str, str]) -> bytes:
    return _string_field(1, header.get("key") or "") + _string_field(2, header.get("value") or "")


def _decode_header(data: bytes) -> dict[str, str]:
    pos = 0
    header: dict[str, str] = {"key": "", "value": ""}
    while pos < len(data):
        tag, pos = _decode_varint(data, pos)
        field = tag >> 3
        wire = tag & 7
        if wire == 2:
            length, pos = _decode_varint(data, pos)
            raw = data[pos : pos + length]
            pos += length
            if field == 1:
                header["key"] = raw.decode()
            elif field == 2:
                header["value"] = raw.decode()
        else:
            pos = _skip_field(data, pos, wire)
    return header


def _encode_frame(frame: dict[str, Any]) -> bytes:
    output = bytearray()
    output += _varint_field(1, int(frame.get("SeqID") or 0))
    output += _varint_field(2, int(frame.get("LogID") or 0))
    output += _varint_field(3, int(frame.get("service") or 0))
    output += _varint_field(4, int(frame.get("method") or 0))
    for header in frame.get("headers") or []:
        output += _bytes_field(5, _encode_header(header))
    if frame.get("payloadEncoding") is not None:
        output += _string_field(6, str(frame.get("payloadEncoding") or ""))
    if frame.get("payloadType") is not None:
        output += _string_field(7, str(frame.get("payloadType") or ""))
    if frame.get("payload") is not None:
        output += _bytes_field(8, bytes(frame.get("payload") or b""))
    if frame.get("LogIDNew") is not None:
        output += _string_field(9, str(frame.get("LogIDNew") or ""))
    return bytes(output)


def _decode_frame(data: bytes) -> dict[str, Any]:
    pos = 0
    frame: dict[str, Any] = {"headers": [], "payload": b""}
    while pos < len(data):
        tag, pos = _decode_varint(data, pos)
        field = tag >> 3
        wire = tag & 7
        if wire == 0:
            value, pos = _decode_varint(data, pos)
            if field == 1:
                frame["SeqID"] = value
            elif field == 2:
                frame["LogID"] = value
            elif field == 3:
                frame["service"] = value
            elif field == 4:
                frame["method"] = value
        elif wire == 2:
            length, pos = _decode_varint(data, pos)
            raw = data[pos : pos + length]
            pos += length
            if field == 5:
                frame.setdefault("headers", []).append(_decode_header(raw))
            elif field == 6:
                frame["payloadEncoding"] = raw.decode()
            elif field == 7:
                frame["payloadType"] = raw.decode()
            elif field == 8:
                frame["payload"] = raw
            elif field == 9:
                frame["LogIDNew"] = raw.decode()
        else:
            pos = _skip_field(data, pos, wire)
    return frame


def _headers_dict(frame: dict[str, Any]) -> dict[str, str]:
    return {str(item.get("key") or ""): str(item.get("value") or "") for item in frame.get("headers") or []}


@dataclass
class _ChunkState:
    chunks: list[bytes | None]
    created_at: float


class _FeishuWsRunner:
    def __init__(self, *, account_id: int, app_id: str, app_secret: str, domain: str):
        self.account_id = account_id
        self.app_id = app_id
        self.app_secret = app_secret
        self.domain = domain
        self.stop_event = asyncio.Event()
        self.chunk_cache: dict[str, _ChunkState] = {}
        self.ping_interval = 120.0
        self.service_id = 0

    async def run_forever(self) -> None:
        while not self.stop_event.is_set():
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("feishu_ws_disconnected", account_id=self.account_id, error=str(exc))
                await asyncio.sleep(5)

    async def _pull_connect_config(self) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{resolve_feishu_base_url(self.domain)}/callback/ws/endpoint",
                json={"AppID": self.app_id, "AppSecret": self.app_secret},
                headers={"locale": "zh", "User-Agent": "Message Channel"},
            )
            response.raise_for_status()
            data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Feishu WS endpoint error: {data}")
        ws_url = str((data.get("data") or {}).get("URL") or "").strip()
        if not ws_url:
            raise RuntimeError(f"Feishu WS endpoint URL missing: {data}")
        client_config = (data.get("data") or {}).get("ClientConfig") or {}
        self.ping_interval = float(client_config.get("PingInterval") or 120)
        parsed = urlsplit(ws_url)
        query = parse_qs(parsed.query)
        self.service_id = int((query.get("service_id") or ["0"])[0] or 0)
        return ws_url

    async def _run_once(self) -> None:
        ws_url = await self._pull_connect_config()
        logger.info("feishu_ws_connecting", account_id=self.account_id)
        async with websockets.connect(ws_url) as websocket:
            logger.info("feishu_ws_connected", account_id=self.account_id)
            ping_task = asyncio.create_task(self._ping_loop(websocket))
            try:
                async for message in websocket:
                    await self._handle_message(websocket, bytes(message))
                    if self.stop_event.is_set():
                        break
            finally:
                ping_task.cancel()

    async def _ping_loop(self, websocket: Any) -> None:
        while not self.stop_event.is_set():
            await self._send_frame(
                websocket,
                {
                    "SeqID": 0,
                    "LogID": 0,
                    "service": self.service_id,
                    "method": 0,
                    "headers": [{"key": "type", "value": "ping"}],
                },
            )
            await asyncio.sleep(max(self.ping_interval, 10.0))

    async def _handle_message(self, websocket: Any, raw_message: bytes) -> None:
        frame = _decode_frame(raw_message)
        method = int(frame.get("method") or 0)
        if method == 0:
            self._handle_control_frame(frame)
            return
        if method == 1:
            await self._handle_data_frame(websocket, frame)

    def _handle_control_frame(self, frame: dict[str, Any]) -> None:
        headers = _headers_dict(frame)
        if headers.get("type") != "pong" or not frame.get("payload"):
            return
        try:
            data = json.loads(bytes(frame.get("payload") or b"{}").decode())
        except Exception:
            return
        if data.get("PingInterval"):
            self.ping_interval = float(data.get("PingInterval") or self.ping_interval)

    def _merge_data_frame(self, frame: dict[str, Any]) -> dict[str, Any] | None:
        headers = _headers_dict(frame)
        if headers.get("type") not in {"event", "card"}:
            return None
        message_id = headers.get("message_id") or headers.get("trace_id") or ""
        total = max(int(headers.get("sum") or 1), 1)
        seq = int(headers.get("seq") or 0)
        state = self.chunk_cache.get(message_id)
        if not state or len(state.chunks) != total:
            state = _ChunkState(chunks=[None] * total, created_at=time.time())
            self.chunk_cache[message_id] = state
        if 0 <= seq < total:
            state.chunks[seq] = bytes(frame.get("payload") or b"")
        if any(chunk is None for chunk in state.chunks):
            return None
        self.chunk_cache.pop(message_id, None)
        merged = b"".join(chunk or b"" for chunk in state.chunks)
        return json.loads(merged.decode())

    async def _handle_data_frame(self, websocket: Any, frame: dict[str, Any]) -> None:
        start_at = time.time()
        code = 200
        try:
            payload = self._merge_data_frame(frame)
            if payload:
                task = asyncio.create_task(self._process_event_payload(payload))
                _WS_EVENT_TASKS.add(task)
                task.add_done_callback(_WS_EVENT_TASKS.discard)
        except Exception as exc:  # noqa: BLE001
            code = 500
            logger.warning("feishu_ws_event_failed", account_id=self.account_id, error=str(exc))
        response_payload = json.dumps({"code": code}, ensure_ascii=False).encode()
        response_frame = {
            **frame,
            "headers": [
                *(frame.get("headers") or []),
                {"key": "biz_rt", "value": str(int((time.time() - start_at) * 1000))},
            ],
            "payload": response_payload,
        }
        await self._send_frame(websocket, response_frame)

    async def _process_event_payload(self, payload: dict[str, Any]) -> None:
        try:
            from app.domain.notifications.gateway_service import handle_feishu_event_payload

            async with get_db_context() as db:
                await handle_feishu_event_payload(db, payload, gateway_account_id=self.account_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("feishu_ws_event_failed", account_id=self.account_id, error=str(exc))

    async def _send_frame(self, websocket: Any, frame: dict[str, Any]) -> None:
        await websocket.send(_encode_frame(frame))


async def start_feishu_gateway_ws_account(*, account_id: int, app_id: str, app_secret: str, domain: str) -> None:
    signature = (str(app_id), str(app_secret), str(domain or "feishu"))
    current_task = _WS_TASKS.get(account_id)
    if current_task and not current_task.done() and _WS_SIGNATURES.get(account_id) == signature:
        return
    await stop_feishu_gateway_ws_account(account_id)
    runner = _FeishuWsRunner(account_id=account_id, app_id=app_id, app_secret=app_secret, domain=domain or "feishu")
    _WS_STOP_EVENTS[account_id] = runner.stop_event
    _WS_SIGNATURES[account_id] = signature
    _WS_TASKS[account_id] = asyncio.create_task(runner.run_forever())


async def stop_feishu_gateway_ws_account(account_id: int) -> None:
    stop_event = _WS_STOP_EVENTS.pop(account_id, None)
    if stop_event:
        stop_event.set()
    task = _WS_TASKS.pop(account_id, None)
    _WS_SIGNATURES.pop(account_id, None)
    if task and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def ensure_feishu_gateway_ws() -> None:
    async with get_db_context() as db:
        from app.domain.notifications.gateway_service import MessageGatewayAccountService

        accounts = await MessageGatewayAccountService(db).get_active_accounts("feishu")
        active_ids = {int(account.id) for account in accounts}
        for account in accounts:
            app_secret = decrypt_provider_secret_or_plain(account.token_encrypted)
            if not account.account_id or not app_secret:
                continue
            await start_feishu_gateway_ws_account(
                account_id=int(account.id),
                app_id=str(account.account_id),
                app_secret=str(app_secret),
                domain=str((account.extra or {}).get("domain") or account.base_url or "feishu"),
            )
    for account_id in list(_WS_TASKS):
        if account_id not in active_ids:
            await stop_feishu_gateway_ws_account(account_id)


async def stop_feishu_gateway_ws() -> None:
    for account_id in list(_WS_TASKS):
        await stop_feishu_gateway_ws_account(account_id)
