"""Admin-configurable Gemini detection pass line. Code default stays 75."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.models.platform_setting import RealphotosPlatformSetting
from app.capabilities.realphotos.permissions import ROLE_ADMIN
from app.capabilities.realphotos.services.gemini_detector import prompt_pass_line
from app.capabilities.realphotos.services.redo_policy import PASS_SCORE
from app.core.exceptions import BusinessError, ForbiddenError

PASS_SCORE_KEY = "gemini_detection_pass_score"


def _is_admin(actor_role_codes: set[str]) -> bool:
    return ROLE_ADMIN in actor_role_codes or "admin" in actor_role_codes


def normalize_pass_score(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BusinessError(message="检测及格线须为 0 到 100 的整数", code="PASS_SCORE_REJECTED")
    if value < 0 or value > 100:
        raise BusinessError(message="检测及格线须在 0 到 100", code="PASS_SCORE_REJECTED")
    return int(value)


class DetectionPassScoreService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def current(self) -> int:
        """Live line for new detection. Missing or unreadable row stays at PASS_SCORE (75)."""
        row = await self._row()
        if row is None:
            return int(PASS_SCORE)
        try:
            value = int(str(row.setting_value).strip())
        except ValueError:
            return int(PASS_SCORE)
        if value < 0 or value > 100:
            return int(PASS_SCORE)
        return value

    async def view(self, *, actor_role_codes: set[str]) -> dict:
        score = await self.current()
        return _payload(score, writable=_is_admin(actor_role_codes))

    async def update(
        self,
        *,
        actor_role_codes: set[str],
        pass_score: int,
        tenant_id: int,
        actor_user_id: int,
    ) -> dict:
        if not _is_admin(actor_role_codes):
            raise ForbiddenError(message="只有平台管理员可以修改 Gemini 检测及格线")
        score = normalize_pass_score(pass_score)
        row = await self._row()
        if row is None:
            row = RealphotosPlatformSetting(
                tenant_id=int(tenant_id),
                setting_key=PASS_SCORE_KEY,
                setting_value=str(score),
                updated_by_user_id=int(actor_user_id),
            )
            self.db.add(row)
        else:
            row.setting_value = str(score)
            row.updated_by_user_id = int(actor_user_id)
        await self.db.flush()
        return _payload(score, writable=True)

    async def _row(self) -> RealphotosPlatformSetting | None:
        return (
            await self.db.execute(
                select(RealphotosPlatformSetting).where(
                    RealphotosPlatformSetting.setting_key == PASS_SCORE_KEY,
                    RealphotosPlatformSetting.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()


def _payload(score: int, *, writable: bool) -> dict:
    return {
        "passScore": int(score),
        "defaultPassScore": int(PASS_SCORE),
        "writable": bool(writable),
        "promptLine": prompt_pass_line(score),
    }
