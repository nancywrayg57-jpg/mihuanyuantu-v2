"""会话续期提醒：在渠道过期**之前**，用它自己去提醒用户回一句。

## 为什么需要

微信（iLink）的发送依赖 `context_token`，而这个 token 来自用户的**最后一条入站消息**。
太久没说话就会失效，发送报 `ret=-2`，我们只能事后给一句
"微信会话已过期，请先在微信 Channel 中发送一条新消息刷新会话"。

事后提示的问题是：**用户是在一条重要消息发失败之后才知道的**。日报、告警恰好
是那种"平时不看、要看的时候必须在"的东西，等它发失败再补救已经晚了。

## 过期时间从哪来：协议规定的 24 小时

iLink 协议里 `context_token` **随每条入站消息下发**，有效期 **24 小时**：
用户超过 24 小时没主动说话，token 失效，Bot 就再也无法触达他。
（协议本身的限制：iLink Bot 不能主动发起会话，只能在用户说话后的窗口内回复。）

所以过期时间是算出来的，不是问出来的：

    expires_at = last_inbound_at + 24 小时

**没有任何接口返回这个时间。** 已核实：官方协议文档里 `/ilink/bot/getconfig`
返回的是 `typing_ticket`，不是会话有效期；入站载荷也不带过期字段。
（本模块最初的写法是"调 getconfig 问过期"，那是建立在错误假设上的，已改正。）

`last_inbound_at` 我们本来就在维护——用户每发一条消息就刷新一次，
正好是这个 TTL 的起点。

## 不做的事

- **不自动续期**：续期必须由用户主动发消息，系统替他"保活"是绕过对方平台的会话规则
- **不反复打扰**：提醒过就记一笔，一个窗口内只提醒一次
- **不给已经过期的渠道发**：那时发也发不出去，只会在日志里刷失败
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.logger import get_logger
from app.domain.notifications.models import UserMessageChannel

logger = get_logger(__name__)

#: 只有会话会过期的渠道类型才需要提醒。
#: 企微/飞书走的是常驻网关或机器人，不依赖"用户最近说过话"。
SESSION_EXPIRING_CHANNEL_TYPES = frozenset({"wechat"})

#: iLink 协议规定的 context_token 有效期：用户最后一次说话之后 24 小时。
#: 这不是我们选的数字，是协议限制——超时之后 Bot 无法再触达用户。
WECHAT_CONTEXT_TOKEN_TTL_HOURS = 24

#: 距离过期还剩多久开始提醒。这个才是我们能选的：
#: 太早像骚扰，太晚用户来不及看。
REMIND_BEFORE_EXPIRY_HOURS = 6

#: 同一个渠道两次提醒的最小间隔。
MIN_REMIND_INTERVAL_HOURS = 24

#: 渠道 `extra` 里的开关与状态位。放 extra 是刻意的：
#: 这是个可选的提醒偏好，不值得为它加一列，也不该进业务配置以外的地方。
EXTRA_ENABLED_KEY = "renewalReminderEnabled"
EXTRA_LAST_REMINDED_KEY = "renewalReminderAt"
#: 会话过期时不丢消息：先保留，用户下次在渠道里发消息（token 刷新）后自动补发。
#: 默认关闭——保留意味着用户可能收到一批"迟到"的消息，得他点头。
EXTRA_HOLD_KEY = "holdUntilActiveEnabled"


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def reminder_enabled(channel: UserMessageChannel) -> bool:
    """默认**关闭**，用户在渠道设置里勾选后才触发。

    这是刻意的 opt-in：提醒会往用户的微信里推一条未经请求的消息，
    还会占用他自己的会话窗口。**替用户决定"你需要被提醒"是越界的**，
    哪怕出发点是好的。

    （最初写成默认开启，理由是"默认关掉等于默认让人踩坑"；
    产品定为 opt-in——主动打扰这件事应该由用户点头。）
    """
    extra = channel.extra if isinstance(channel.extra, dict) else {}
    return bool(extra.get(EXTRA_ENABLED_KEY))


#: 入站消息的**发生时间**（上游给的），写在 extra 里。
#: 优先用它而不是 `last_inbound_at`——后者是我们处理消息的时间。
EXTRA_INBOUND_ORIGIN_KEY = "lastInboundOriginAt"


def hold_enabled(channel: UserMessageChannel) -> bool:
    extra = getattr(channel, "extra", None)
    extra = extra if isinstance(extra, dict) else {}
    return bool(extra.get(EXTRA_HOLD_KEY)) and str(getattr(channel, "channel_type", "") or "") in SESSION_EXPIRING_CHANNEL_TYPES


def session_expired(channel: UserMessageChannel, moment: datetime | None = None) -> bool:
    """按协议 TTL 判定会话是否已过期；无法判定（没有入站记录）视为未过期。"""
    expires_at = resolve_expiry(channel)
    if expires_at is None:
        return False
    return (moment or _now()) >= expires_at


def resolve_expiry(channel: UserMessageChannel) -> datetime | None:
    """这个渠道的会话什么时候过期。没有入站记录则返回 None。

    协议规定 `context_token` 随入站消息下发、24 小时有效，
    所以过期时间就是"最后一次入站 + TTL"。不需要问上游——也问不到。

    起点优先取 `extra.lastInboundOriginAt`（上游给的消息发生时间），
    回落到 `last_inbound_at`（我们处理它的时间）。两者通常只差毫秒，
    但网关停机后补拉旧消息时能差几小时——那时用处理时间会把过期时间**高估**，
    提醒发出去时 token 其实已经失效。（codex 复核发现）
    """
    extra = channel.extra if isinstance(channel.extra, dict) else {}
    started_at = _parse_time(extra.get(EXTRA_INBOUND_ORIGIN_KEY)) or _parse_time(
        getattr(channel, "last_inbound_at", None)
    )
    if started_at is None:
        return None
    return started_at + timedelta(hours=WECHAT_CONTEXT_TOKEN_TTL_HOURS)


def needs_renewal_reminder(
    channel: UserMessageChannel,
    *,
    expires_at: datetime | None,
    now: datetime | None = None,
    remind_before_hours: int = REMIND_BEFORE_EXPIRY_HOURS,
) -> bool:
    """该不该提醒。纯函数，边界直接可测。

    `expires_at` 由调用方从上游拿；**为 None 时一律不提醒**——
    宁可什么都不做，也不按猜出来的时间打扰用户。
    """
    if channel.channel_type not in SESSION_EXPIRING_CHANNEL_TYPES:
        return False
    if channel.status != "active":
        return False
    if not reminder_enabled(channel):
        return False
    if expires_at is None:
        return False

    moment = now or _now()
    remaining = expires_at - moment
    if remaining <= timedelta(0):
        # 已经过期：这时发也发不出去，只会刷失败日志
        return False
    if remaining > timedelta(hours=remind_before_hours):
        return False

    extra = channel.extra if isinstance(channel.extra, dict) else {}
    last_reminded = _parse_time(extra.get(EXTRA_LAST_REMINDED_KEY))
    if last_reminded is not None and moment - last_reminded < timedelta(
        hours=MIN_REMIND_INTERVAL_HOURS
    ):
        return False
    return True


def build_reminder_text(channel: UserMessageChannel) -> tuple[str, str]:
    """提醒的标题与正文。写清"为什么收到"和"该做什么"，不然像骚扰。"""
    name = channel.name or "微信 Channel"
    return (
        "消息渠道即将失效",
        (
            f"你绑定的「{name}」快要失效了。\n\n"
            "微信的会话有效期依赖你最近一次主动发消息。"
            "**在这里回复任意一句话**即可续期，之后的通知才能正常送达。\n\n"
            "这条提醒是你在「个人设置 - 消息 Channel」里开启的，可以随时关掉。"
        ),
    )


async def send_renewal_reminders(
    db,
    *,
    now: datetime | None = None,
    remind_before_hours: int = REMIND_BEFORE_EXPIRY_HOURS,
    checkpoint=None,
) -> dict[str, int]:
    """扫描并发送续期提醒。返回 `{scanned, reminded, failed, unknownExpiry}`。

    `unknownExpiry` 计的是"从没入站过、算不出过期时间"的渠道——
    它们本来也发不出消息（没有可用的 context_token）。

    `checkpoint`（如 `db.commit`）在**每次成功发送并登记之后**调用：
    攒到最后一把提交的话，第 30 个渠道抛异常 = 前 29 条"已提醒"记录全部回滚，
    下一轮把它们再提醒一遍。和 message_relay 逐渠道落盘是同一个道理。
    """
    from app.domain.notifications.message_channels import UserMessageChannelService

    moment = now or _now()
    service = UserMessageChannelService(db)
    result = await db.execute(
        select(UserMessageChannel).where(
            UserMessageChannel.channel_type.in_(sorted(SESSION_EXPIRING_CHANNEL_TYPES)),
            UserMessageChannel.status == "active",
            UserMessageChannel.deleted_at.is_(None),
        )
    )
    channels = list(result.scalars().all())

    stats = {"scanned": len(channels), "reminded": 0, "failed": 0, "unknownExpiry": 0}
    for channel in channels:
        if not reminder_enabled(channel):
            continue
        expires_at = resolve_expiry(channel)
        if expires_at is None:
            stats["unknownExpiry"] += 1
            continue
        if not needs_renewal_reminder(
            channel, expires_at=expires_at, now=moment, remind_before_hours=remind_before_hours
        ):
            continue

        title, content = build_reminder_text(channel)
        try:
            ok, error = await service.deliver_to_channel(
                channel,
                title=title,
                content=content,
                message_type="notification",
                extra={"source": "channel_renewal_reminder"},
            )
        except Exception as exc:  # noqa: BLE001 - 单条失败不影响其余
            ok, error = False, type(exc).__name__
        if ok:
            # 只有**发成功**才记时间：发失败还记，等于把重试窗口一起关掉，
            # 一次网络抖动就让这个渠道永远等不到下一次提醒。
            #
            # 用 `merge_extra` 而不是整块写回：扫描时读到的 `extra` 到这里已经
            # 隔了一次外部发送，期间的入站写入（新 context token 等）会被陈旧快照覆盖。
            await service.merge_extra(channel, {EXTRA_LAST_REMINDED_KEY: moment.isoformat()})
            stats["reminded"] += 1
            if checkpoint is not None:
                await checkpoint()
        else:
            stats["failed"] += 1
            logger.info(
                "channel_renewal_reminder_failed",
                channel_id=int(channel.id),
                error=str(error)[:200],
            )
    return stats
