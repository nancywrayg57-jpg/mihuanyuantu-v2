"""Message gateway polling tasks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.core.logger import get_logger
from app.core.task_queue import scheduler_job_lock
from app.domain.notifications.gateway_service import (
    MessageGatewayAccountService,
    poll_pending_feishu_registrations,
    poll_pending_wechat_logins,
    poll_wechat_gateway_account_isolated,
)
from app.infrastructure.database.portable_sql import table_exists
from app.infrastructure.database.session import get_db_context

logger = get_logger(__name__)
_MESSAGE_GATEWAY_POLL_LOCK_KEY = 480281904
_MISSING_SCHEMA_WARNED: set[str] = set()
_MISSING_SCHEMA_NEXT_CHECK_AT: dict[str, float] = {}
_MISSING_SCHEMA_RECHECK_SECONDS = 300.0


async def _message_gateway_tables_ready(db, *, task_name: str) -> bool:
    required_tables = {"message_gateway_accounts", "user_message_channels"}
    cache_key = ",".join(sorted(required_tables))
    now = time.monotonic()
    if now < _MISSING_SCHEMA_NEXT_CHECK_AT.get(cache_key, 0.0):
        return False

    try:
        existing = {name for name in required_tables if await table_exists(db, name)}
    except Exception:
        logger.debug("message_gateway_schema_check_failed", task=task_name, exc_info=True)
        return True

    missing = sorted(required_tables - existing)
    if not missing:
        _MISSING_SCHEMA_NEXT_CHECK_AT.pop(cache_key, None)
        return True

    _MISSING_SCHEMA_NEXT_CHECK_AT[cache_key] = now + _MISSING_SCHEMA_RECHECK_SECONDS
    warn_key = ",".join(missing)
    if warn_key not in _MISSING_SCHEMA_WARNED:
        _MISSING_SCHEMA_WARNED.add(warn_key)
        logger.warning(
            "message_gateway_task_skipped_missing_tables",
            task=task_name,
            missing_tables=missing,
            hint="Run Alembic revisions for user message channels before enabling message gateway background tasks.",
        )
    return False


@asynccontextmanager
async def _message_gateway_poll_lock() -> AsyncGenerator[bool, None]:
    """跨进程互斥走公共入口 `scheduler_job_lock`（PG advisory lock；SQLite 单进程直接放行）。"""
    async with scheduler_job_lock("message_gateway_poll") as acquired:
        yield acquired


async def poll_message_gateways() -> None:
    """Poll active system message gateways and bind inbound personal channels."""
    async with get_db_context() as db:
        if not await _message_gateway_tables_ready(db, task_name="poll_message_gateways"):
            return

    async with _message_gateway_poll_lock() as lock_acquired:
        if not lock_acquired:
            logger.debug("message_gateway_poll_skipped_locked")
            return

        async with get_db_context() as db:
            service = MessageGatewayAccountService(db)
            processed = 0
            processed += await poll_pending_wechat_logins(db)
            processed += await poll_pending_feishu_registrations(db)
            accounts = await service.get_active_accounts("wechat")
            account_ids = [int(account.id) for account in accounts if getattr(account, "id", None) is not None]
            await db.commit()
            if account_ids:
                account_results = await asyncio.gather(
                    *(poll_wechat_gateway_account_isolated(account_id) for account_id in account_ids),
                    return_exceptions=True,
                )
                for account_id, result in zip(account_ids, account_results, strict=False):
                    if isinstance(result, Exception):
                        logger.warning(
                            "message_gateway_account_poll_failed",
                            account_id=account_id,
                            error_type=type(result).__name__,
                            error=str(result),
                        )
                        continue
                    processed += int(result or 0)
            if account_ids or processed:
                logger.info("message_gateways_polled", accounts=len(account_ids), processed=processed)


async def ensure_message_gateway_websockets() -> None:
    """Ensure long-connection message gateway receivers are running."""
    from app.domain.notifications.feishu_ws_client import ensure_feishu_gateway_ws
    from app.domain.notifications.wecom_ws_client import ensure_wecom_channel_ws

    # 长连接任务字典只保存本进程状态；若跨进程互斥，未持锁进程将缺少自己的接收连接。
    async with get_db_context() as db:
        if not await _message_gateway_tables_ready(db, task_name="ensure_message_gateway_websockets"):
            return

    await ensure_feishu_gateway_ws()
    await ensure_wecom_channel_ws()


def register_message_gateway_shutdown() -> None:
    """把通知域的长连接收尾注册给调度器。

    内核的 scheduler 不认识通知域，由这里主动注册；
    模块自己负责自己的关停，而不是让内核去 import 模块。
    """
    from app.core.scheduler import register_shutdown_hook

    async def _stop() -> None:
        from app.domain.notifications.feishu_ws_client import stop_feishu_gateway_ws

        await stop_feishu_gateway_ws()

        from app.domain.notifications.wecom_ws_client import stop_wecom_channel_ws

        await stop_wecom_channel_ws()

    register_shutdown_hook(_stop)
