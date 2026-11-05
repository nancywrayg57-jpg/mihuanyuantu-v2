"""Admin integer wallet adjustments (S0)."""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DBSession, PermissionChecker
from app.capabilities.realphotos.permissions import WALLET_ADJUST
from app.capabilities.realphotos.schemas.wallet import WalletAdjustRequest
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.core.response import SuccessResponse

router = APIRouter(prefix="/admin")


@router.post("/wallet-adjustments")
async def adjust_wallet(
    body: WalletAdjustRequest,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker([WALLET_ADJUST])),
) -> dict[str, Any]:
    data = await RealphotosCreditService(db).admin_adjust(
        tenant_id=int(body.tenant_id),
        delta_available=int(body.delta_available),
        operator_user_id=int(current_user.id),
        reason=body.reason,
        event_key=body.event_key,
        target_user_id=body.target_user_id,
    )
    await db.commit()
    return SuccessResponse(data=data)
