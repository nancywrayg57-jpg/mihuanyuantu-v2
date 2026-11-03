"""System message gateway management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import CurrentSuperuser, DBSession
from app.core.exceptions import NotFoundError
from app.core.logger import get_logger
from app.core.response import SuccessResponse
from app.core.schemas import ResponseBase
from app.domain.notifications.gateway_service import (
    InboundGatewayAuthContext,
    MessageGatewayAccountService,
    authenticate_inbound_gateway_request,
    extract_wecom_event_payload,
    handle_feishu_event_payload,
    handle_wecom_event_payload,
)
from app.domain.notifications.ilink_client import WechatIlinkClient
from app.infrastructure.database.session import get_db_context

router = APIRouter()
logger = get_logger(__name__)


async def _handle_feishu_event_payload_background(
    payload: dict[str, Any],
    gateway_account_id: int | None = None,
    bind_attempt_source: str | None = None,
) -> None:
    try:
        async with get_db_context() as db:
            await handle_feishu_event_payload(
                db,
                payload,
                gateway_account_id=gateway_account_id,
                bind_attempt_source=bind_attempt_source,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("feishu_http_event_failed", error=str(exc))


async def _handle_wecom_event_payload_background(
    payload: dict[str, Any],
    gateway_account_id: int | None = None,
    bind_attempt_source: str | None = None,
) -> None:
    try:
        async with get_db_context() as db:
            await _handle_wecom_event_payload(
                db,
                payload,
                gateway_account_id=gateway_account_id,
                bind_attempt_source=bind_attempt_source,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("wecom_http_event_failed", error=str(exc))


def _extract_wecom_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return extract_wecom_event_payload(payload)


async def _handle_wecom_event_payload(
    db: DBSession,
    payload: dict[str, Any],
    *,
    gateway_account_id: int | None = None,
    bind_attempt_source: str | None = None,
) -> None:
    await handle_wecom_event_payload(
        db,
        payload,
        gateway_account_id=gateway_account_id,
        bind_attempt_source=bind_attempt_source,
    )


async def authenticate_gateway_http_request(
    request: Request,
    db: DBSession,
    *,
    channel_type: str,
) -> InboundGatewayAuthContext:
    """Extract transport data; authentication policy stays in the domain service."""
    return await authenticate_inbound_gateway_request(
        db,
        channel_type=channel_type,
        account_id=request.headers.get("x-aoju-gateway-account-id"),
        timestamp=request.headers.get("x-aoju-gateway-timestamp"),
        nonce=request.headers.get("x-aoju-gateway-nonce"),
        signature=request.headers.get("x-aoju-gateway-signature"),
        body=await request.body(),
    )


def _unsigned_bind_attempt_source(request: Request, *, signed: bool) -> str | None:
    if signed:
        return None
    client_host = request.client.host if request.client else "unknown"
    return f"unsigned-http:{client_host}"


class MessageGatewayAccountItem(BaseModel):
    id: int
    channel_type: str = Field(..., alias="channelType")
    name: str
    account_id: str | None = Field(None, alias="accountId")
    base_url: str | None = Field(None, alias="baseUrl")
    gateway_url: str | None = Field(None, alias="gatewayUrl")
    bot_qr_url: str | None = Field(None, alias="botQrUrl")
    bot_open_url: str | None = Field(None, alias="botOpenUrl")
    domain: str | None = None
    status: str
    is_default: bool = Field(False, alias="isDefault")
    token_configured: bool = Field(False, alias="tokenConfigured")
    token_masked: str | None = Field(None, alias="tokenMasked")
    last_poll_at: Any = Field(None, alias="lastPollAt")
    last_error: str | None = Field(None, alias="lastError")

    model_config = ConfigDict(populate_by_name=True)


class WechatGatewayLoginStartResponse(BaseModel):
    qrcode: str
    qrcode_img_content: str | None = Field(None, alias="qrcodeImgContent")
    raw: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class WechatGatewayLoginConfirmRequest(BaseModel):
    qrcode: str
    name: str = "微信 Channel 网关"
    is_default: bool = Field(True, alias="isDefault")

    model_config = ConfigDict(populate_by_name=True)


class FeishuGatewayUpsertRequest(BaseModel):
    name: str = "飞书 Channel 网关"
    app_id: str = Field(..., alias="appId")
    app_secret: str = Field(..., alias="appSecret")
    domain: str = "feishu"
    verification_token: str | None = Field(None, alias="verificationToken")
    encrypt_key: str | None = Field(None, alias="encryptKey")
    bot_qr_url: str | None = Field(None, alias="botQrUrl")
    is_default: bool = Field(True, alias="isDefault")

    model_config = ConfigDict(populate_by_name=True)


class WecomGatewayUpsertRequest(BaseModel):
    name: str = "企业微信 Channel 网关"
    bot_id: str = Field(..., alias="botId")
    bot_secret: str | None = Field(None, alias="botSecret")
    gateway_url: str | None = Field(None, alias="gatewayUrl")
    bot_qr_url: str | None = Field(None, alias="botQrUrl")
    bot_open_url: str | None = Field(None, alias="botOpenUrl")
    is_default: bool = Field(True, alias="isDefault")

    model_config = ConfigDict(populate_by_name=True)


class FeishuEventRequest(BaseModel):
    type: str | None = None
    challenge: str | None = None
    token: str | None = None
    event: dict[str, Any] = Field(default_factory=dict)
    header: dict[str, Any] = Field(default_factory=dict)
    schema_: str | None = Field(None, alias="schema")

    model_config = ConfigDict(populate_by_name=True)


class WecomEventRequest(BaseModel):
    event: dict[str, Any] = Field(default_factory=dict)
    message: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    text: Any = None
    content: str | None = None
    external_user_id: str | None = Field(None, alias="externalUserId")
    conversation_id: str | None = Field(None, alias="conversationId")
    model_config = ConfigDict(populate_by_name=True, extra="allow")


@router.get("", response_model=ResponseBase[list[MessageGatewayAccountItem]])
async def list_message_gateways(_: CurrentSuperuser, db: DBSession) -> dict[str, Any]:
    service = MessageGatewayAccountService(db)
    accounts = await service.list_accounts()
    return SuccessResponse(data=[service.to_item(account) for account in accounts])


@router.post("/wechat/login/start", response_model=ResponseBase[WechatGatewayLoginStartResponse])
async def start_wechat_gateway_login(_: CurrentSuperuser) -> dict[str, Any]:
    data = await WechatIlinkClient().get_bot_qrcode()
    return SuccessResponse(
        data={
            "qrcode": data.get("qrcode") or data.get("qrCode") or "",
            "qrcodeImgContent": data.get("qrcode_img_content") or data.get("qrcodeImgContent"),
            "raw": data,
        }
    )


@router.post("/wechat/login/confirm", response_model=ResponseBase[MessageGatewayAccountItem])
async def confirm_wechat_gateway_login(
    data: WechatGatewayLoginConfirmRequest,
    _: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    status = await WechatIlinkClient().get_qrcode_status(qrcode=data.qrcode)
    token = status.get("bot_token") or status.get("botToken")
    base_url = status.get("baseurl") or status.get("baseUrl")
    account_id = status.get("account_id") or status.get("accountId") or status.get("bot_id") or status.get("botId")
    if not token or not base_url:
        raise NotFoundError(message="微信网关扫码尚未确认或未返回 token/baseUrl")
    service = MessageGatewayAccountService(db)
    account = await service.upsert_wechat_account(
        name=data.name,
        account_id=account_id,
        base_url=base_url,
        token=token,
        is_default=data.is_default,
    )
    return SuccessResponse(data=service.to_item(account))


@router.put("/feishu", response_model=ResponseBase[MessageGatewayAccountItem])
async def upsert_feishu_gateway(
    data: FeishuGatewayUpsertRequest,
    _: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    service = MessageGatewayAccountService(db)
    account = await service.upsert_feishu_account(
        name=data.name,
        app_id=data.app_id,
        app_secret=data.app_secret,
        domain=data.domain,
        bot_qr_url=data.bot_qr_url,
        is_default=data.is_default,
    )
    return SuccessResponse(data=service.to_item(account))


@router.put("/wecom", response_model=ResponseBase[MessageGatewayAccountItem])
async def upsert_wecom_gateway(
    data: WecomGatewayUpsertRequest,
    _: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    service = MessageGatewayAccountService(db)
    account = await service.upsert_wecom_account(
        name=data.name,
        bot_id=data.bot_id,
        bot_secret=data.bot_secret,
        gateway_url=data.gateway_url,
        bot_qr_url=data.bot_qr_url,
        bot_open_url=data.bot_open_url,
        is_default=data.is_default,
    )
    return SuccessResponse(data=service.to_item(account))


@router.post("/feishu/events")
async def receive_feishu_event(
    data: FeishuEventRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> dict[str, Any]:
    auth = await authenticate_gateway_http_request(request, db, channel_type="feishu")
    if data.challenge:
        return {"challenge": data.challenge}

    background_tasks.add_task(
        _handle_feishu_event_payload_background,
        {
            "schema": data.schema_,
            "header": data.header,
            "event": data.event,
            "type": data.type,
        },
        auth.gateway_account_id,
        _unsigned_bind_attempt_source(request, signed=auth.signed),
    )
    return {"code": 0, "msg": "ok"}


@router.post("/wecom/events")
async def receive_wecom_event(
    data: WecomEventRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> dict[str, Any]:
    auth = await authenticate_gateway_http_request(request, db, channel_type="wecom")
    background_tasks.add_task(
        _handle_wecom_event_payload_background,
        data.model_dump(by_alias=True),
        auth.gateway_account_id,
        _unsigned_bind_attempt_source(request, signed=auth.signed),
    )
    return {"code": 0, "msg": "ok"}
