"""租户隔离与归属越权：真跑 SQL，不是断言"代码里写了 tenant_id"。

这三条是所有多租户业务表的最低要求：
- 跨租户读不到（404，不是 403：403 会泄漏"这里有一条工单"）
- 同租户他人读不到（同上）
- 列表/统计只统计本租户
"""

from __future__ import annotations

import pytest

from app.capabilities.support.models import SupportTicket
from app.capabilities.support.schemas import TicketCreate, TicketUpdate
from app.capabilities.support.service import SupportService
from app.core.exceptions import BusinessError, NotFoundError

TENANT_A = 4001
TENANT_B = 4002
USER_A = 91
USER_B = 92
AGENT = 99


def _payload(subject: str = "printer is on fire") -> TicketCreate:
    return TicketCreate(subject=subject, description="it started smoking", category="incident")


@pytest.mark.asyncio
async def test_ticket_is_scoped_to_its_tenant(db) -> None:
    service = SupportService(db)
    mine = await service.create_ticket(tenant_id=TENANT_A, user_id=USER_A, data=_payload())

    with pytest.raises(NotFoundError):
        await service.get_ticket(tenant_id=TENANT_B, ticket_id=mine.id)

    rows, total = await service.list_tickets(tenant_id=TENANT_B, page=1, page_size=20)
    assert rows == [] and total == 0
    assert (await service.summary(tenant_id=TENANT_B))["total"] == 0
    assert (await service.summary(tenant_id=TENANT_A))["total"] == 1


@pytest.mark.asyncio
async def test_owner_scope_hides_another_users_ticket_in_the_same_tenant(db) -> None:
    service = SupportService(db)
    theirs = await service.create_ticket(tenant_id=TENANT_A, user_id=USER_B, data=_payload())

    # 本人可读
    assert (
        await service.get_ticket(
            tenant_id=TENANT_A, ticket_id=theirs.id, owner_user_id=USER_B
        )
    ).id == theirs.id
    # 同租户他人 404
    with pytest.raises(NotFoundError):
        await service.get_ticket(tenant_id=TENANT_A, ticket_id=theirs.id, owner_user_id=USER_A)
    # 客服台（不带 owner 约束）可读
    assert (await service.get_ticket(tenant_id=TENANT_A, ticket_id=theirs.id)).id == theirs.id


@pytest.mark.asyncio
async def test_cross_tenant_admin_write_cannot_reach_another_tenants_ticket(db) -> None:
    service = SupportService(db)
    ticket = await service.create_ticket(tenant_id=TENANT_A, user_id=USER_A, data=_payload())

    with pytest.raises(NotFoundError):
        await service.update_ticket(
            tenant_id=TENANT_B,
            ticket_id=ticket.id,
            user_id=AGENT,
            data=TicketUpdate(status="closed"),
        )
    with pytest.raises(NotFoundError):
        await service.add_admin_message(
            tenant_id=TENANT_B, ticket_id=ticket.id, user_id=AGENT, body="hello"
        )


@pytest.mark.asyncio
async def test_ticket_number_and_initial_message_are_created(db) -> None:
    service = SupportService(db)
    ticket = await service.create_ticket(tenant_id=TENANT_A, user_id=USER_A, data=_payload())

    assert ticket.ticket_no == f"SUP-{TENANT_A}-{ticket.id:06d}"
    assert [message.message_type for message in ticket.messages] == ["initial"]
    assert ticket.status == "open"


@pytest.mark.asyncio
async def test_internal_notes_never_reach_the_requester_payload(db) -> None:
    service = SupportService(db)
    ticket = await service.create_ticket(tenant_id=TENANT_A, user_id=USER_A, data=_payload())
    await service.add_admin_message(
        tenant_id=TENANT_A,
        ticket_id=ticket.id,
        user_id=AGENT,
        body="requester must never see this",
        is_internal=True,
    )
    refreshed = await service.get_ticket(
        tenant_id=TENANT_A, ticket_id=ticket.id, owner_user_id=USER_A
    )

    user_view = service.ticket_payload(refreshed, include_messages=True)
    admin_view = service.ticket_payload(refreshed, include_messages=True, include_internal=True)

    assert all(not message["isInternal"] for message in user_view["messages"])
    assert any(message["isInternal"] for message in admin_view["messages"])


@pytest.mark.asyncio
async def test_status_transitions_and_closed_ticket_guard(db) -> None:
    service = SupportService(db)
    ticket = await service.create_ticket(tenant_id=TENANT_A, user_id=USER_A, data=_payload())

    await service.add_admin_message(
        tenant_id=TENANT_A, ticket_id=ticket.id, user_id=AGENT, body="looking into it"
    )
    assert (await service.get_ticket(tenant_id=TENANT_A, ticket_id=ticket.id)).status == "pending"

    await service.update_ticket(
        tenant_id=TENANT_A, ticket_id=ticket.id, user_id=AGENT, data=TicketUpdate(status="closed")
    )
    with pytest.raises(BusinessError):
        await service.add_user_message(
            tenant_id=TENANT_A, ticket_id=ticket.id, user_id=USER_A, body="one more thing"
        )


@pytest.mark.asyncio
async def test_soft_deleted_ticket_disappears_from_reads(db) -> None:
    service = SupportService(db)
    ticket = await service.create_ticket(tenant_id=TENANT_A, user_id=USER_A, data=_payload())
    await service.delete(ticket)

    with pytest.raises(NotFoundError):
        await service.get_ticket(tenant_id=TENANT_A, ticket_id=ticket.id)
    rows, total = await service.list_tickets(tenant_id=TENANT_A, page=1, page_size=20)
    assert rows == [] and total == 0


@pytest.mark.asyncio
async def test_keyword_and_related_filters_stay_within_the_tenant(db) -> None:
    service = SupportService(db)
    await service.create_ticket(
        tenant_id=TENANT_A,
        user_id=USER_A,
        data=TicketCreate(
            subject="invoice question", description="about the invoice", category="billing"
        ),
    )
    await service.create_anonymous_ticket(
        tenant_id=TENANT_B,
        subject="invoice question",
        description="about the invoice",
        related_type="public_contact",
    )

    rows, total = await service.list_tickets(
        tenant_id=TENANT_A, page=1, page_size=20, keyword="invoice"
    )
    assert total == 1
    assert rows[0].tenant_id == TENANT_A

    rows, total = await service.list_tickets(
        tenant_id=TENANT_A, page=1, page_size=20, related_type="public_contact"
    )
    assert total == 0


@pytest.mark.asyncio
async def test_anonymous_ticket_uses_the_sentinel_requester(db) -> None:
    from app.capabilities.support.models import ANONYMOUS_REQUESTER_ID

    service = SupportService(db)
    ticket = await service.create_anonymous_ticket(
        tenant_id=TENANT_A,
        subject="hello",
        description="from a visitor",
        category="not-a-real-category",
        priority="not-a-real-priority",
    )

    assert ticket.requester_user_id == ANONYMOUS_REQUESTER_ID
    assert ticket.created_by is None
    # 未知取值被收敛到白名单，而不是原样落库
    assert ticket.category == "other"
    assert ticket.priority == "normal"
    assert isinstance(ticket, SupportTicket)
