"""Thin HTTP adapter for sample items."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession, PermissionChecker, TenantCtx
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse, ResponseBase

from .permissions import CREATE, DELETE, READ, UPDATE
from .schemas import Create, Detail, ListItem, Update
from .service import SampleItemService

router = APIRouter()


@router.get("", response_model=ResponseBase[PageResponse[ListItem]])
async def list_sample_items(
    tenant_ctx: TenantCtx,
    db: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    _: None = Depends(PermissionChecker([READ])),
) -> dict[str, Any]:
    items, total = await SampleItemService(db).list_items(
        tenant_id=tenant_ctx.tenant_id,
        page=page,
        page_size=page_size,
    )
    return SuccessResponse(
        data=PageResponse[ListItem](
            list=[ListItem.model_validate(item) for item in items],
            total=total,
            pageSize=page_size,
            currentPage=page,
        )
    )


@router.get("/{item_id}", response_model=ResponseBase[Detail])
async def get_sample_item(
    item_id: int,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([READ])),
) -> dict[str, Any]:
    item = await SampleItemService(db).require_item(
        tenant_id=tenant_ctx.tenant_id,
        item_id=item_id,
    )
    return SuccessResponse(data=Detail.model_validate(item))


@router.post("", response_model=ResponseBase[Detail], status_code=status.HTTP_201_CREATED)
async def create_sample_item(
    data: Create,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([CREATE])),
) -> dict[str, Any]:
    item = await SampleItemService(db).create_item(
        tenant_id=tenant_ctx.tenant_id,
        data=data,
    )
    return SuccessResponse(data=Detail.model_validate(item))


@router.patch("/{item_id}", response_model=ResponseBase[Detail])
async def update_sample_item(
    item_id: int,
    data: Update,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([UPDATE])),
) -> dict[str, Any]:
    item = await SampleItemService(db).update_item(
        tenant_id=tenant_ctx.tenant_id,
        item_id=item_id,
        data=data,
    )
    return SuccessResponse(data=Detail.model_validate(item))


@router.delete("/{item_id}", response_model=ResponseBase[None])
async def delete_sample_item(
    item_id: int,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([DELETE])),
) -> dict[str, Any]:
    await SampleItemService(db).delete_item(
        tenant_id=tenant_ctx.tenant_id,
        item_id=item_id,
    )
    return SuccessResponse(data=None)
