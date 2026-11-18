"""租户内任务编号：处理任务与生图任务各从 1 开始，互不串号。

2026-11-18 UX-P0-5：工作台/任务详情/积分流水统一使用「处理 #96 / 生图 #11」口径。
编号按 `id` 升序在租户内排名（软删除行不占号），与既有处理任务编号规则一致。
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.dialect import get_dialect

IMAGE_TABLE = "cap_realphotos_image_tasks"
GENERATION_TABLE = "cap_realphotos_generation_tasks"

_ALLOWED_TABLES = {IMAGE_TABLE, GENERATION_TABLE}


async def tenant_sequence_map(
    db: AsyncSession,
    *,
    table: str,
    tenant_id: int,
    ids: Iterable[int | str | None],
) -> dict[int, int]:
    """返回 `{row_id: 租户内序号}`；只计算请求中出现的 id。

    PostgreSQL 走窗口函数；SQLite 仅用于测试/轻量档，用 Python 侧枚举保证语义一致。
    """

    if table not in _ALLOWED_TABLES:
        raise ValueError(f"unsupported task table: {table}")
    wanted = {int(item) for item in ids if item is not None and str(item).strip() != ""}
    if not wanted:
        return {}

    if get_dialect().name == "sqlite":
        rows = (
            await db.execute(
                text(
                    f"select id from {table} "
                    "where tenant_id = :tenant_id and deleted_at is null order by id"
                ),
                {"tenant_id": int(tenant_id)},
            )
        ).all()
        result: dict[int, int] = {}
        for seq, (row_id,) in enumerate(rows, start=1):
            row_id = int(row_id)
            if row_id in wanted:
                result[row_id] = seq
        return result

    rows = (
        await db.execute(
            text(
                "select id, seq from ("
                "  select id, row_number() over (order by id) as seq"
                f"  from {table}"
                "  where tenant_id = :tenant_id and deleted_at is null"
                ") x where id = any(:ids)"
            ),
            {"tenant_id": int(tenant_id), "ids": sorted(wanted)},
        )
    ).all()
    return {int(row_id): int(seq) for row_id, seq in rows}


async def processing_task_no_map(
    db: AsyncSession, *, tenant_id: int, task_ids: Iterable[int | str | None]
) -> dict[int, int]:
    return await tenant_sequence_map(
        db, table=IMAGE_TABLE, tenant_id=tenant_id, ids=task_ids
    )


async def generation_task_no_map(
    db: AsyncSession, *, tenant_id: int, task_ids: Iterable[int | str | None]
) -> dict[int, int]:
    return await tenant_sequence_map(
        db, table=GENERATION_TABLE, tenant_id=tenant_id, ids=task_ids
    )


def format_task_no(kind: str, task_no: int | None, fallback_id: int | str | None = None) -> str:
    """统一展示口径：处理 #96 / 生图 #11；编号缺失时退回 `#id`。"""

    label = "处理" if kind == "processing" else "生图"
    number: int | str | None = task_no if task_no is not None else fallback_id
    return f"{label} #{number}" if number is not None else label
