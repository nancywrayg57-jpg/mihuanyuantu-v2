"""入站解析必须限定到"绑定这条渠道的那个网关账号"。

## 为什么

HMAC 签名只证明**某个合法网关**在说话，不证明**这个用户所属的网关**在说话。
而 `message_gateway_accounts` 没有 `tenant_id`、是全局共享的，同一渠道类型
可以有多个 active 账号（`get_default_active` 找不到默认就取任意一个 active）。

本系统是多租户多用户，只是 channel 与消息绑定到个人。所以不限定归属的话，
持有账号 A 密钥的运行时可以声称任意 `external_user_id`，
驱动**任何租户**下匹配到的渠道——包括经 `relay_inbound_to_assistant`
注入那个用户的 AI 助手、消耗他的额度。（codex 复核发现）
"""

from __future__ import annotations

import inspect

from app.domain.notifications import gateway_service
from app.domain.notifications.message_channels import UserMessageChannelService


def _where_source(func) -> str:
    return inspect.getsource(func)


def test_public_lookup_filters_by_gateway_account():
    """`find_active_inbound_channel` 必须接受并使用 gateway_account_id。"""
    signature = inspect.signature(UserMessageChannelService.find_active_inbound_channel)

    assert "gateway_account_id" in signature.parameters
    source = _where_source(UserMessageChannelService.find_active_inbound_channel)
    assert "UserMessageChannel.gateway_account_id ==" in source


def test_assistant_relay_lookup_also_filters():
    """**注入 AI 助手那条路径**同样要限定——它是后果最重的一段。

    只修公开的查找函数、漏掉这个内部函数，等于没修。
    """
    signature = inspect.signature(gateway_service._find_active_inbound_channel_for_update)

    assert "gateway_account_id" in signature.parameters
    source = _where_source(gateway_service._find_active_inbound_channel_for_update)
    assert "UserMessageChannel.gateway_account_id ==" in source


def test_relay_passes_the_authenticated_account_down():
    """鉴权拿到的账号 ID 必须一路传到查找处，不能中途丢掉。"""
    source = _where_source(gateway_service.relay_inbound_to_assistant)

    assert "gateway_account_id=gateway_account_id" in source


def test_bind_records_the_owning_account():
    """绑定时就把账号记下来，此后只有它能驱动这条渠道。"""
    signature = inspect.signature(UserMessageChannelService.bind_inbound_message)

    assert "gateway_account_id" in signature.parameters
    assert '"gateway_account_id"' in _where_source(UserMessageChannelService.bind_inbound_message)


def test_legacy_channels_are_claimed_on_first_authenticated_inbound():
    """存量渠道（字段为 NULL）在第一次经过鉴权的入站里被认领。

    不预先回填是有意的：我们并不知道存量当初是被哪个账号绑的，
    猜一个填进去比留空更危险。而"NULL 也能匹配"只对**已通过签名**的请求开放——
    在此之前那些端点根本没有鉴权，所以这不是放宽。
    """
    source = _where_source(UserMessageChannelService.record_inbound_message)

    assert "gateway_account_id" in source
    assert "channel.gateway_account_id is None" in source, "没有认领逻辑，存量永远匹配不到归属"
