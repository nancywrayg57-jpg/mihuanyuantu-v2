"""网关账号归属必须一路传到底，并且外发要用绑定的那个账号。

## 为什么写成"扫调用点"而不是行为测试

上一轮我给多个调用点做了**跨文件的批量字符串替换**，结果在
`poll_wechat_gateway_account` 里塞进了一个该作用域根本不存在的变量
（那里的账号叫 `account`），微信收到绑定码就会 `NameError` ——
**而这条主路径没有任何测试**，全量 2632 条照样绿。（codex 复核发现）

行为测试要拉起长轮询和外部网关，成本高；而这类错误的形态很固定：
"调用点漏传/传错账号"。所以这里直接扫调用点，配一条静态检查兜住整类问题。
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import pathlib

from app.domain.notifications import gateway_service
from app.domain.notifications.gateway_service import MessageGatewayAccountService
from app.domain.notifications.message_channels import UserMessageChannelService

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_polling_passes_the_account_it_already_holds():
    """微信长轮询函数里，每个渠道解析/绑定/记录入站都要带上账号。

    它手里本来就有 `account`——不传下去的话，隔离查询在这条路径上等于没开。
    """
    # **逐个调用点检查，不数数量。**
    # 第一版写的是 `count(...) >= 5`，而实际有 6 处——删掉一处照样通过，
    # 变异测试当场证明这条守卫是假的。
    scoped_callees = {
        "bind_inbound_message",
        "relay_inbound_to_assistant",
        "find_active_inbound_channel",
        "record_inbound_message",
    }
    tree = ast.parse(inspect.getsource(gateway_service.poll_wechat_gateway_account).lstrip())

    missing: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name not in scoped_callees:
            continue
        seen.add(name)
        keyword = next((kw for kw in node.keywords if kw.arg == "gateway_account_id"), None)
        if keyword is None:
            missing.append(f"{name}（第 {node.lineno} 行）没传 gateway_account_id")
            continue
        # 必须是 account.id——这个作用域里没有别的账号来源
        if "account.id" not in ast.unparse(keyword.value):
            missing.append(f"{name}（第 {node.lineno} 行）传的不是 account.id")

    assert seen == scoped_callees, f"测试假设已过期，轮询函数里少了：{scoped_callees - seen}"
    assert not missing, "隔离查询只在参数非空时才过滤，漏传即失效：\n  " + "\n  ".join(missing)


def test_no_call_site_references_an_undefined_account_variable():
    """整个文件里不得出现"传了 `gateway_account_id=gateway_account_id`
    但作用域内没有这个名字"的写法——那正是上一轮那个 NameError。"""
    tree = ast.parse((BACKEND / "app/domain/notifications/gateway_service.py").read_text(encoding="utf-8"))

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = {arg.arg for arg in node.args.args} | {arg.arg for arg in node.args.kwonlyargs}
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                names.add(sub.id)
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.keyword)
                and sub.arg == "gateway_account_id"
                and isinstance(sub.value, ast.Name)
                and sub.value.id not in names
            ):
                offenders.append(f"{node.name}: 引用了未定义的 {sub.value.id}")

    assert not offenders, "调用点引用了作用域内不存在的变量：\n  " + "\n  ".join(offenders)


def test_outbound_uses_the_account_bound_to_the_channel():
    """外发要用**渠道绑定的**账号，不是当前默认账号。

    渠道被账号 B 绑上却拿账号 A 的凭据外发：飞书 open_id 是应用级作用域，
    直接失败；微信在管理员切换默认账号后也会立刻用错凭据。
    """
    assert hasattr(MessageGatewayAccountService, "resolve_for_channel")

    source = inspect.getsource(UserMessageChannelService._deliver_gateway)
    assert source.count("resolve_for_channel(") == 2, "微信与飞书两条外发路径都要用绑定账号"
    assert "get_default_active(" not in source, "还在直接取默认账号"


def test_public_bind_endpoint_keeps_the_authenticated_account():
    """公开绑定入口不能丢掉鉴权拿到的账号。

    丢掉的话新绑定的渠道写成 NULL，而 NULL 是"存量待认领"的语义——
    等于持续制造新的跨账号冒充窗口。
    """
    source = (BACKEND / "app/api/v1/endpoints/message_channels.py").read_text(encoding="utf-8")

    assert "gateway_account_id=auth.gateway_account_id" in source
    assert 'f"gateway-account:{auth.gateway_account_id}"' in source, (
        "已签名请求的限流来源要按账号固定，否则轮换 external user 就能绕开失败计数"
    )


def test_default_gateway_lookup_imports_the_gateway_model() -> None:
    class FakeDb:
        async def scalar(self, _statement):  # noqa: ANN001
            return 1

    service = UserMessageChannelService(FakeDb())  # type: ignore[arg-type]
    assert asyncio.run(
        service._is_default_gateway_account(channel_type="wechat", gateway_account_id=5)  # noqa: SLF001
    )
