"""
AOJU Backend - Scheduled Tasks Scheduler

定时任务调度器模块，基于 APScheduler 实现。
支持多个定时任务的统一管理，包括间隔任务和 Cron 任务。

使用方式：
1. 在 app/tasks/ 目录下创建任务文件
2. 在 register_tasks() 函数中注册任务
3. 应用启动时自动启动调度器

示例：
    from app.core.scheduler import scheduler
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler.add_job(
        my_task_function,
        trigger=IntervalTrigger(minutes=30),
        id='my_task_job',
        name='我的定时任务',
        replace_existing=True
    )
"""
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# 全局调度器实例
scheduler = AsyncIOScheduler()

# 关停钩子。内核不认识任何业务/能力域：需要在调度器停止时收尾的模块
# （例如通知域的飞书长连接）自己 register_shutdown_hook 进来。
# 之前这里直接 import app.domain.notifications 的客户端，等于内核认识了通知域。
_SHUTDOWN_HOOKS: list[Callable[[], Awaitable[None]]] = []


def register_shutdown_hook(hook: Callable[[], Awaitable[None]]) -> None:
    """Register an async callable to run after the scheduler stops."""
    if hook not in _SHUTDOWN_HOOKS:
        _SHUTDOWN_HOOKS.append(hook)


def register_tasks() -> None:
    """
    注册所有定时任务

    在此处添加需要定时执行的任务。
    任务函数需要是异步函数（async def）。
    """

    if settings.MESSAGE_GATEWAY_TASKS_ENABLED:
        from app.tasks.message_gateway_task import (
            ensure_message_gateway_websockets,
            poll_message_gateways,
            register_message_gateway_shutdown,
        )

        register_message_gateway_shutdown()

        scheduler.add_job(
            poll_message_gateways,
            trigger=IntervalTrigger(seconds=max(5, int(settings.MESSAGE_GATEWAY_POLL_INTERVAL_SECONDS or 20))),
            id="message_gateway_poll_job",
            name="消息 Channel 网关轮询",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        scheduler.add_job(
            ensure_message_gateway_websockets,
            trigger=IntervalTrigger(seconds=10),
            id="message_gateway_ws_job",
            name="消息 Channel 长连接守护",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # 会话续期提醒：微信 context_token 有效期 24 小时（协议规定），到期前用渠道自己提醒用户回一句。
    # notifications 是 base 域，与网关任务并列注册；扫描本身在没有可续期渠道时是 no-op，
    # 跨进程互斥走 scheduler_job_lock。
    from app.tasks.channel_renewal_task import channel_renewal_reminder_task

    scheduler.add_job(
        channel_renewal_reminder_task,
        trigger=IntervalTrigger(hours=1),
        id="channel_renewal_reminder_job",
        name="消息渠道会话续期提醒",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 业务分支的定时任务由组合层登记（纯 base 返回空）——内核 scheduler 里不出现业务名
    from app.core.composition import register_scheduler_jobs

    plugin_jobs = register_scheduler_jobs(scheduler)
    if plugin_jobs:
        logger.info("plugin_scheduler_jobs_registered", jobs=list(plugin_jobs))

    logger.info("scheduled_tasks_registered", task_count=len(scheduler.get_jobs()))


async def start_scheduler() -> None:
    """
    启动定时任务调度器

    在应用启动时调用，会自动注册并启动所有定时任务。
    """
    if not settings.SCHEDULER_ENABLED:
        logger.info("scheduler_disabled")
        return

    try:
        # 注册任务
        register_tasks()

        # 启动调度器
        if not scheduler.get_jobs():
            logger.info("scheduler_no_jobs_registered")
            return

        if not scheduler.running:
            scheduler.start()
            logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))

            # 打印已注册的任务
            for job in scheduler.get_jobs():
                logger.info(
                    "scheduled_job_registered",
                    job_id=job.id,
                    job_name=job.name,
                    next_run=str(job.next_run_time) if job.next_run_time else None
                )
    except Exception as e:
        logger.error("scheduler_start_failed", error=str(e))
        raise


async def stop_scheduler() -> None:
    """
    停止定时任务调度器

    在应用关闭时调用，优雅地停止所有定时任务。
    """
    try:
        if scheduler.running:
            scheduler.shutdown(wait=True)
            logger.info("scheduler_stopped")
        for hook in list(_SHUTDOWN_HOOKS):
            try:
                await hook()
            except Exception as e:
                logger.warning(
                    "scheduler_shutdown_hook_failed",
                    hook=getattr(hook, "__qualname__", repr(hook)),
                    error=str(e),
                )
    except Exception as e:
        logger.error("scheduler_stop_failed", error=str(e))


def add_interval_task(
    func: Callable,
    task_id: str,
    task_name: str,
    minutes: int = 0,
    hours: int = 0,
    seconds: int = 0,
) -> None:
    """
    添加间隔执行任务

    Args:
        func: 任务函数（异步函数）
        task_id: 任务唯一标识
        task_name: 任务名称（用于日志）
        minutes: 间隔分钟数
        hours: 间隔小时数
        seconds: 间隔秒数
    """
    scheduler.add_job(
        func,
        trigger=IntervalTrigger(
            hours=hours,
            minutes=minutes,
            seconds=seconds
        ),
        id=task_id,
        name=task_name,
        replace_existing=True
    )
    logger.info(
        "interval_task_added",
        task_id=task_id,
        task_name=task_name,
        interval_hours=hours,
        interval_minutes=minutes,
        interval_seconds=seconds
    )


def add_cron_task(
    func: Callable,
    task_id: str,
    task_name: str,
    hour: int | str = "*",
    minute: int | str = "0",
    second: int | str = "0",
    day: int | str = "*",
    month: int | str = "*",
    day_of_week: int | str = "*",
) -> None:
    """
    添加 Cron 定时任务

    Args:
        func: 任务函数（异步函数）
        task_id: 任务唯一标识
        task_name: 任务名称（用于日志）
        hour: 小时 (0-23)
        minute: 分钟 (0-59)
        second: 秒 (0-59)
        day: 日期 (1-31)
        month: 月份 (1-12)
        day_of_week: 星期几 (0-6, 0=周一)
    """
    scheduler.add_job(
        func,
        trigger=CronTrigger(
            hour=hour,
            minute=minute,
            second=second,
            day=day,
            month=month,
            day_of_week=day_of_week
        ),
        id=task_id,
        name=task_name,
        replace_existing=True
    )
    logger.info(
        "cron_task_added",
        task_id=task_id,
        task_name=task_name,
        cron_expression=f"{second} {minute} {hour} {day} {month} {day_of_week}"
    )


def remove_task(task_id: str) -> bool:
    """
    移除定时任务

    Args:
        task_id: 任务唯一标识

    Returns:
        是否成功移除
    """
    try:
        scheduler.remove_job(task_id)
        logger.info("task_removed", task_id=task_id)
        return True
    except Exception as e:
        logger.warning("task_remove_failed", task_id=task_id, error=str(e))
        return False


def get_all_jobs() -> list[dict]:
    """
    获取所有已注册的定时任务

    Returns:
        任务列表，每个任务包含 id, name, next_run_time
    """
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    return jobs
