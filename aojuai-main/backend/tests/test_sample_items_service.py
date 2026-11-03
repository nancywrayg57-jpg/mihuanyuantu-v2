from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.capabilities.sample_items.models import SampleItem
from app.capabilities.sample_items.service import SampleItemService


class AsyncSessionAdapter:
    def __init__(self, session: Session):
        self.session = session

    async def scalar(self, statement):  # noqa: ANN001
        return self.session.scalar(statement)

    async def execute(self, statement):  # noqa: ANN001
        return self.session.execute(statement)

    def add(self, instance: object) -> None:
        self.session.add(instance)

    async def flush(self) -> None:
        self.session.flush()

    async def refresh(self, instance: object) -> None:
        self.session.refresh(instance)


@pytest.fixture
def sample_service() -> tuple[SampleItemService, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SampleItem.__table__.create(engine)
    session = Session(engine)
    session.add_all(
        [
            SampleItem(id=1, tenant_id=10, code="one", name="Tenant one"),
            SampleItem(id=2, tenant_id=20, code="two", name="Tenant two"),
        ]
    )
    session.commit()
    try:
        yield SampleItemService(AsyncSessionAdapter(session)), session  # type: ignore[arg-type]
    finally:
        session.close()
        engine.dispose()


async def assert_cross_tenant_hidden(service: SampleItemService) -> None:
    assert await service.get_item(tenant_id=10, item_id=2) is None


@pytest.mark.asyncio
async def test_cross_tenant_reads_are_hidden_and_filter_mutation_is_detected(
    sample_service: tuple[SampleItemService, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = sample_service
    original_get_item = SampleItemService.get_item

    await assert_cross_tenant_hidden(service)

    # 变异：把租户条件从查询里拿掉，跨租户就该能读到——读不到说明这条测试
    # 根本没在验租户隔离（它可能只是碰巧被别的条件挡住了）。
    async def get_item_without_tenant_filter(self, *, tenant_id: int, item_id: int):
        return await self.get_one(where=[SampleItem.id == item_id])

    monkeypatch.setattr(SampleItemService, "get_item", get_item_without_tenant_filter)
    with pytest.raises(AssertionError):
        await assert_cross_tenant_hidden(service)

    monkeypatch.setattr(SampleItemService, "get_item", original_get_item)
    await assert_cross_tenant_hidden(service)


async def assert_soft_deleted_hidden(service: SampleItemService) -> None:
    assert await service.get_item(tenant_id=10, item_id=1) is None


@pytest.mark.asyncio
async def test_soft_deleted_rows_are_hidden_and_filter_mutation_is_detected(
    sample_service: tuple[SampleItemService, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = sample_service
    await service.delete_item(tenant_id=10, item_id=1)
    await assert_soft_deleted_hidden(service)

    original_get_item = SampleItemService.get_item

    # 变异：绕过基类的软删除过滤，软删掉的行就该重新可见。
    async def get_item_including_deleted(self, *, tenant_id: int, item_id: int):
        return await self.get_one(
            where=[SampleItem.id == item_id, SampleItem.tenant_id == tenant_id],
            include_deleted=True,
        )

    monkeypatch.setattr(SampleItemService, "get_item", get_item_including_deleted)
    with pytest.raises(AssertionError):
        await assert_soft_deleted_hidden(service)

    monkeypatch.setattr(SampleItemService, "get_item", original_get_item)
    await assert_soft_deleted_hidden(service)
