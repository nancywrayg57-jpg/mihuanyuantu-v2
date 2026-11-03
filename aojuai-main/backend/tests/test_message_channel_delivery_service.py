from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.notifications import message_channels as message_channels_mod


@pytest.mark.asyncio
async def test_wechat_channel_delivery_returns_failure_instead_of_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = SimpleNamespace(
        id=2,
        channel_type="wechat",
        status="active",
        message_types=["notification"],
        external_user_id="wx-user",
        context_token="ctx-token",
    )

    class FakeGatewayAccountService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def resolve_for_channel(self, channel_type: str, *, gateway_account_id=None):
            # 外发改成优先用**渠道绑定的**账号；假对象跟着提供同名方法，
            # 否则这些用例测的是"方法不存在"，不是投递行为。
            return await self.get_default_active(channel_type)

        async def get_default_active(self, _channel_type: str):
            return SimpleNamespace(
                base_url="https://ilinkai.weixin.qq.com",
                token_encrypted="encrypted-token",
            )

    class FakeWechatIlinkClient:
        def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
            self.base_url = base_url
            self.token = token
            self.timeout = timeout

        async def send_text(self, *, to_user_id: str, text: str, context_token: str | None = None) -> str:
            raise RuntimeError("iLink sendmessage failed: ret=-2, message={'ret': -2}")

    monkeypatch.setattr(
        "app.domain.notifications.gateway_service.MessageGatewayAccountService",
        FakeGatewayAccountService,
    )
    monkeypatch.setattr(
        "app.domain.notifications.ilink_client.WechatIlinkClient",
        FakeWechatIlinkClient,
    )
    monkeypatch.setattr(
        "app.core.provider_secrets.decrypt_provider_secret_or_plain",
        lambda _value: "plain-token",
    )

    service = message_channels_mod.UserMessageChannelService(db=None)  # type: ignore[arg-type]
    ok, message = await service.deliver_to_channel(
        channel,
        title="测试消息",
        content="hello",
        message_type="notification",
    )

    assert ok is False
    assert "请先在微信 Channel 中发送一条新消息刷新会话" in message


@pytest.mark.asyncio
async def test_wechat_channel_delivery_prefers_latest_inbound_context_token(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = SimpleNamespace(
        id=2,
        channel_type="wechat",
        status="active",
        message_types=["notification"],
        external_user_id="wx-user",
        context_token="channel-token",
        extra={"lastInbound": {"context_token": "latest-inbound-token"}},
    )

    class FakeGatewayAccountService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def resolve_for_channel(self, channel_type: str, *, gateway_account_id=None):
            # 外发改成优先用**渠道绑定的**账号；假对象跟着提供同名方法，
            # 否则这些用例测的是"方法不存在"，不是投递行为。
            return await self.get_default_active(channel_type)

        async def get_default_active(self, _channel_type: str):
            return SimpleNamespace(
                base_url="https://ilinkai.weixin.qq.com",
                token_encrypted="encrypted-token",
            )

    calls: list[str | None] = []

    class FakeWechatIlinkClient:
        def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
            self.base_url = base_url
            self.token = token
            self.timeout = timeout

        async def send_text(self, *, to_user_id: str, text: str, context_token: str | None = None) -> str:
            calls.append(context_token)
            return "ok"

    monkeypatch.setattr(
        "app.domain.notifications.gateway_service.MessageGatewayAccountService",
        FakeGatewayAccountService,
    )
    monkeypatch.setattr(
        "app.domain.notifications.ilink_client.WechatIlinkClient",
        FakeWechatIlinkClient,
    )
    monkeypatch.setattr(
        "app.core.provider_secrets.decrypt_provider_secret_or_plain",
        lambda _value: "plain-token",
    )

    service = message_channels_mod.UserMessageChannelService(db=None)  # type: ignore[arg-type]
    ok, message = await service.deliver_to_channel(
        channel,
        title="测试消息",
        content="hello",
        message_type="notification",
    )

    assert ok is True
    assert message == "发送成功"
    assert calls == ["latest-inbound-token"]


@pytest.mark.asyncio
async def test_wechat_channel_delivery_filters_dedupe_tokens_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = SimpleNamespace(
        id=2,
        channel_type="wechat",
        status="active",
        message_types=["notification"],
        external_user_id="wx-user",
        context_token="channel-token",
        extra={
            "lastInboundContextToken": "wechat:message_id:m-1",
            "recentInboundContextTokens": ["wechat:message_id:m-1", "recent-context-token"],
        },
    )

    class FakeGatewayAccountService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def resolve_for_channel(self, channel_type: str, *, gateway_account_id=None):
            # 外发改成优先用**渠道绑定的**账号；假对象跟着提供同名方法，
            # 否则这些用例测的是"方法不存在"，不是投递行为。
            return await self.get_default_active(channel_type)

        async def get_default_active(self, _channel_type: str):
            return SimpleNamespace(
                base_url="https://ilinkai.weixin.qq.com",
                token_encrypted="encrypted-token",
            )

    calls: list[str | None] = []

    class FakeWechatIlinkClient:
        def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
            self.base_url = base_url
            self.token = token
            self.timeout = timeout

        async def send_text(self, *, to_user_id: str, text: str, context_token: str | None = None) -> str:
            calls.append(context_token)
            if context_token == "channel-token":
                raise RuntimeError("iLink sendmessage failed: ret=-2, message={'ret': -2}")
            return "ok"

    monkeypatch.setattr(
        "app.domain.notifications.gateway_service.MessageGatewayAccountService",
        FakeGatewayAccountService,
    )
    monkeypatch.setattr(
        "app.domain.notifications.ilink_client.WechatIlinkClient",
        FakeWechatIlinkClient,
    )
    monkeypatch.setattr(
        "app.core.provider_secrets.decrypt_provider_secret_or_plain",
        lambda _value: "plain-token",
    )

    service = message_channels_mod.UserMessageChannelService(db=None)  # type: ignore[arg-type]
    ok, message = await service.deliver_to_channel(
        channel,
        title="测试消息",
        content="hello",
        message_type="notification",
    )

    assert ok is True
    assert message == "发送成功"
    assert calls == ["recent-context-token"]


@pytest.mark.asyncio
async def test_wechat_channel_test_prefers_latest_inbound_context_token(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = SimpleNamespace(
        id=2,
        channel_type="wechat",
        status="active",
        message_types=["notification"],
        external_user_id="wx-user",
        context_token="channel-token",
        extra={"lastInbound": {"context_token": "latest-inbound-token"}},
    )

    class FakeGatewayAccountService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def resolve_for_channel(self, channel_type: str, *, gateway_account_id=None):
            # 外发改成优先用**渠道绑定的**账号；假对象跟着提供同名方法，
            # 否则这些用例测的是"方法不存在"，不是投递行为。
            return await self.get_default_active(channel_type)

        async def get_default_active(self, _channel_type: str):
            return SimpleNamespace(
                base_url="https://ilinkai.weixin.qq.com",
                token_encrypted="encrypted-token",
            )

    calls: list[str | None] = []

    class FakeWechatIlinkClient:
        def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
            self.base_url = base_url
            self.token = token
            self.timeout = timeout

        async def send_text(self, *, to_user_id: str, text: str, context_token: str | None = None) -> str:
            calls.append(context_token)
            return "ok"

    monkeypatch.setattr(
        "app.domain.notifications.gateway_service.MessageGatewayAccountService",
        FakeGatewayAccountService,
    )
    monkeypatch.setattr(
        "app.domain.notifications.ilink_client.WechatIlinkClient",
        FakeWechatIlinkClient,
    )
    monkeypatch.setattr(
        "app.core.provider_secrets.decrypt_provider_secret_or_plain",
        lambda _value: "plain-token",
    )

    service = message_channels_mod.UserMessageChannelService(db=None)  # type: ignore[arg-type]
    ok, message = await service.test_channel_delivery(
        channel,
        title="测试消息",
        content="hello",
    )

    assert ok is True
    assert message == "发送成功"
    assert calls == ["latest-inbound-token"]


@pytest.mark.asyncio
async def test_wechat_channel_test_translates_stale_context_error(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = SimpleNamespace(
        id=2,
        channel_type="wechat",
        status="active",
        message_types=["notification"],
        external_user_id="wx-user",
        context_token="channel-token",
        extra={"lastInbound": {"context_token": "latest-inbound-token"}},
    )

    class FakeGatewayAccountService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            self.db = _db

        async def resolve_for_channel(self, channel_type: str, *, gateway_account_id=None):
            # 外发改成优先用**渠道绑定的**账号；假对象跟着提供同名方法，
            # 否则这些用例测的是"方法不存在"，不是投递行为。
            return await self.get_default_active(channel_type)

        async def get_default_active(self, _channel_type: str):
            return SimpleNamespace(
                base_url="https://ilinkai.weixin.qq.com",
                token_encrypted="encrypted-token",
            )

    class FakeWechatIlinkClient:
        def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
            self.base_url = base_url
            self.token = token
            self.timeout = timeout

        async def send_text(self, *, to_user_id: str, text: str, context_token: str | None = None) -> str:
            raise RuntimeError("iLink sendmessage failed: ret=-2, message={'ret': -2}")

    monkeypatch.setattr(
        "app.domain.notifications.gateway_service.MessageGatewayAccountService",
        FakeGatewayAccountService,
    )
    monkeypatch.setattr(
        "app.domain.notifications.ilink_client.WechatIlinkClient",
        FakeWechatIlinkClient,
    )
    monkeypatch.setattr(
        "app.core.provider_secrets.decrypt_provider_secret_or_plain",
        lambda _value: "plain-token",
    )

    service = message_channels_mod.UserMessageChannelService(db=None)  # type: ignore[arg-type]
    ok, message = await service.test_channel_delivery(
        channel,
        title="测试消息",
        content="hello",
    )

    assert ok is False
    assert "请先在微信 Channel 中发送一条新消息刷新会话" in message


def test_webhook_error_text_never_contains_the_url():
    """投递失败的错误文案不得带 URL——用户可能把 secret 放在路径或 query 里，

    而这条文案会写进 target_snapshot、被 relay 状态查询接口返回给外部应用。
    """
    from app.domain.notifications.message_channels import _scrub_urls

    scrubbed = _scrub_urls(
        "ConnectError: All connection attempts failed for "
        "https://hooks.example.com/warn/T000/B000/SECRETTOKEN?key=shh"
    )
    assert "SECRETTOKEN" not in scrubbed
    assert "shh" not in scrubbed
    assert "hooks.example.com" not in scrubbed
    assert "<url>" in scrubbed
