"""API schemas for sample items."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Create(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class Update(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class ListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    code: str
    name: str
    description: str | None
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime | None = Field(serialization_alias="updatedAt")


class Detail(ListItem):
    tenant_id: int = Field(serialization_alias="tenantId")
