"""
AOJU Backend - Common Response Schemas
"""
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ResponseBase(BaseModel, Generic[T]):
    """
    Standard API response format.
    Compatible with vue-pure-admin frontend.
    """

    success: bool = True
    data: T | None = None
    message: str | None = None
    code: str = "SUCCESS"


class PageInfo(BaseModel):
    """Pagination info"""

    total: int = Field(description="Total count")
    page_size: int = Field(alias="pageSize", description="Items per page")
    current_page: int = Field(alias="currentPage", description="Current page number")

    model_config = ConfigDict(populate_by_name=True)


class PageResponse(BaseModel, Generic[T]):
    """Paginated response data"""

    items: list[T] = Field(alias="list", description="List data")
    total: int = Field(description="Total count")
    page_size: int = Field(alias="pageSize", description="Items per page")
    current_page: int = Field(alias="currentPage", description="Current page number")

    model_config = ConfigDict(populate_by_name=True)


class ErrorResponse(BaseModel):
    """Error response format"""

    success: bool = False
    code: str
    message: str
    details: Any = None


class TokenResponse(BaseModel):
    """Token response for login"""

    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    expires: datetime
    token_type: str = "bearer"

    model_config = ConfigDict(populate_by_name=True)


class IDResponse(BaseModel):
    """Response with just an ID"""

    id: int
