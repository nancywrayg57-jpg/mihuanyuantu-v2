"""Thin HTTP adapter for the support capability.

路由只做参数校验 / 依赖注入 / 调用 Service。每条需要授权的路由都挂一个
`PermissionChecker`，权限码与 `access.py` 里的按钮一一对应。

`/public/tickets` 是本包**自己拥有**的匿名入口：租户由内核的公开主机解析
（`resolve_public_tenant_for_module`）得出，模块开关由它一并校验；蜜罐与
fail-closed 限流在 `public_intake.py`。它不依赖公开站/CMS 是否安装。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx, snapshot_current_user
from app.core.public_site import resolve_public_tenant_for_module
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse, ResponseBase

from .constants import DEFAULT_CATEGORY
from .permissions import CREATE, MANAGE, READ
from .public_intake import enforce_public_submit_rate_limit, is_honeypot_hit
from .schemas import (
    AdminMessageCreate,
    AdminTicketListQuery,
    PublicTicketCreate,
    PublicTicketReceipt,
    SupportOptions,
    SupportSummary,
    TicketCreate,
    TicketDetail,
    TicketListItem,
    TicketListQuery,
    TicketMessageCreate,
    TicketUpdate,
)
from .service import SupportService

router = APIRouter()


@router.get("/options", response_model=ResponseBase[SupportOptions])
async def support_options(
    _: None = Depends(PermissionChecker([READ])),
) -> dict[str, Any]:
    """Enumerate ticket categories, statuses and priorities (values only)."""
    return SuccessResponse(data=SupportService.options())


@router.get("/tickets", response_model=ResponseBase[PageResponse[TicketListItem]])
async def list_my_tickets(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: Annotated[TicketListQuery, Depends()],
    _: None = Depends(PermissionChecker([READ])),
) -> dict[str, Any]:
    actor = snapshot_current_user(current_user)
    service = SupportService(db)
    rows, total = await service.list_tickets(
        tenant_id=tenant_ctx.tenant_id,
        owner_user_id=actor.user_id,
        page=query.page,
        page_size=query.page_size,
        status=query.status,
        category=query.category,
        priority=query.priority,
        keyword=query.keyword,
    )
    users = await service.user_briefs(rows)
    return SuccessResponse(
        data={
            "list": [service.ticket_payload(ticket, user_briefs=users) for ticket in rows],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.post(
    "/tickets",
    response_model=ResponseBase[TicketDetail],
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    data: TicketCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([CREATE])),
) -> dict[str, Any]:
    actor = snapshot_current_user(current_user)
    service = SupportService(db)
    ticket = await service.create_ticket(
        tenant_id=tenant_ctx.tenant_id,
        user_id=actor.user_id,
        data=data,
    )
    users = await service.user_briefs([ticket])
    return SuccessResponse(
        data=service.ticket_payload(ticket, user_briefs=users, include_messages=True)
    )


@router.get("/tickets/{ticket_id}", response_model=ResponseBase[TicketDetail])
async def get_my_ticket(
    ticket_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([READ])),
) -> dict[str, Any]:
    actor = snapshot_current_user(current_user)
    service = SupportService(db)
    ticket = await service.get_ticket(
        tenant_id=tenant_ctx.tenant_id,
        ticket_id=ticket_id,
        owner_user_id=actor.user_id,
    )
    users = await service.user_briefs([ticket])
    return SuccessResponse(
        data=service.ticket_payload(ticket, user_briefs=users, include_messages=True)
    )


@router.post("/tickets/{ticket_id}/messages", response_model=ResponseBase[TicketDetail])
async def reply_my_ticket(
    ticket_id: int,
    data: TicketMessageCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([CREATE])),
) -> dict[str, Any]:
    actor = snapshot_current_user(current_user)
    service = SupportService(db)
    ticket = await service.add_user_message(
        tenant_id=tenant_ctx.tenant_id,
        ticket_id=ticket_id,
        user_id=actor.user_id,
        body=data.body,
        attachments=data.attachments,
    )
    users = await service.user_briefs([ticket])
    return SuccessResponse(
        data=service.ticket_payload(ticket, user_briefs=users, include_messages=True)
    )


@router.get("/admin/summary", response_model=ResponseBase[SupportSummary])
async def admin_summary(
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([MANAGE])),
) -> dict[str, Any]:
    return SuccessResponse(data=await SupportService(db).summary(tenant_id=tenant_ctx.tenant_id))


@router.get("/admin/tickets", response_model=ResponseBase[PageResponse[TicketListItem]])
async def admin_list_tickets(
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: Annotated[AdminTicketListQuery, Depends()],
    _: None = Depends(PermissionChecker([MANAGE])),
) -> dict[str, Any]:
    service = SupportService(db)
    rows, total = await service.list_tickets(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        status=query.status,
        category=query.category,
        priority=query.priority,
        keyword=query.keyword,
        requester_user_id=query.requester_user_id,
        assignee_user_id=query.assignee_user_id,
        unassigned=query.unassigned,
        related_type=query.related_type,
        exclude_related_type=query.exclude_related_type,
    )
    users = await service.user_briefs(rows)
    return SuccessResponse(
        data={
            "list": [service.ticket_payload(ticket, user_briefs=users) for ticket in rows],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/admin/tickets/{ticket_id}", response_model=ResponseBase[TicketDetail])
async def admin_get_ticket(
    ticket_id: int,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([MANAGE])),
) -> dict[str, Any]:
    service = SupportService(db)
    ticket = await service.get_ticket(tenant_id=tenant_ctx.tenant_id, ticket_id=ticket_id)
    users = await service.user_briefs([ticket])
    return SuccessResponse(
        data=service.ticket_payload(
            ticket, user_briefs=users, include_messages=True, include_internal=True
        )
    )


@router.patch("/admin/tickets/{ticket_id}", response_model=ResponseBase[TicketDetail])
async def admin_update_ticket(
    ticket_id: int,
    data: TicketUpdate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([MANAGE])),
) -> dict[str, Any]:
    actor = snapshot_current_user(current_user)
    service = SupportService(db)
    ticket = await service.update_ticket(
        tenant_id=tenant_ctx.tenant_id,
        ticket_id=ticket_id,
        user_id=actor.user_id,
        data=data,
    )
    users = await service.user_briefs([ticket])
    return SuccessResponse(
        data=service.ticket_payload(
            ticket, user_briefs=users, include_messages=True, include_internal=True
        )
    )


@router.post("/admin/tickets/{ticket_id}/messages", response_model=ResponseBase[TicketDetail])
async def admin_reply_ticket(
    ticket_id: int,
    data: AdminMessageCreate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([MANAGE])),
) -> dict[str, Any]:
    actor = snapshot_current_user(current_user)
    service = SupportService(db)
    ticket = await service.add_admin_message(
        tenant_id=tenant_ctx.tenant_id,
        ticket_id=ticket_id,
        user_id=actor.user_id,
        body=data.body,
        is_internal=data.is_internal,
        status=data.status,
        attachments=data.attachments,
    )
    users = await service.user_briefs([ticket])
    return SuccessResponse(
        data=service.ticket_payload(
            ticket, user_briefs=users, include_messages=True, include_internal=True
        )
    )


@router.post("/public/tickets", response_model=ResponseBase[PublicTicketReceipt])
async def submit_public_ticket(
    data: PublicTicketCreate,
    request: Request,
    db: DBSession,
) -> dict[str, Any]:
    """Anonymous ticket submission for a visitor with no account.

    顺序是刻意的：先解析租户（未知主机 / 该租户没开 support => 404），
    再看蜜罐（命中就静默接受，不计入限流也不建单），最后才是限流与写库。
    """
    resolved = await resolve_public_tenant_for_module(
        request=request,
        db=db,
        module_code="support",
    )
    if is_honeypot_hit(data.website):
        return SuccessResponse(data=PublicTicketReceipt(accepted=True))

    await enforce_public_submit_rate_limit(tenant_id=resolved.tenant.id, request=request)

    description_lines = [data.message.strip(), "", f"Name: {data.name.strip()}", f"Email: {data.email.strip()}"]
    if data.source_page:
        description_lines.append(f"Source page: {data.source_page.strip()}")
    ticket = await SupportService(db).create_anonymous_ticket(
        tenant_id=resolved.tenant.id,
        subject=(data.subject or "").strip() or f"Public request: {data.name.strip()}",
        description="\n".join(description_lines).strip(),
        category=data.category or DEFAULT_CATEGORY,
        extra={
            "source": "public_form",
            "contact": {
                "name": data.name,
                "email": data.email,
                "sourcePage": data.source_page,
            },
        },
    )
    return SuccessResponse(
        data=PublicTicketReceipt(
            accepted=True,
            ticketId=int(ticket.id),
            ticketNo=ticket.ticket_no,
        )
    )
