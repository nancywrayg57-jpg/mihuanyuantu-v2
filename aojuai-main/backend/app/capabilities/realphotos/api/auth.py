"""Captcha challenge + login (S0)."""

from typing import Any

from fastapi import APIRouter

from app.api.deps import DBSession
from app.capabilities.realphotos.schemas.auth import ChallengeCreate, LoginRequest
from app.capabilities.realphotos.services.auth_service import RealphotosAuthService
from app.core.response import SuccessResponse

router = APIRouter(prefix="/auth")


@router.post("/challenges")
async def create_challenge(
    db: DBSession,
    body: ChallengeCreate | None = None,
) -> dict[str, Any]:
    payload = body or ChallengeCreate()
    data = await RealphotosAuthService(db).create_challenge(client_key=payload.client_key)
    await db.commit()
    return SuccessResponse(data=data)


@router.post("/login")
async def login(body: LoginRequest, db: DBSession) -> dict[str, Any]:
    data = await RealphotosAuthService(db).login(
        username=body.username,
        password=body.password,
        challenge_id=body.challenge_id,
        challenge_code=body.challenge_code,
    )
    await db.commit()
    return SuccessResponse(data=data)
