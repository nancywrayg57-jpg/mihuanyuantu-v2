"""Execution job enqueue/read (S0)."""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.permissions import JOBS_ENQUEUE, JOBS_READ
from app.capabilities.realphotos.schemas.jobs import EnqueueJobRequest
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.core.response import SuccessResponse

router = APIRouter(prefix="/jobs")


@router.post("")
async def enqueue_job(
    body: EnqueueJobRequest,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    job = await RealphotosJobService(db).enqueue(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        job_kind=body.job_kind,
        payload=body.payload,
    )
    await db.commit()
    return SuccessResponse(data=RealphotosJobService(db).to_payload(job))


@router.get("/{job_id}")
async def get_job(
    job_id: int,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_READ])),
) -> dict[str, Any]:
    job = await RealphotosJobService(db).get_job(
        tenant_id=int(tenant_ctx.tenant_id),
        job_id=int(job_id),
    )
    return SuccessResponse(data=RealphotosJobService(db).to_payload(job))
