"""队列 L0：任务的认领语义。

`app/core/worker_runtime.py` 统一了轮询骨架（L1），但**没有**统一"任务存哪、
怎么认领、崩了之后重跑还是判死"。结果是八套队列各写了一套语义：
四种僵尸窗口（300/900/1800/21600 秒）、三种认领标记的写法、两种相反的回收策略，
`ppt_master` 还把"判死+退积分"同时写在 worker 认领路径和**读路径**的收割函数里——
用户刷新页面会触发写操作，两处并发收割全靠 SKIP LOCKED 碰巧兜住。

完整盘点与迁移顺序见 `docs/dev/reference/TASK_QUEUE_TOP_LEVEL_DESIGN.md`。

## 这一层只解决五个问题

1. **交付语义**：崩了重跑（`at_least_once`）还是判死（`at_most_once`）。
   **没有默认值，必须显式写**——这正是原来缺的那句话。
   `message_relay` 重跑是对的（有幂等键），`ppt_master` 判死也可能是对的
   （生成要烧钱，盲目重跑等于重复扣费）。两个都对，错的是这件事原来是隐式的。
2. **重试上限与退避**
3. **租约**：僵尸窗口多长、执行期间是否续租
4. **公平性**：按哪一列排他，避免一个属主的积压把别人堵在身后
5. 准入（入队侧）不在这里——只有对外开放入站口的队列需要，见各自的 service

## 不做的

不引入 Redis / Celery。PostgreSQL 的 `SKIP LOCKED` 在当前量级完全够用，
多一个中间件就多一个部署依赖和一处故障域。
"""

from __future__ import annotations

import hashlib
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import and_, func, or_, select, text, update

from app.core.logger import get_logger
from app.infrastructure.database.dialect import get_dialect

logger = get_logger(__name__)

DeliverySemantics = Literal["at_least_once", "at_most_once"]


class LeaseLostError(RuntimeError):
    """租约已被别人接管。

    **必须与业务失败区分开**：把它当业务失败走 `record_failure()`，
    会把新持有者正在跑的任务放回队列甚至判死——旧 worker 反过来干掉了接管者。
    调用方捕获它之后应当放弃本条（不写任何结果），而不是登记失败。（codex 复核发现）
    """


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class QueuePolicy:
    """一个队列的交付语义。挂在 `WorkerDefinition.queue` 上。"""

    #: 崩溃后的处理方式。**必填，没有默认值。**
    #:
    #: - `at_least_once`：租约过期的行会被重新认领。前提是**副作用幂等**——
    #:   要么业务侧有幂等键，要么重复执行无害。
    #: - `at_most_once`：租约过期的行由 `reap_expired()` 判死，绝不重跑。
    #:   适用于"执行一次就产生了不可撤销的代价"（扣费、外发不可撤回的消息）。
    delivery: DeliverySemantics

    #: 认领后多久未续租算持有者已死。
    #:
    #: **没有心跳就只能把窗口设大。** 仓库里 harness / agent_worker 设到 21600 秒
    #: 正是因为执行期间不写任何东西，设小了会把还活着的长任务抢走。
    #: 想设小就得同时开 `renew_lease`——这是同一件事的两面。
    lease_seconds: int

    #: 最多尝试几次。`at_most_once` 只能是 1。
    max_attempts: int = 1

    #: 第 N 次失败后等多久再认领（秒）。空元组=立即重试。
    #: 长度不足时沿用最后一个值。
    retry_backoff_seconds: tuple[int, ...] = ()

    #: 公平键的列名。设了它，一个键值同时只会有一条在执行中。
    #:
    #: 纯 FIFO 会队头阻塞：一个用户灌 200 条，其他人全排在后面等，
    #: 而队列的意义本来就是"大家都能按时收到"。
    fairness_key: str | None = None

    #: 执行期间是否续租。开了才敢把 `lease_seconds` 设小。
    renew_lease: bool = False

    #: 各队列的状态取值不同（`queued`/`pending`、`delivering`/`running`），
    #: 不强行统一——改状态字符串要动历史数据，收益却只是好看。
    queued_status: str = "queued"
    running_status: str = "running"
    failed_status: str = "failed"

    def validate(self, *, source: str) -> None:
        if self.delivery not in ("at_least_once", "at_most_once"):
            raise ValueError(f"{source}: delivery 必须是 at_least_once 或 at_most_once")
        if self.lease_seconds <= 0:
            raise ValueError(f"{source}: lease_seconds 必须为正")
        if self.max_attempts < 1:
            raise ValueError(f"{source}: max_attempts 至少为 1")
        if self.delivery == "at_most_once" and self.max_attempts != 1:
            # 声明"绝不重跑"却又允许重试，两句话直接打架。
            # 这种矛盾正是本层要消灭的东西，不能自己先犯。
            raise ValueError(f"{source}: at_most_once 不能配 max_attempts>1")
        # 刻意**允许** at_most_once + renew_lease：还活着的昂贵长任务正需要
        # 心跳来防止 reaper 误判死。初版禁了这组合，理由（"不重跑，续租没意义"）
        # 把两件事搞混了——续租防的是被误收割，不是为了重跑。（codex 复核发现）

    def backoff_for(self, attempts: int) -> int:
        """第 `attempts` 次失败之后要等多少秒。"""
        if not self.retry_backoff_seconds:
            return 0
        index = min(max(int(attempts) - 1, 0), len(self.retry_backoff_seconds) - 1)
        return int(self.retry_backoff_seconds[index])


@dataclass
class ClaimStats:
    """一次认领的观测数据。让"为什么没认领到"可被回答。"""

    locked_wait: bool = False
    fairness_blocked: bool = False
    reclaimed_stale: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def queue_lock_key(table_name: str) -> int:
    """由表名推出的 advisory lock 键，跨进程稳定。

    刻意不用 PostgreSQL 的 `hashtext()`：那是个未文档化的内部函数，
    换大版本可能改哈希算法，而这个键必须在所有进程和所有版本上一致。
    """
    digest = hashlib.blake2b(table_name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


async def claim_one(
    db,
    model,
    *,
    policy: QueuePolicy,
    worker_id: str,
    extra_where: tuple = (),
    now: datetime | None = None,
    stats: ClaimStats | None = None,
):
    """认领一条待办并把它置为执行中。返回 ORM 行；没有可认领的返回 `None`。

    **调用方必须在拿到返回值后尽快提交。** 开了公平键时，本函数持有一把
    事务级 advisory lock，提交才释放；在提交前干活会让所有认领串行等待。
    正确的用法是：认领 → 立刻 commit → 另开会话执行。

    ## 公平键为什么要靠 advisory lock，而不是子查询

    "排除掉已经有一条在执行中的键值"这个子查询，在 READ COMMITTED 下
    **看不见别的事务尚未提交的 running 行**。两个 worker 同时认领时，
    A 已锁定并改写了属主 U 的一条但还没提交，B 的子查询里 U 仍然是空闲的，
    于是 B 又认领了 U 的另一条——公平性直接失效。
    `FOR UPDATE SKIP LOCKED` 挡不住这个：两条是不同的行，没有锁冲突。

    advisory lock 不走 MVCC，是锁管理器的状态，立刻对所有会话可见。
    拿到锁之后再取快照（READ COMMITTED 每条语句都取新快照），
    就一定能看到上一个认领者提交的结果。

    代价是同一队列的认领互相串行。这没关系：认领是一条走索引的语句（微秒级），
    而任务本身以秒计。**只在声明了公平键时才加锁**，其余队列这一步不存在。
    """
    table_name = model.__tablename__

    if policy.fairness_key:
        # bind 参数而不是拼串：这个键将来可能来自配置。
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:key)").bindparams(key=queue_lock_key(table_name))
        )
        if stats is not None:
            stats.locked_wait = True

    # 时间在**拿到锁之后**取：等锁可能等很久，锁前取的时间写进 claimed_at
    # 会让租约一落地就偏旧，极端情况下一提交就接近过期。（codex 复核发现）
    moment = now or _now()
    stale_before = moment - timedelta(seconds=policy.lease_seconds)
    status_col = model.status
    ready = or_(
        model.next_attempt_at.is_(None),
        model.next_attempt_at <= moment,
    )
    # 注意这里的括号：`(queued AND 已到退避时间) OR (running AND 租约过期)`。
    # 写成三项直接 OR 会让 `next_attempt_at IS NULL` 单独成立，
    # 于是连 failed 的行都能被认领——真实库上的用例当场抓到过这个。
    claimable = [and_(status_col == policy.queued_status, ready)]

    if policy.delivery == "at_least_once":
        # 租约过期的行可以重新认领：worker 被 kill 时会留下这种行，
        # 不回收就永远卡住。at_most_once 走 `reap_expired()` 判死，不在这里捡。
        claimable.append(
            and_(status_col == policy.running_status, model.claimed_at < stale_before)
        )

    where = [or_(*claimable)]
    if hasattr(model, "deleted_at"):
        where.append(model.deleted_at.is_(None))
    where.extend(extra_where)

    if policy.fairness_key:
        key_col = getattr(model, policy.fairness_key)
        busy = (
            select(key_col)
            .where(
                status_col == policy.running_status,
                model.claimed_at >= stale_before,
                *( [model.deleted_at.is_(None)] if hasattr(model, "deleted_at") else [] ),
            )
            .scalar_subquery()
        )
        where.append(key_col.notin_(busy))

    result = await db.execute(
        select(model)
        .where(*where)
        .order_by(model.created_at.asc(), model.id.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    if stats is not None and str(row.status) == policy.running_status:
        stats.reclaimed_stale = True
        logger.warning(
            "task_queue_reclaimed_stale",
            table=table_name,
            row_id=int(row.id),
            previous_owner=row.claimed_by,
            attempts=int(row.attempts or 0),
        )

    row.status = policy.running_status
    row.claimed_at = moment
    # **每次认领一个唯一 token**，不是进程 ID。同一进程有多个并发槽：
    # 槽 A 卡死、租约过期后被同进程的槽 B 接管时，进程 ID 完全相同，
    # A 醒来比对进程 ID 永远通过，照样覆盖 B 的成果。（codex 复核发现）
    # worker_id 保留在前半段，日志里仍能看出是谁的槽。
    row.claimed_by = f"{worker_id[:40]}#{secrets.token_hex(8)}"[:64]
    row.next_attempt_at = None
    await db.flush()
    return row


async def fence_ownership(db, model, *, row_id: int, token: str) -> bool:
    """终态提交前的所有权栅栏。返回 `False` = 行已不属于你，必须 rollback。

    续租带条件只保护了**续租这一步**；成功/部分成功的终态写入若不设防，
    旧 worker 在最后一次续租之后卡住、租约过期、被接管，醒来照样能把
    接管者的成果整体覆盖掉。（codex 复核发现）

    做法：一条 `claimed_by` 条件的空更新。rowcount=1 说明行还是你的，
    而且**这一步拿到了行锁**——认领方用的是 `SKIP LOCKED`，会跳过被锁的行，
    所以从这里到 commit 之间不可能再发生接管。栅栏必须是提交前的最后一步。

    注意本函数会触发 autoflush，把本事务的未提交修改先写进事务内——
    这无害：别人看不见未提交内容，栅栏失败整个事务回滚。
    """
    result = await db.execute(
        update(model)
        .where(model.id == int(row_id), model.claimed_by == str(token))
        .values(claimed_at=_now())
    )
    owned = int(getattr(result, "rowcount", 0) or 0) == 1
    if not owned:
        logger.warning(
            "task_queue_fence_rejected", table=model.__tablename__, row_id=int(row_id)
        )
    return owned


async def renew_lease(db, model, *, row_id: int, token: str, policy: QueuePolicy) -> bool:
    """续租。返回 `False` 表示租约已被别人接管，调用方应当停止写结果。

    实现是**带 claimed_by 条件的原子 UPDATE**，不是比对内存里的 ORM 值：
    `expire_on_commit=False` 的会话里，ORM 对象上的 `claimed_by` 是认领时的旧值，
    接管发生后它不会自己变——比对它永远通过，旧 worker 照样续租并覆盖结果。
    条件更新由数据库在行锁下判定，rowcount=0 就是"这条已经不属于你"。
    （codex 复核发现）
    """
    if not policy.renew_lease:
        return True
    result = await db.execute(
        update(model)
        .where(
            model.id == int(row_id),
            model.claimed_by == str(token),
            # 还要求仍在执行态：reap_expired 判死、人工重放都可能在票据未清的
            # 情况下改变状态，只比对票据会让旧 worker 在终态行上续租成功，
            # 然后接着往一条已判死的行里写结果。（codex 复核发现）
            model.status == policy.running_status,
        )
        .values(claimed_at=_now())
    )
    renewed = int(getattr(result, "rowcount", 0) or 0) == 1
    if not renewed:
        logger.warning(
            "task_queue_lease_lost",
            table=model.__tablename__,
            row_id=int(row_id),
            expected=str(token),
        )
    return renewed


def record_failure(row, *, policy: QueuePolicy, error: str | None = None) -> str:
    """登记一次失败，决定这一条是回队列还是判死。返回落定的状态。

    `attempts` 的口径是**完成的尝试**（成功或失败都算），认领本身不算——
    把僵尸回收记成一次尝试，任务可能一次都没真正执行过就被判死。
    业务侧在成功/部分成功的终态里自行 +1；全失败走这里统一 +1。
    """
    attempts = int(row.attempts or 0) + 1
    row.attempts = attempts
    if attempts >= policy.max_attempts:
        row.status = policy.failed_status
        row.next_attempt_at = None
    else:
        row.status = policy.queued_status
        backoff = policy.backoff_for(attempts)
        row.next_attempt_at = (_now() + timedelta(seconds=backoff)) if backoff else None
    if error is not None and hasattr(row, "error_summary"):
        row.error_summary = str(error)[:500]
    return str(row.status)


async def reap_expired(
    db,
    model,
    *,
    policy: QueuePolicy,
    limit: int = 50,
    now: datetime | None = None,
) -> list:
    """把租约过期的行判死，返回被判死的行，供调用方做退费之类的补偿。

    **只给 `at_most_once` 用。** `at_least_once` 的过期行由 `claim_one()`
    直接重新认领；判死逻辑必须只有一处（`ppt_master` 把同一套判死+退款
    写了两份、其中一份挂在读路径上，就是要避免的形态）。

    也刻意**不挂在读路径上**。判死是写操作，让"用户刷新页面"能决定一条任务
    的生死，本身就是设计错误。调用方应当把它放到 worker 或定时任务里。
    """
    if policy.delivery != "at_most_once":
        raise ValueError("reap_expired 只适用于 at_most_once；at_least_once 由 claim_one 回收")

    moment = now or _now()
    stale_before = moment - timedelta(seconds=policy.lease_seconds)
    where = [
        model.status == policy.running_status,
        model.claimed_at < stale_before,
    ]
    if hasattr(model, "deleted_at"):
        where.append(model.deleted_at.is_(None))

    result = await db.execute(
        select(model)
        .where(*where)
        .order_by(model.claimed_at.asc())
        .with_for_update(skip_locked=True)
        .limit(max(1, int(limit)))
    )
    rows = list(result.scalars().all())
    for row in rows:
        row.status = policy.failed_status
        if hasattr(row, "error_summary"):
            row.error_summary = f"租约超过 {policy.lease_seconds} 秒未续，判定执行进程已退出"
        logger.warning(
            "task_queue_reaped",
            table=model.__tablename__,
            row_id=int(row.id),
            previous_owner=row.claimed_by,
        )
    if rows:
        await db.flush()
    return rows


async def pending_depth(db, model, *, policy: QueuePolicy, extra_where: tuple = ()) -> int:
    """待办深度。准入控制与运维看板共用一个口径。"""
    where = [model.status.in_((policy.queued_status, policy.running_status))]
    if hasattr(model, "deleted_at"):
        where.append(model.deleted_at.is_(None))
    where.extend(extra_where)
    return int(await db.scalar(select(func.count()).select_from(model).where(*where)) or 0)


@asynccontextmanager
async def scheduler_job_lock(job_name: str):
    """定时任务的跨进程互斥。`yield` 出的布尔值 = 是否拿到了锁。

    APScheduler 的 `max_instances=1` 只约束**同一个进程**里的调度器；
    多开一个 API 进程就是多一份定时器，同一个 job 会在两边同时跑。
    仓库里原本只有 `poll_message_gateways` 自己处理了这件事
    （`app/tasks/message_gateway_task.py`），其余 job 都假设单进程——
    这里把那套做法抽成公共入口，job 逐个套上。

    用 **try**-lock 而不是阻塞锁：没拿到就说明另一个进程正在跑这一轮，
    本轮直接跳过即可，下个触发点再试。定时任务等锁没有意义。

    连接失败或方言不支持 advisory lock 时**放行**（返回 True）——
    单进程部署里锁本来就是多余的，不能让锁的可用性反过来卡住任务本身。
    """
    async with get_dialect().scheduler_job_lock(job_name) as acquired:
        yield acquired
