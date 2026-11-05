from pydantic import BaseModel, ConfigDict, Field


class WalletAdjustRequest(BaseModel):
    tenant_id: int = Field(..., alias="tenantId", gt=0)
    delta_available: int = Field(..., alias="deltaAvailable")
    reason: str = Field(..., min_length=1, max_length=500)
    event_key: str = Field(..., alias="eventKey", min_length=1, max_length=128)
    target_user_id: int | None = Field(default=None, alias="targetUserId")

    model_config = ConfigDict(populate_by_name=True)
