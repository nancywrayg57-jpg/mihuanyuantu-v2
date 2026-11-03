"""
API Key 管理端点（自助，仅限本人密钥）

安全约束：
- 创建/吊销必须经 JWT 登录态，不接受 API Key 认证（防止密钥自我复制）
- 明文只在创建响应中返回一次
"""
from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ForbiddenError
from app.core.schemas import ResponseBase
from app.domain.auth.api_key_service import ApiKeyService

router = APIRouter()


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., max_length=200, description="用途名称，如 WIN-办公室-同步客户端")
    scopes: list[str] | None = Field(
        None, description="允许的 API 路径前缀；缺省为培训管理相关接口"
    )
    expires_in_days: int | None = Field(
        None, alias="expiresInDays", ge=1, le=3650, description="有效天数；缺省永不过期"
    )


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    key_prefix: str = Field(..., alias="keyPrefix")
    scopes: list[str]
    expires_at: datetime | None = Field(None, alias="expiresAt")
    last_used_at: datetime | None = Field(None, alias="lastUsedAt")
    created_at: datetime = Field(..., alias="createdAt")


class ApiKeyCreatedResponse(ApiKeyResponse):
    api_key: str = Field(..., alias="apiKey", description="明文，仅本次返回")


def _reject_api_key_auth(request: Request) -> None:
    if getattr(request.state, "auth_via_api_key", False):
        raise ForbiddenError(message="API Key 认证不能管理 API Key，请使用登录态")


@router.get("", response_model=ResponseBase[list[ApiKeyResponse]])
async def list_api_keys(db: DBSession, current_user: CurrentUser):
    """当前用户的 API Key 列表（不含明文）"""
    keys = await ApiKeyService.list_keys(db, current_user.tenant_id, current_user.id)
    return ResponseBase(success=True, data=keys)


@router.post("", response_model=ResponseBase[ApiKeyCreatedResponse])
async def create_api_key(
    data: ApiKeyCreate,
    db: DBSession,
    current_user: CurrentUser,
    request: Request,
):
    """创建 API Key（明文仅本次返回，请立即保存）"""
    _reject_api_key_auth(request)
    api_key, plaintext = await ApiKeyService.create_key(
        db,
        current_user.tenant_id,
        current_user.id,
        name=data.name,
        scopes=data.scopes,
        expires_in_days=data.expires_in_days,
    )
    resp = ApiKeyCreatedResponse.model_validate(
        {**ApiKeyResponse.model_validate(api_key).model_dump(by_alias=False), "api_key": plaintext}
    )
    return ResponseBase(success=True, data=resp, message="请立即保存明文密钥，之后无法再次查看")


@router.delete("/{key_id}", response_model=ResponseBase)
async def revoke_api_key(
    key_id: int,
    db: DBSession,
    current_user: CurrentUser,
    request: Request,
):
    """吊销 API Key"""
    _reject_api_key_auth(request)
    await ApiKeyService.revoke_key(db, current_user.tenant_id, current_user.id, key_id)
    return ResponseBase(success=True, message="已吊销")
