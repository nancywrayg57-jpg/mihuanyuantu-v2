from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnqueueJobRequest(BaseModel):
    job_kind: str = Field(default="heartbeat", alias="jobKind")
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
