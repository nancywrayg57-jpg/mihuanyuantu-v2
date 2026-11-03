"""Tenant-safe sample CRUD; every read and write scopes by ``tenant_id``.

继承 `RepositoryBase` 是基座的既定约定（14 个域里 12 个都这么写），
它已经处理软删除过滤、分页与计数、更新/软删除的落库细节。
样例模块是新模块要照抄的模板，**必须跟主线一致**，不要另起一套手写查询——
否则每个从这里复制出去的模块都会偏离基座约定。

租户过滤不在基类里，仍由本层每个方法显式带上：
基类不知道"当前租户是谁"，把它交给基类反而会让越权变成隐式行为。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.infrastructure.repository import RepositoryBase

from .models import SampleItem
from .schemas import Create, Update


class SampleItemService(RepositoryBase[SampleItem]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, SampleItem)

    async def list_items(
        self,
        *,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SampleItem], int]:
        rows, total = await self.get_list(
            page=page,
            page_size=page_size,
            where=[SampleItem.tenant_id == tenant_id],
            order_by="id",
            order_desc=True,
            return_total=True,
        )
        return list(rows), int(total or 0)

    async def get_item(self, *, tenant_id: int, item_id: int) -> SampleItem | None:
        return await self.get_one(
            where=[
                SampleItem.id == item_id,
                SampleItem.tenant_id == tenant_id,
            ]
        )

    async def require_item(self, *, tenant_id: int, item_id: int) -> SampleItem:
        item = await self.get_item(tenant_id=tenant_id, item_id=item_id)
        if item is None:
            raise NotFoundError(message="样例条目不存在")
        return item

    async def _code_exists(
        self,
        *,
        tenant_id: int,
        code: str,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(SampleItem.id).where(
            SampleItem.code == code,
            SampleItem.tenant_id == tenant_id,
            SampleItem.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(SampleItem.id != exclude_id)
        return await self.db.scalar(stmt) is not None

    async def create_item(self, *, tenant_id: int, data: Create) -> SampleItem:
        if await self._code_exists(tenant_id=tenant_id, code=data.code):
            raise ConflictError(message="当前租户已存在相同编码")
        return await self.create({"tenant_id": tenant_id, **data.model_dump()})

    async def update_item(
        self,
        *,
        tenant_id: int,
        item_id: int,
        data: Update,
    ) -> SampleItem:
        item = await self.require_item(tenant_id=tenant_id, item_id=item_id)
        changes = data.model_dump(exclude_unset=True)
        next_code = changes.get("code")
        if next_code is not None and await self._code_exists(
            tenant_id=tenant_id,
            code=next_code,
            exclude_id=item.id,
        ):
            raise ConflictError(message="当前租户已存在相同编码")
        return await self.update(item, changes)

    async def delete_item(self, *, tenant_id: int, item_id: int) -> None:
        item = await self.require_item(tenant_id=tenant_id, item_id=item_id)
        await self.delete(item)
