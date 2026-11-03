from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.message_channels import _bind_instructions
from app.api.v1.endpoints.message_gateways import _extract_wecom_event_payload
from app.domain.notifications import gateway_service as gateway_service_mod
from app.domain.notifications import ilink_client as ilink_client_mod
from app.domain.notifications import wecom_qrcode as wecom_qrcode_mod
from app.domain.notifications import wecom_ws_client as wecom_ws_client_mod
from app.domain.notifications.gateway_service import (
    MESSAGE_CHANNEL_ASSISTANT_ROUTE,
    _append_pending_inbound_message,
    _build_deferred_pending_notice,
    _build_pending_followup_message,
    _inbound_message_dedupe_token,
    _is_duplicate_inbound_context,
    _message_channel_assistant_session_matches,
    _pending_inbound_messages,
    _resolve_channel_control_command,
    _resolve_wechat_login,
    _should_auto_merge_pending_followup,
    _wechat_pending_waits_for_bind_code,
    _WechatTypingRuntime,
)
from app.domain.notifications.ilink_client import _raise_for_ilink_error
from app.domain.notifications.ilink_client import _is_retryable_sendmessage_context_error
from app.domain.notifications.message_channels import select_unambiguous_inbound_channel
from app.domain.notifications.schemas import (
    UserMessageChannelBindStartRequest,
    UserMessageChannelInboundBindRequest,
    UserMessageChannelTestRequest,
)


def test_select_unambiguous_inbound_channel_prefers_exact_conversation() -> None:
    exact_channel = SimpleNamespace(id=1, conversation_id="chat-a")
    legacy_channel = SimpleNamespace(id=2, conversation_id=None)

    selected = select_unambiguous_inbound_channel(
        [legacy_channel, exact_channel],
        conversation_id="chat-a",
    )

    assert selected is exact_channel


def test_select_unambiguous_inbound_channel_rejects_ambiguous_without_conversation() -> None:
    first_channel = SimpleNamespace(id=1, conversation_id="chat-a")
    second_channel = SimpleNamespace(id=2, conversation_id="chat-b")

    selected = select_unambiguous_inbound_channel(
        [first_channel, second_channel],
        conversation_id=None,
    )

    assert selected is None


def test_message_channel_assistant_session_context_is_channel_scoped() -> None:
    channel = SimpleNamespace(id=18, user_id=7)
    context_data = {
        "source": "message_channel",
        "channelType": "wechat",
        "channelId": 18,
        "externalUserId": "wx-user",
        "conversationId": "wx-session",
        "boundUserId": 7,
        "boundTenantId": 3,
    }

    assert _message_channel_assistant_session_matches(
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data=context_data,
        channel=channel,
        channel_type="wechat",
        external_user_id="wx-user",
        conversation_id="wx-session",
        tenant_id=3,
    )
    assert not _message_channel_assistant_session_matches(
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data={**context_data, "channelId": 19},
        channel=channel,
        channel_type="wechat",
        external_user_id="wx-user",
        conversation_id="wx-session",
        tenant_id=3,
    )
    assert not _message_channel_assistant_session_matches(
        route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
        context_data={**context_data, "conversationId": "other-session"},
        channel=channel,
        channel_type="wechat",
        external_user_id="wx-user",
        conversation_id="wx-session",
        tenant_id=3,
    )


def test_message_channel_user_visible_defaults_are_brand_neutral() -> None:
    payload = UserMessageChannelTestRequest()
    assert "AOJUAI" not in payload.title

    instructions = _bind_instructions("wechat", "123456", gateway_ready=True, site_brand="演示平台")
    assert any("演示平台" in item for item in instructions)
    assert all("AOJUAI" not in item for item in instructions)


def test_wecom_message_channel_bind_contracts_are_supported() -> None:
    start = UserMessageChannelBindStartRequest.model_validate({"channelType": "wecom"})
    inbound = UserMessageChannelInboundBindRequest.model_validate(
        {
            "bindingCode": "12345678",
            "channelType": "wecom",
            "externalUserId": "wecom-user",
            "conversationId": "wecom-session",
        }
    )
    instructions = _bind_instructions("wecom", "12345678", gateway_ready=False, site_brand="演示平台")

    assert start.channel_type == "wecom"
    assert inbound.channel_type == "wecom"
    assert any("企业微信" in item for item in instructions)
    assert any("八位关联码" in item for item in instructions)


def test_wecom_qr_start_payload_is_normalized() -> None:
    data = wecom_qrcode_mod.parse_wecom_qr_start(
        {
            "data": {
                "scode": "abc123",
                "auth_url": "https://work.weixin.qq.com/ai/qc/c?s=abc123",
            }
        }
    )

    assert data["scode"] == "abc123"
    assert data["authUrl"] == "https://work.weixin.qq.com/ai/qc/c?s=abc123"
    assert data["qrPageUrl"].endswith("abc123")
    assert data["qrPayload"] == data["authUrl"]


def test_wecom_qr_status_redacts_secret() -> None:
    data = wecom_qrcode_mod.parse_wecom_qr_status(
        "abc123",
        {
            "data": {
                "status": "success",
                "bot_info": {"botid": "bot-1", "secret": "plain-secret"},
            }
        },
    )

    assert data["connected"] is True
    assert data["botId"] == "bot-1"
    assert data["secret"] == "plain-secret"
    assert data["raw"]["data"]["bot_info"]["secret"] == "***"


def test_wecom_official_bot_payload_is_normalized_for_channel_binding() -> None:
    payload = {
        "cmd": "aibot_callback",
        "headers": {"req_id": "req-1"},
        "body": {
            "msgid": "msg-1",
            "aibotid": "bot-1",
            "chattype": "single",
            "from": {"userid": "zhangsan", "corpid": "corp-1"},
            "msgtype": "text",
            "text": {"content": "123456"},
        },
    }

    parsed = _extract_wecom_event_payload(payload)
    dedupe_token = _inbound_message_dedupe_token(
        channel_type="wecom",
        raw_payload=payload,
        context_token=parsed["contextToken"],
    )

    assert parsed["text"] == "123456"
    assert parsed["externalUserId"] == "zhangsan"
    assert parsed["conversationId"] == "zhangsan"
    assert parsed["contextToken"] == "msg-1"
    assert dedupe_token == "wecom:msgid:msg-1"


def test_wecom_callback_response_url_is_extracted() -> None:
    payload = {
        "cmd": "aibot_msg_callback",
        "headers": {"req_id": "req-1"},
        "body": {
            "msgid": "msg-1",
            "from": {"userid": "zhangsan"},
            "msgtype": "text",
            "text": {"content": "你好"},
            "response_url": "https://qyapi.weixin.qq.com/cgi-bin/aibot/response?response_code=abc",
        },
    }

    assert wecom_ws_client_mod._response_url_from_frame(payload).endswith("response_code=abc")


@pytest.mark.asyncio
async def test_wecom_callback_reply_prefers_response_url_without_passive_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    runner = wecom_ws_client_mod._WecomWsRunner(
        channel_id=4,
        bot_id="bot-1",
        secret="secret",
        ws_url="wss://example.test/ws",
    )
    frame = {
        "cmd": "aibot_msg_callback",
        "headers": {"req_id": "req-1"},
        "body": {
            "from": {"userid": "zhangsan"},
            "text": {"content": "你好"},
            "response_url": "https://qyapi.weixin.qq.com/cgi-bin/aibot/response?response_code=abc",
        },
    }

    async def fake_response_url(_frame, text: str, *, stream_id: str):  # noqa: ANN001
        calls.append(("response_url", text))
        return {"errcode": 0}

    async def fail_reply_stream(*_args, **_kwargs):  # noqa: ANN003
        raise AssertionError("passive reply should not run after response_url succeeds")

    monkeypatch.setattr(runner, "reply_via_response_url", fake_response_url)
    monkeypatch.setattr(runner, "reply_stream", fail_reply_stream)

    ok, error = await runner._send_callback_reply(
        frame,
        "最终回复",
        stream_id="stream-1",
        prefer_response_url=True,
        chat_id="zhangsan",
    )

    assert ok is True
    assert error is None
    assert calls == [("response_url", "最终回复")]


@pytest.mark.asyncio
async def test_wecom_callback_reply_falls_back_to_active_send_without_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    runner = wecom_ws_client_mod._WecomWsRunner(
        channel_id=4,
        bot_id="bot-1",
        secret="secret",
        ws_url="wss://example.test/ws",
    )
    frame = {
        "cmd": "aibot_msg_callback",
        "headers": {"req_id": "req-1"},
        "body": {"from": {"userid": "zhangsan"}, "text": {"content": "你好"}},
    }

    async def fake_reply_stream(*_args, **_kwargs):  # noqa: ANN003
        raise TimeoutError()

    async def fake_active(chat_id: str, text: str) -> str:
        calls.append((chat_id, text))
        return "aibot_send_msg-1"

    monkeypatch.setattr(runner, "reply_stream", fake_reply_stream)
    monkeypatch.setattr(runner, "send_message_no_ack", fake_active)

    ok, error = await runner._send_callback_reply(
        frame,
        "最终回复",
        stream_id="stream-1",
        prefer_response_url=True,
        chat_id="zhangsan",
    )

    assert ok is True
    assert error is None
    assert calls == [("zhangsan", "最终回复")]


@pytest.mark.asyncio
async def test_send_wecom_channel_text_does_not_wait_for_active_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    class FakeRunner:
        def __init__(self) -> None:
            self.authenticated = asyncio.Event()
            self.authenticated.set()

        async def send_message_no_ack(self, chat_id: str, text: str) -> str:
            calls.append((chat_id, text))
            return "aibot_send_msg-1"

    monkeypatch.setitem(wecom_ws_client_mod._WS_RUNNERS, 8, FakeRunner())

    ok, message = await wecom_ws_client_mod.send_wecom_channel_text(channel_id=8, chat_id="zhangsan", text="任务结果")

    assert ok is True
    assert message == "发送成功"
    assert calls == [("zhangsan", "任务结果")]


def test_wechat_gateway_ready_pending_channel_waits_for_bind_code() -> None:
    extra = {
        "bindMode": "qr_inbound",
        "bindingCode": "123456",
        "qr": {
            "gatewayReady": True,
            "providerRaw": {"qrcode": "legacy-qr"},
        },
    }

    assert _resolve_wechat_login(extra) is None
    assert _wechat_pending_waits_for_bind_code(extra)


def test_message_channel_pending_inbound_messages_are_deduped_and_compacted() -> None:
    extra = _append_pending_inbound_message({}, {"text": "补充第一条", "dedupeToken": "m-1"})
    extra = _append_pending_inbound_message(extra, {"text": "补充第一条重复", "dedupeToken": "m-1"})
    extra = _append_pending_inbound_message(extra, {"text": "补充第二条", "dedupeToken": "m-2"})

    pending = _pending_inbound_messages(extra)

    assert [item["text"] for item in pending] == ["补充第一条", "补充第二条"]
    assert "lastPendingInboundAt" in extra


def test_message_channel_pending_followup_prompt_keeps_user_references() -> None:
    prompt = _build_pending_followup_message(
        [
            {"text": "刚才的问题限定在下个月"},
            {"text": "再按项目负责人分组"},
        ]
    )

    assert "补充 1" in prompt
    assert "刚才的问题限定在下个月" in prompt
    assert "补充 2" in prompt
    assert "再按项目负责人分组" in prompt


def test_message_channel_pending_followup_auto_merge_is_cost_bounded() -> None:
    assert _should_auto_merge_pending_followup([{"text": "按下个月"}, {"text": "按负责人分组"}])
    assert not _should_auto_merge_pending_followup(
        [
            {"text": "第一条"},
            {"text": "第二条"},
            {"text": "第三条"},
            {"text": "第四条"},
        ]
    )
    assert not _should_auto_merge_pending_followup([{"text": "长内容" * 220}])

    notice = _build_deferred_pending_notice([{"text": "长内容" * 220}])
    assert "没有自动合并重跑" in notice
    assert "补充 1" in notice


def test_message_channel_retry_token_bypasses_duplicate_guard() -> None:
    channel = SimpleNamespace(
        context_token=None,
        extra={
            "recentInboundContextTokens": ["wechat:m-1"],
            "retryInboundDedupeToken": "wechat:m-1",
        },
    )

    assert not _is_duplicate_inbound_context(channel, "wechat:m-1")

    channel.extra.pop("retryInboundDedupeToken")
    assert _is_duplicate_inbound_context(channel, "wechat:m-1")


def test_message_channel_control_commands_are_protocol_only() -> None:
    assert _resolve_channel_control_command("新对话") == "new_session"
    assert _resolve_channel_control_command(" 清空上下文 ") == "clear_session"
    assert _resolve_channel_control_command("取消当前操作") == "cancel_pending"
    assert _resolve_channel_control_command("不新建了") == "cancel_pending"
    assert _resolve_channel_control_command("不新建了，列出当前未开展的项目") is None
    assert _resolve_channel_control_command("新增一个项目") is None


@pytest.mark.asyncio
async def test_wechat_typing_runtime_is_stage_driven_and_stops() -> None:
    calls: list[tuple[str, int | str]] = []

    class FakeClient:
        async def send_typing_indicator(self, *, to_user_id: str, context_token: str | None = None, status: int = 1):
            calls.append(("typing", status))
            return True

        async def send_text(self, *, to_user_id: str, text: str, context_token: str | None = None):
            calls.append(("text", text))
            return "ok"

    runtime = _WechatTypingRuntime(FakeClient(), to_user_id="wx-user", context_token="ctx")  # type: ignore[arg-type]

    assert await runtime.start()
    await runtime.touch("assistant_call")
    assert await runtime.stop()

    assert calls[0] == ("typing", 1)
    assert calls[-1] == ("typing", 2)
    assert all(item[0] == "typing" for item in calls)


def test_ilink_client_rejects_business_error_payload() -> None:
    with pytest.raises(RuntimeError, match="sendmessage failed"):
        _raise_for_ilink_error({"ret": 1001, "msg": "invalid token"}, operation="sendmessage")

    _raise_for_ilink_error({"ret": 0}, operation="sendmessage")


def test_ilink_client_detects_retryable_context_error() -> None:
    exc = RuntimeError("iLink sendmessage failed: ret=-2, message={'ret': -2}")
    assert _is_retryable_sendmessage_context_error(exc) is True

    other = RuntimeError("iLink sendmessage failed: ret=1001, message=invalid token")
    assert _is_retryable_sendmessage_context_error(other) is False


@pytest.mark.asyncio
async def test_ilink_get_updates_timeout_is_clamped_below_poll_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[float] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"ret": 0, "msgs": [], "get_updates_buf": "next"}

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            captured.append(float(timeout))

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(ilink_client_mod.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(ilink_client_mod.settings, "MESSAGE_GATEWAY_POLL_INTERVAL_SECONDS", 20, raising=False)
    monkeypatch.setattr(ilink_client_mod.settings, "MESSAGE_GATEWAY_WECHAT_GET_UPDATES_TIMEOUT_SECONDS", 30.0, raising=False)

    client = ilink_client_mod.WechatIlinkClient(base_url="https://ilinkai.weixin.qq.com", token="plain-token")
    payload = await client.get_updates(get_updates_buf="cursor-1")

    assert payload["ret"] == 0
    assert captured == [18.0]


@pytest.mark.asyncio
async def test_wechat_gateway_poll_commits_before_long_poll_request(monkeypatch: pytest.MonkeyPatch) -> None:
    account = SimpleNamespace(
        id=9,
        token_encrypted="encrypted-token",
        base_url="https://ilinkai.weixin.qq.com",
        get_updates_buf="cursor-1",
        account_id="bot-1",
    )

    class FakeDb:
        def __init__(self) -> None:
            self.commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    db = FakeDb()
    update_calls: list[tuple[str | None, str | None]] = []

    class FakeGatewayAccountService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def update_poll_state(self, _account, *, buf: str | None = None, error: str | None = None) -> None:  # noqa: ANN001
            update_calls.append((buf, error))

    class FakeChannelService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

    class FakeWechatIlinkClient:
        def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0) -> None:
            self.base_url = base_url
            self.token = token
            self.timeout = timeout

        async def get_updates(self, *, get_updates_buf: str | None = None, timeout: float | None = None) -> dict[str, object]:
            assert db.commit_count >= 1
            assert get_updates_buf == "cursor-1"
            return {"ret": 0, "msgs": [], "get_updates_buf": "cursor-2"}

    monkeypatch.setattr(gateway_service_mod, "decrypt_provider_secret_or_plain", lambda _value: "plain-token")
    monkeypatch.setattr(gateway_service_mod, "MessageGatewayAccountService", FakeGatewayAccountService)
    monkeypatch.setattr(gateway_service_mod, "UserMessageChannelService", FakeChannelService)
    monkeypatch.setattr(gateway_service_mod, "WechatIlinkClient", FakeWechatIlinkClient)

    processed = await gateway_service_mod.poll_wechat_gateway_account(db, account)  # type: ignore[arg-type]

    assert processed == 0
    assert db.commit_count >= 2
    assert update_calls == [("cursor-2", None)]


@pytest.mark.asyncio
async def test_pending_wechat_login_poll_commits_before_qrcode_status_request(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = SimpleNamespace(
        id=12,
        channel_type="wechat",
        status="pending",
        extra={"wechatLogin": {"qrcode": "qr-1", "pollBaseUrl": "https://ilinkai.weixin.qq.com"}},
    )

    class FakeDb:
        def __init__(self) -> None:
            self.commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    db = FakeDb()
    updates: list[dict[str, object]] = []

    class FakeChannelService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def get_list(self, **_kwargs):  # noqa: ANN003
            return [channel], 1

        async def update(self, _channel, values: dict[str, object]):  # noqa: ANN001
            updates.append(values)
            return _channel

        async def delete(self, _channel) -> None:  # noqa: ANN001
            raise AssertionError("delete should not be called in this branch")

    class FakeGatewayAccountService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

    class FakeWechatIlinkClient:
        def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0) -> None:
            self.base_url = base_url
            self.token = token
            self.timeout = timeout

        async def get_qrcode_status(self, *, qrcode: str) -> dict[str, object]:
            assert db.commit_count >= 1
            assert qrcode == "qr-1"
            raise RuntimeError("temporary unavailable")

    monkeypatch.setattr(gateway_service_mod, "UserMessageChannelService", FakeChannelService)
    monkeypatch.setattr(gateway_service_mod, "MessageGatewayAccountService", FakeGatewayAccountService)
    monkeypatch.setattr(gateway_service_mod, "WechatIlinkClient", FakeWechatIlinkClient)

    processed = await gateway_service_mod.poll_pending_wechat_logins(db)  # type: ignore[arg-type]

    assert processed == 0
    assert db.commit_count >= 2
    assert len(updates) == 1
    assert "temporary unavailable" in str(updates[0]["extra"])


@pytest.mark.asyncio
async def test_message_channel_runtime_queues_and_merges_inbound_during_active_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = SimpleNamespace(
        id=18,
        user_id=7,
        channel_type="wechat",
        external_user_id="wx-user",
        conversation_id="wx-session",
        context_token=None,
        extra={},
        last_error=None,
        last_sent_at=None,
    )
    user = SimpleNamespace(id=7, tenant_id=3, deleted_at=None)
    events: list[str] = []

    class FakeResult:
        def __init__(self, value: object) -> None:
            self.value = value

        def scalar_one_or_none(self) -> object:
            return self.value

    class FakeDB:
        def __init__(self) -> None:
            self.execute_calls = 0
            self.commit_count = 0

        async def execute(self, _stmt):  # noqa: ANN001
            self.execute_calls += 1
            return FakeResult(user if self.execute_calls <= 2 else channel)

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeChannelService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def record_inbound_message(
            self,
            target_channel,
            *,
            gateway_account_id=None,
            context_token=None,
            inbound_dedupe_token=None,
            conversation_id=None,
            raw_payload=None,
        ):
            target_channel.context_token = context_token or target_channel.context_token
            target_channel.conversation_id = conversation_id or target_channel.conversation_id
            extra = dict(target_channel.extra or {})
            extra["lastInbound"] = raw_payload
            token = str(inbound_dedupe_token or context_token or "").strip()
            if token:
                tokens = [item for item in extra.get("recentInboundContextTokens", []) if item != token]
                extra["recentInboundContextTokens"] = [token, *tokens][:8]
            target_channel.extra = extra
            return target_channel

        async def update(self, target_channel, values: dict):
            for key, value in values.items():
                setattr(target_channel, key, value)
            return target_channel

        async def set_delivery_result(self, target_channel, *, ok: bool, error: str | None = None) -> None:
            target_channel.last_error = None if ok else error

    class FakeAssistantService:
        messages: list[str] = []

        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def create_session(self, **_kwargs):  # noqa: ANN003
            return SimpleNamespace(id=77)

        async def get_session(self, **_kwargs):  # noqa: ANN003
            return SimpleNamespace(
                id=77,
                route_path=MESSAGE_CHANNEL_ASSISTANT_ROUTE,
                context_data={
                    "source": "message_channel",
                    "channelType": "wechat",
                    "channelId": 18,
                    "externalUserId": "wx-user",
                    "conversationId": "wx-session",
                    "boundUserId": 7,
                    "boundTenantId": 3,
                },
            )

        async def chat_reply(self, *, message: str, **_kwargs):  # noqa: ANN003
            self.__class__.messages.append(message)
            if message == "第一条":
                nested_reply = await gateway_service_mod.relay_inbound_to_assistant(
                    db=self.db,
                    channel_type="wechat",
                    external_user_id="wx-user",
                    conversation_id="wx-session",
                    context_token="ctx-2",
                    text="第二条补充",
                    raw_payload={"message_id": "m-2", "text": "第二条补充"},
                    inbound_dedupe_token="wechat:m-2",
                )
                assert nested_reply is not None
                assert "补充内容" in nested_reply
                return SimpleNamespace(reply="第一条回复")
            assert "补充 1: 第二条补充" in message
            return SimpleNamespace(reply="已合并补充")

    async def fake_find_active(*_args, **_kwargs):  # noqa: ANN003
        return channel

    async def fake_processing_start():
        events.append("processing:start")
        return {"started": True}

    async def fake_processing_cleanup(state):
        events.append(f"processing:cleanup:{bool(state)}")

    async def fake_get_user_data_scope(_db, _user):  # noqa: ANN001
        return SimpleNamespace(has_all_read_access=True, read_team_ids=[])

    async def fake_resolve_tenant_site_brand(*_args, **_kwargs):  # noqa: ANN003
        return "演示平台"

    async def fake_assistant_is_enabled(*_args, **_kwargs):  # noqa: ANN003
        return True

    FakeAssistantService.messages = []
    gateway_service_mod._MESSAGE_CHANNEL_ACTIVE_CHANNEL_IDS.clear()
    monkeypatch.setattr(gateway_service_mod, "UserMessageChannelService", FakeChannelService)
    monkeypatch.setattr(gateway_service_mod, "_find_active_inbound_channel_for_update", fake_find_active)
    monkeypatch.setattr(gateway_service_mod, "_resolve_tenant_site_brand", fake_resolve_tenant_site_brand)
    monkeypatch.setattr(
        "app.domain.assistant.config_service.AssistantConfigService.is_enabled",
        fake_assistant_is_enabled,
    )
    monkeypatch.setattr("app.domain.assistant.service.AssistantService", FakeAssistantService)
    monkeypatch.setattr("app.core.data_permission.get_user_data_scope", fake_get_user_data_scope)

    reply = await gateway_service_mod.relay_inbound_to_assistant(
        db=FakeDB(),  # type: ignore[arg-type]
        channel_type="wechat",
        external_user_id="wx-user",
        conversation_id="wx-session",
        context_token="ctx-1",
        text="第一条",
        raw_payload={"message_id": "m-1", "text": "第一条"},
        inbound_dedupe_token="wechat:m-1",
        processing_callback=fake_processing_start,
        processing_cleanup_callback=fake_processing_cleanup,
    )

    assert reply == "第一条回复\n\n已合并补充"
    assert events == ["processing:start", "processing:cleanup:True"]
    assert FakeAssistantService.messages == [
        "第一条",
        "用户在上一条消息处理期间继续发送了补充内容。请把这些补充与刚才的问题合并理解；"
        "如果需要引用，请使用“补充 1 / 补充 2”的说法，不要暴露内部 Channel 字段。\n"
        "补充 1: 第二条补充",
    ]
    assert _pending_inbound_messages(channel.extra) == []
    assert not gateway_service_mod._MESSAGE_CHANNEL_ACTIVE_CHANNEL_IDS


def test_upsert_request_keeps_extra_when_it_is_omitted():
    """编辑表单不传 `extra` 时，必须保持原样，**不能**覆盖成空。

    `update_user_channel` 的写法是 `extra if extra is not None else channel.extra`，
    所以 schema 默认值必须是 None 而不是 `{}`。默认成 `{}` 的后果是静默的：
    扫码绑定的渠道把会话状态存在 extra 里（微信的 lastInboundContextToken、
    lastInbound、续期提醒偏好），一次编辑就把它们抹掉，
    这条渠道从此发不出消息，而且不报错——只在下次投递时莫名失败。
    """
    from app.domain.notifications.schemas import UserMessageChannelUpsertRequest

    request = UserMessageChannelUpsertRequest(name="我的渠道")

    assert request.extra is None, "extra 默认成 {} 会静默清空扫码渠道的会话状态"


def test_upsert_request_can_still_clear_extra_explicitly():
    """要清空得**显式**传 `{}`——保留这条路，否则没法真正清理。"""
    from app.domain.notifications.schemas import UserMessageChannelUpsertRequest

    request = UserMessageChannelUpsertRequest(name="我的渠道", extra={})

    assert request.extra == {}



# ---------------------------------------------------------------- 绑定限流的网关账号隔离（codex 终审 #2）


def test_guard_key_differs_across_gateway_accounts():
    """飞书 open_id 是应用级作用域：账号 A 的失败尝试不得撞进账号 B 的限流。"""
    from app.domain.notifications.message_channels import _bind_guard_key

    a = _bind_guard_key(
        channel_type="feishu", subject_type="external-user",
        subject="ou_same_id", gateway_account_id=1,
    )
    b = _bind_guard_key(
        channel_type="feishu", subject_type="external-user",
        subject="ou_same_id", gateway_account_id=2,
    )
    assert a != b, "不同网关账号共享限流桶，可被跨账号刷爆"


def test_guard_key_without_account_stays_stable():
    """未知账号（None）退化为共享键——宁可误伤也不放行，且键形态稳定。"""
    from app.domain.notifications.message_channels import _bind_guard_key

    first = _bind_guard_key(
        channel_type="wechat", subject_type="external-user", subject="wx1",
    )
    again = _bind_guard_key(
        channel_type="wechat", subject_type="external-user", subject="wx1",
        gateway_account_id=None,
    )
    assert first == again


@pytest.mark.asyncio
async def test_legacy_null_channels_only_match_the_default_account(monkeypatch):
    """存量（gateway_account_id IS NULL）渠道只允许默认账号认领。

    HMAC 只证明"来自某个合法网关"，不证明"这个用户所属的网关"——
    放开的话账号 A 可用受害者的 external ID 认领账号 B 的存量渠道，
    驱动其 AI 助手。（codex 终审 #1）
    """
    from app.domain.notifications.message_channels import UserMessageChannelService

    captured: dict[str, object] = {}

    service = UserMessageChannelService.__new__(UserMessageChannelService)

    async def fake_is_default(*, channel_type, gateway_account_id):
        return gateway_account_id == 1  # 账号 1 是默认，账号 2 不是

    async def fake_get_list(**kwargs):
        captured["where"] = kwargs["where"]
        return [], 0

    service._is_default_gateway_account = fake_is_default
    service.get_list = fake_get_list

    # 非默认账号（2）：where 里不允许出现 IS NULL 分支
    await service.find_active_inbound_channel(
        channel_type="wechat", external_user_id="wx-u", gateway_account_id=2,
    )
    rendered = " ".join(str(c) for c in captured["where"])
    assert "IS NULL" not in rendered.replace("deleted_at IS NULL", ""), (
        f"非默认账号仍能匹配存量 NULL 渠道：{rendered}"
    )

    # 默认账号（1）：允许带 IS NULL 分支（认领存量）
    await service.find_active_inbound_channel(
        channel_type="wechat", external_user_id="wx-u", gateway_account_id=1,
    )
    rendered_default = " ".join(str(c) for c in captured["where"])
    assert "gateway_account_id IS NULL" in rendered_default


@pytest.mark.asyncio
async def test_feishu_does_not_fall_back_to_default_when_bound_account_is_dead():
    """飞书绑定账号停用后**不回落默认账号**（codex 终审 #14）。

    open_id 是应用级作用域：换一个账号（应用）后这个 open_id 指不到同一个人，
    回落发出去要么报错、要么错投。明确失败比静默错投诚实。
    微信可以回落——用户 ID 全局有效，那是运维换账号的正常路径。
    """
    from app.domain.notifications.gateway_service import MessageGatewayAccountService

    service = MessageGatewayAccountService.__new__(MessageGatewayAccountService)
    calls: list[str] = []

    async def dead_account(_id):
        return SimpleNamespace(status="disabled")

    async def default_active(channel_type):
        calls.append(channel_type)
        return SimpleNamespace(id=99, status="active")

    service.get_account = dead_account
    service.get_default_active = default_active

    got = await service.resolve_for_channel("feishu", gateway_account_id=7)
    assert got is None, "飞书回落到了默认账号，会用错凭据错投"
    assert calls == [], "不该去查默认账号"

    got_wechat = await service.resolve_for_channel("wechat", gateway_account_id=7)
    assert got_wechat is not None and got_wechat.id == 99, "微信应当回落默认账号"
