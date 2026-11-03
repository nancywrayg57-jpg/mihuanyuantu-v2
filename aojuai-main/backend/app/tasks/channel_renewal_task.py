"""会话续期提醒的定时入口。

**这个文件是补上来的。** 第一版只写了 `send_renewal_reminders()` 而没有任何调用方，
20 条单测全绿、功能却永远不会运行——正是本轮反复在别处修的那类"改了但不生效"。
codex 复核时一句话点破："典型的单测全绿，但生产入口没接上"。

每小时跑一次：微信 token 有效期 24 小时，提醒窗口是最后 6 小时，
一小时一次足够命中，也不会把扫描压力堆上去。
"""

from __future__ import annotations

from app.core.logger import get_logger

logger = get_logger(__name__)


async def channel_renewal_reminder_task() -> None:
    from app.core.task_queue import scheduler_job_lock
    from app.domain.notifications.channel_renewal import send_renewal_reminders
    from app.infrastructure.database import get_db_context

    # 跨进程互斥：APScheduler 的 max_instances=1 只约束本进程，
    # 多开一个 API 进程就是两份定时器，同一个用户会收到两条提醒。
    async with scheduler_job_lock("channel_renewal_reminder") as acquired:
        if not acquired:
            return
        async with get_db_context() as db:
            # 逐条提交（checkpoint）：外发是不可回滚的副作用，
            # "发了但登记被回滚"意味着下一轮重复打扰。
            stats = await send_renewal_reminders(db, checkpoint=db.commit)
            await db.commit()

    if stats["reminded"] or stats["failed"] or stats["unknownExpiry"]:
        logger.info("channel_renewal_reminders_done", **stats)
