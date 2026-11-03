"""会话续期提醒的边界。

微信发送依赖用户最后一条入站消息带来的 `context_token`；太久没说话就失效。
原来只能事后给一句"会话已过期"——而用户是在**一条重要消息发失败之后**才知道的。
这里在它还能用的时候，用它自己提醒用户回一句。

边界都很容易写错，所以逐条钉死：太早不提醒、太晚不提醒（那时已经发不出去）、
提醒过不重复、关掉了就不发、不该管的渠道类型不碰。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.domain.notifications.channel_renewal import (
    EXTRA_ENABLED_KEY,
    EXTRA_LAST_REMINDED_KEY,
    REMIND_BEFORE_EXPIRY_HOURS,
    WECHAT_CONTEXT_TOKEN_TTL_HOURS,
    build_reminder_text,
    needs_renewal_reminder,
    reminder_enabled,
    resolve_expiry,
    send_renewal_reminders,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _channel(*, channel_type: str = "wechat", status: str = "active", extra=None, idle_hours: float = 0, opted_in: bool = True):
    return SimpleNamespace(
        id=1,
        name="我的微信",
        channel_type=channel_type,
        status=status,
        external_user_id="wx-user",
        last_inbound_at=NOW - timedelta(hours=idle_hours),
        # 默认关闭，所以除非用例专门测开关，一律显式开启。
        # 这里是**合并**不是替换：传了 extra 的用例（如"最近提醒过"）
        # 仍然需要带上开关，否则会因为"没开启"而提前返回，测不到真正想测的分支。
        extra={**({EXTRA_ENABLED_KEY: True} if opted_in else {}), **(extra or {})},
    )


def _in(hours: float):
    """还剩多久过期。"""
    return NOW + timedelta(hours=hours)


def test_not_reminded_while_still_far_from_expiry():
    """离过期还早就提醒 = 骚扰。"""
    assert needs_renewal_reminder(_channel(), expires_at=_in(REMIND_BEFORE_EXPIRY_HOURS + 1), now=NOW) is False


def test_reminded_inside_the_window():
    assert needs_renewal_reminder(_channel(), expires_at=_in(REMIND_BEFORE_EXPIRY_HOURS - 1), now=NOW) is True


def test_not_reminded_after_it_already_expired():
    """已经过期时发也发不出去，只会刷失败日志。"""
    assert needs_renewal_reminder(_channel(), expires_at=NOW - timedelta(minutes=1), now=NOW) is False


def test_unknown_expiry_never_reminds():
    """**拿不到过期时间就什么都不做。**

    这是这个模块的核心约定：上游没告诉我们剩多久，就不要按猜出来的时间打扰用户。
    """
    assert needs_renewal_reminder(_channel(), expires_at=None, now=NOW) is False


def test_not_reminded_twice_in_the_same_window():
    """提醒过就记一笔，一个窗口内只提醒一次。"""
    recent = (NOW - timedelta(hours=2)).isoformat()
    channel = _channel(extra={EXTRA_LAST_REMINDED_KEY: recent})

    assert needs_renewal_reminder(channel, expires_at=_in(1), now=NOW) is False


def test_reminded_again_after_the_interval():
    old = (NOW - timedelta(hours=30)).isoformat()
    channel = _channel(extra={EXTRA_LAST_REMINDED_KEY: old})

    assert needs_renewal_reminder(channel, expires_at=_in(1), now=NOW) is True


def test_default_is_off_until_the_user_opts_in():
    """**默认关闭。** 提醒会往用户微信推一条未经请求的消息、还占用他的会话窗口，
    替他决定"你需要被提醒"是越界的——哪怕出发点是好的。"""
    assert reminder_enabled(_channel(opted_in=False)) is False
    assert needs_renewal_reminder(_channel(opted_in=False), expires_at=_in(1), now=NOW) is False


def test_opting_in_enables_it():
    channel = _channel(extra={EXTRA_ENABLED_KEY: True})

    assert reminder_enabled(channel) is True
    assert needs_renewal_reminder(channel, expires_at=_in(1), now=NOW) is True


def test_switch_off_is_respected():
    channel = _channel(opted_in=False, extra={EXTRA_ENABLED_KEY: False})

    assert needs_renewal_reminder(channel, expires_at=_in(1), now=NOW) is False


@pytest.mark.parametrize("channel_type", ["wecom", "feishu", "webhook"])
def test_other_channel_types_are_left_alone(channel_type):
    """企微/飞书/Webhook 不依赖"用户最近说过话"，不该收到这种提醒。"""
    assert needs_renewal_reminder(_channel(channel_type=channel_type), expires_at=_in(1), now=NOW) is False


def test_disabled_channel_is_left_alone():
    assert needs_renewal_reminder(_channel(status="disabled"), expires_at=_in(1), now=NOW) is False


# ------------------------------------------------------------------ 过期时间怎么算


def test_expiry_is_last_inbound_plus_protocol_ttl():
    """过期时间 = 最后一次入站 + 协议规定的 24 小时。

    这不是我们挑的数字：iLink 的 `context_token` 随入站消息下发、24 小时有效，
    超时后 Bot 无法再触达用户。**没有任何接口返回这个时间**——
    官方协议文档里 `/ilink/bot/getconfig` 返回的是 `typing_ticket`。
    """
    channel = _channel(idle_hours=10)

    assert resolve_expiry(channel) == NOW - timedelta(hours=10) + timedelta(
        hours=WECHAT_CONTEXT_TOKEN_TTL_HOURS
    )


def test_ttl_matches_the_protocol():
    """把协议常量本身钉住：改这个数字等于改协议假设，必须是有意的。"""
    assert WECHAT_CONTEXT_TOKEN_TTL_HOURS == 24


def test_no_inbound_means_no_computable_expiry():
    """从没入站过 → 算不出过期时间，也没有可用的 context_token，本来就发不出去。"""
    channel = _channel()
    channel.last_inbound_at = None

    assert resolve_expiry(channel) is None


def test_reminder_text_says_why_and_what_to_do():
    """提醒必须写清"为什么收到"和"该做什么"，否则像骚扰。"""
    title, content = build_reminder_text(_channel())

    assert "失效" in title
    assert "回复" in content
    assert "关掉" in content, "要告诉用户怎么退订"


# ------------------------------------------------------------------ 扫描


class _FakeService:
    def __init__(self, *, ok: bool) -> None:
        self.ok = ok
        self.sent: list[tuple[str, str]] = []
        self.updated: list[dict] = []

    async def deliver_to_channel(self, channel, *, title, content, message_type, extra):  # noqa: ANN001
        self.sent.append((title, content))
        return self.ok, None if self.ok else "会话已过期"

    async def merge_extra(self, channel, patch):  # noqa: ANN001
        # 真实实现走 PostgreSQL 的 JSONB `||`：**局部合并，不是读-改-写**。
        # 读-改-写的问题不是窗口大小而是它必然存在——外发期间的入站写入
        # 会被扫描时的陈旧快照覆盖。假对象照同样语义合并。
        self.updated.append({"extra": patch})
        channel.extra = {**(channel.extra or {}), **patch}

    async def update(self, channel, values):  # noqa: ANN001
        self.updated.append(values)
        channel.extra = values.get("extra", channel.extra)


class _FakeDB:
    def __init__(self, channels) -> None:
        self._channels = channels

    async def execute(self, _stmt):  # noqa: ANN001
        channels = self._channels

        class _Result:
            def scalars(self):
                return SimpleNamespace(all=lambda: channels)

        return _Result()


@pytest.mark.asyncio
async def test_successful_reminder_records_the_time(monkeypatch):
    channel = _channel(idle_hours=WECHAT_CONTEXT_TOKEN_TTL_HOURS - 1)
    service = _FakeService(ok=True)
    monkeypatch.setattr(
        "app.domain.notifications.message_channels.UserMessageChannelService",
        lambda _db: service,
    )

    stats = await send_renewal_reminders(_FakeDB([channel]), now=NOW)

    assert stats == {"scanned": 1, "reminded": 1, "failed": 0, "unknownExpiry": 0}
    assert service.updated[0]["extra"] == {EXTRA_LAST_REMINDED_KEY: NOW.isoformat()}, (
        "写回的应当只有这一个键——整块写回会覆盖外发期间的入站状态"
    )


@pytest.mark.asyncio
async def test_failed_reminder_does_not_record_the_time(monkeypatch):
    """发失败**不能**记时间。

    记了就等于把重试窗口一起关掉：下一轮扫描会因为"最近提醒过"而跳过，
    于是这个渠道再也等不到提醒——一次网络抖动就永久失守。
    """
    channel = _channel(idle_hours=WECHAT_CONTEXT_TOKEN_TTL_HOURS - 1)
    service = _FakeService(ok=False)
    monkeypatch.setattr(
        "app.domain.notifications.message_channels.UserMessageChannelService",
        lambda _db: service,
    )

    stats = await send_renewal_reminders(_FakeDB([channel]), now=NOW)

    assert stats == {"scanned": 1, "reminded": 0, "failed": 1, "unknownExpiry": 0}
    assert service.updated == [], "发失败却记了时间，重试窗口被关掉了"


@pytest.mark.asyncio
async def test_unknown_expiry_is_counted_and_nothing_is_sent(monkeypatch):
    """算不出过期时间时：不发、但要计数，让运维看得见有多少渠道从没入站过。"""
    channel = _channel()
    channel.last_inbound_at = None
    service = _FakeService(ok=True)
    monkeypatch.setattr(
        "app.domain.notifications.message_channels.UserMessageChannelService",
        lambda _db: service,
    )

    stats = await send_renewal_reminders(_FakeDB([channel]), now=NOW)

    assert stats == {"scanned": 1, "reminded": 0, "failed": 0, "unknownExpiry": 1}
    assert service.sent == []


# ------------------------------------------------------------------ 生产入口


def test_the_reminder_is_actually_scheduled():
    """**这个功能必须真的被调度。**

    第一版只写了 `send_renewal_reminders()` 而没有任何调用方：20 条单测全绿，
    功能却永远不会运行。codex 复核一句话点破——"典型的单测全绿，
    但生产入口没接上"。整场都在别处修这类毛病，自己却交了一个。

    所以这条不测行为，只测"它接上了"：任务在调度器里、且指向正确的函数。
    """
    from app.core.scheduler import register_tasks, scheduler

    register_tasks()
    job = scheduler.get_job("channel_renewal_reminder_job")

    assert job is not None, "续期提醒没有注册进调度器——功能不会运行"
    assert job.func.__name__ == "channel_renewal_reminder_task"


@pytest.mark.asyncio
async def test_task_entry_calls_the_scan(monkeypatch):
    """入口函数要真的调到扫描——注册了但调用别的东西同样等于没接上。"""
    from app.tasks import channel_renewal_task

    called: dict[str, bool] = {}

    async def fake_scan(_db, *, checkpoint=None):  # noqa: ANN001
        called["scan"] = True
        # 入口必须传逐条提交的钩子：不传的话，扫描中途崩溃会回滚
        # 已发送提醒的登记，下一轮重复打扰
        called["checkpoint"] = checkpoint is not None
        return {"scanned": 0, "reminded": 0, "failed": 0, "unknownExpiry": 0}

    class _Ctx:
        async def __aenter__(self):
            return SimpleNamespace(commit=_noop)

        async def __aexit__(self, *_args):
            return False

    async def _noop():
        return None

    monkeypatch.setattr(
        "app.domain.notifications.channel_renewal.send_renewal_reminders", fake_scan
    )
    monkeypatch.setattr("app.infrastructure.database.get_db_context", lambda: _Ctx())

    await channel_renewal_task.channel_renewal_reminder_task()

    assert called.get("scan") is True
    assert called.get("checkpoint") is True, "入口没有把 db.commit 作为 checkpoint 传进去"


@pytest.mark.asyncio
async def test_task_entry_skips_when_another_process_holds_the_lock(monkeypatch):
    """另一个进程在跑这一轮时，本进程必须直接跳过。

    APScheduler 的 max_instances=1 只约束本进程；不互斥的话，
    多开一个 API 进程 = 同一个用户每小时收到两条提醒。
    """
    from contextlib import asynccontextmanager

    from app.tasks import channel_renewal_task

    called: dict[str, bool] = {}

    async def fake_scan(*_args, **_kwargs):  # noqa: ANN002, ANN003
        called["scan"] = True
        return {}

    @asynccontextmanager
    async def busy_lock(_name):  # noqa: ANN001
        yield False  # 没抢到

    monkeypatch.setattr(
        "app.domain.notifications.channel_renewal.send_renewal_reminders", fake_scan
    )
    monkeypatch.setattr("app.core.task_queue.scheduler_job_lock", busy_lock)

    await channel_renewal_task.channel_renewal_reminder_task()

    assert "scan" not in called, "没抢到锁还在扫描，两个进程会重复提醒"


@pytest.mark.asyncio
async def test_checkpoint_fires_after_each_successful_reminder(monkeypatch):
    """checkpoint 必须逐条触发，不能攒到最后。

    外发是不可回滚的副作用："发了 29 条、第 30 条抛异常导致整体回滚"
    意味着那 29 条的登记全丢，下一轮全部重复打扰。
    """
    from app.domain.notifications import channel_renewal

    channels = [
        _channel(idle_hours=WECHAT_CONTEXT_TOKEN_TTL_HOURS - 1) for _ in (1, 2, 3)
    ]
    service = _FakeService(ok=True)
    monkeypatch.setattr(
        "app.domain.notifications.message_channels.UserMessageChannelService",
        lambda _db: service,
    )
    commits: list[int] = []

    async def checkpoint():
        commits.append(len(service.sent))

    stats = await channel_renewal.send_renewal_reminders(
        _FakeDB(channels), now=NOW, checkpoint=checkpoint
    )

    assert stats["reminded"] == 3
    assert commits == [1, 2, 3], f"没有逐条提交：{commits}"


def test_expiry_prefers_the_upstream_message_time():
    """起点优先取上游给的消息发生时间，而不是我们处理它的时间。

    网关停机几小时后补拉旧消息时，两者能差出几小时——用处理时间会把过期时间
    **高估**，提醒发出去时 token 其实已经失效。（codex 复核发现）
    """
    from app.domain.notifications.channel_renewal import EXTRA_INBOUND_ORIGIN_KEY

    origin = NOW - timedelta(hours=5)
    channel = _channel(idle_hours=0, extra={EXTRA_INBOUND_ORIGIN_KEY: origin.isoformat()})

    # last_inbound_at 是 NOW（刚处理完），但真实发生时间是 5 小时前
    assert resolve_expiry(channel) == origin + timedelta(hours=WECHAT_CONTEXT_TOKEN_TTL_HOURS)


def test_expiry_falls_back_to_processing_time():
    """上游没给发生时间（非微信渠道、或旧数据）时回落，不能因此算不出来。"""
    channel = _channel(idle_hours=3)

    assert resolve_expiry(channel) == NOW - timedelta(hours=3) + timedelta(
        hours=WECHAT_CONTEXT_TOKEN_TTL_HOURS
    )
