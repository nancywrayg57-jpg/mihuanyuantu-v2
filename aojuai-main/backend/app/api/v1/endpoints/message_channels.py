"""Personal message channel endpoints.

These channels are system-level user privacy capabilities. Tenant admins do not
manage them; users bind them through QR/inbound flows or manual webhook setup.
"""

from __future__ import annotations

import base64
import secrets
import subprocess
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import BusinessError, NotFoundError
from app.core.provider_secrets import encrypt_provider_secret
from app.core.response import SuccessResponse
from app.core.schemas import ResponseBase
from app.domain.auth.models import Tenant
from app.domain.notifications.feishu_client import begin_feishu_app_registration, build_feishu_bot_open_url
from app.domain.notifications.gateway_service import (
    MessageGatewayAccountService,
    authenticate_inbound_gateway_request,
)
from app.domain.notifications.ilink_client import WechatIlinkClient
from app.domain.notifications.message_channels import UserMessageChannelService
from app.domain.notifications.models import UserMessageChannel
from app.domain.notifications.schemas import (
    UserMessageChannelBindStartRequest,
    UserMessageChannelBindStartResponse,
    UserMessageChannelInboundBindRequest,
    UserMessageChannelItem,
    UserMessageChannelManualCreateRequest,
    UserMessageChannelTestRequest,
    UserMessageChannelTestResponse,
    UserMessageChannelUpsertRequest,
)
from app.domain.notifications.wecom_qrcode import (
    WECOM_BOT_WS_URL,
    WECOM_QR_EXPIRE_SECONDS,
    WECOM_QR_SOURCE,
    fetch_wecom_qrcode,
    query_wecom_qrcode_status,
)

router = APIRouter()

_CHANNEL_DEFAULT_NAMES = {
    "wechat": "微信 Channel",
    "feishu": "飞书 Channel",
    "wecom": "企业微信 Channel",
    "webhook": "Webhook Channel",
}
_BIND_CODE_EXPIRE_MINUTES = 10
_WECHAT_LOGIN_QR_EXPIRE_SECONDS = 120


async def _resolve_current_site_brand(db: DBSession, current_user: CurrentUser) -> str:
    tenant_id = int(getattr(current_user, "tenant_id", 0) or 0)
    if tenant_id <= 0:
        return "平台"
    try:
        result = await db.execute(
            select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.deleted_at.is_(None),
            )
        )
        tenant = result.scalar_one_or_none()
    except Exception:
        return "平台"
    config = dict(getattr(tenant, "config", {}) or {}) if tenant else {}
    seo = config.get("seo") if isinstance(config.get("seo"), dict) else {}
    return str((seo or {}).get("title") or getattr(tenant, "name", None) or "平台").strip() or "平台"


async def _generate_unique_bind_code(service: UserMessageChannelService) -> str:
    for _ in range(20):
        code = f"{secrets.randbelow(90_000_000) + 10_000_000:08d}"
        existing = await service.get_one(
            where=[
                UserMessageChannel.bind_token == code,
                UserMessageChannel.status == "pending",
            ]
        )
        if not existing:
            return code
    raise BusinessError(message="生成绑定码失败，请重试")


def _normalize_qr_image_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.startswith("data:image/"):
        return normalized
    if normalized.startswith(("http://", "https://", "data:")):
        return None
    return f"data:image/png;base64,{normalized}"


def _normalize_configured_qr_image_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://")):
        return normalized
    return _normalize_qr_image_url(normalized)


def _render_qr_image_data_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        result = subprocess.run(
            ["qrencode", "-o", "-", "-t", "PNG", "-s", "8", "-m", "2", normalized],
            check=True,
            capture_output=True,
            timeout=3,
        )
    except Exception:
        return None
    return f"data:image/png;base64,{base64.b64encode(result.stdout).decode()}"


async def _build_wechat_bind_qr(gateway_extra: dict[str, Any] | None) -> dict[str, Any]:
    configured_bot_qr = str((gateway_extra or {}).get("botQrUrl") or "").strip()
    if configured_bot_qr:
        return {
            "qrUrl": configured_bot_qr,
            "qrImageUrl": _normalize_configured_qr_image_url(configured_bot_qr)
            or _render_qr_image_data_url(configured_bot_qr),
            "qrPayload": configured_bot_qr,
            "gatewayReady": True,
            "providerRaw": {},
        }
    try:
        data = await WechatIlinkClient().get_bot_qrcode()
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(message=f"微信二维码获取失败: {exc}") from exc
    qrcode = str(data.get("qrcode") or data.get("qrCode") or "").strip()
    qrcode_img_content = str(data.get("qrcode_img_content") or data.get("qrcodeImgContent") or "").strip()
    if not qrcode and not qrcode_img_content:
        raise BusinessError(message="微信协议未返回二维码")
    return {
        "qrUrl": qrcode_img_content or qrcode,
        "qrImageUrl": _normalize_qr_image_url(qrcode_img_content)
        or _render_qr_image_data_url(qrcode_img_content or qrcode),
        "qrPayload": qrcode or qrcode_img_content,
        "gatewayReady": False,
        "providerRaw": data,
    }


async def _build_feishu_bind_qr(gateway: Any) -> dict[str, Any]:
    configured_domain = str((gateway.extra or {}).get("domain") or gateway.base_url or "feishu").strip() if gateway else ""
    try:
        registration = await begin_feishu_app_registration(domain=configured_domain or "feishu")
    except Exception as exc:  # noqa: BLE001
        if gateway and str(gateway.account_id or "").strip():
            domain = configured_domain or "feishu"
            configured_bot_qr = str((gateway.extra or {}).get("botQrUrl") or "").strip()
            bot_open_url = configured_bot_qr or build_feishu_bot_open_url(app_id=str(gateway.account_id), domain=domain)
            return {
                "qrUrl": bot_open_url,
                "qrImageUrl": _normalize_configured_qr_image_url(configured_bot_qr) or _render_qr_image_data_url(bot_open_url),
                "qrPayload": bot_open_url,
                "verificationUriComplete": None,
                "gatewayReady": True,
                "providerRaw": {"appId": gateway.account_id, "domain": domain, "botQrUrl": configured_bot_qr or None},
            }
        raise BusinessError(message=f"飞书扫码注册二维码获取失败: {exc}") from exc
    qr_url = str(registration.get("verification_uri_complete") or registration.get("verificationUriComplete") or "").strip()
    if not qr_url:
        raise BusinessError(message="飞书扫码注册接口未返回二维码链接")
    try:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parsed = urlsplit(qr_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.setdefault("from", "onboard")
        qr_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    except Exception:
        pass
    return {
        "qrUrl": qr_url,
        "qrImageUrl": _render_qr_image_data_url(qr_url),
        "qrPayload": qr_url,
        "verificationUriComplete": qr_url,
        "gatewayReady": False,
        "providerRaw": {
            "registrationMode": "feishu_app_registration",
            "deviceCode": registration.get("device_code"),
            "interval": registration.get("interval"),
            "expireIn": registration.get("expire_in") or registration.get("expires_in"),
            "domain": configured_domain or "feishu",
        },
    }


def _bind_instructions(channel_type: str, binding_code: str, *, gateway_ready: bool, site_brand: str = "平台") -> list[str]:
    provider = {"wechat": "微信", "feishu": "飞书", "wecom": "企业微信"}.get(channel_type, "消息")
    brand = str(site_brand or "").strip() or "平台"
    instructions = [
        f"使用{provider}扫描二维码进入 {brand} 系统 Channel。",
        "进入会话后的第一条消息只发送页面显示的八位关联码。",
        "系统收到关联码后会回复绑定成功，后续消息由 AI 助手接管。",
    ]
    if not gateway_ready:
        if channel_type == "feishu":
            instructions = [
                f"使用飞书扫描二维码完成 {brand} 机器人授权配置。",
                "授权成功后飞书会收到绑定提示，请发送页面显示的八位关联码完成绑定。",
                "系统收到关联码后会回复绑定成功，后续消息由 AI 助手接管。",
            ]
        elif channel_type == "wecom":
            instructions = [
                f"使用企业微信扫描二维码接入 {brand} 个人消息 Channel。",
                "扫码成功后页面会自动保存企业微信机器人凭据到你的个人 Channel。",
                "随后在企业微信机器人会话发送八位关联码完成绑定。",
            ]
        else:
            instructions.insert(1, "微信 iLink 二维码约 120 秒过期；如果扫码提示过期，请重新获取二维码。")
            instructions.insert(2, "如果二维码要求确认授权，请先在客户端完成确认。")
    return instructions


def _resolve_bind_expires_at(channel_type: str, qr_data: dict[str, Any]) -> datetime:
    if channel_type == "wechat" and not bool(qr_data.get("gatewayReady")):
        return datetime.now(UTC) + timedelta(seconds=_WECHAT_LOGIN_QR_EXPIRE_SECONDS)
    provider_raw = qr_data.get("providerRaw") if isinstance(qr_data.get("providerRaw"), dict) else {}
    if channel_type == "feishu" and provider_raw.get("registrationMode") == "feishu_app_registration":
        return datetime.now(UTC) + timedelta(seconds=int(provider_raw.get("expireIn") or 600))
    if channel_type == "wecom" and provider_raw.get("registrationMode") == "wecom_qrcode":
        return datetime.now(UTC) + timedelta(seconds=int(provider_raw.get("expireIn") or WECOM_QR_EXPIRE_SECONDS))
    return datetime.now(UTC) + timedelta(minutes=_BIND_CODE_EXPIRE_MINUTES)


def _build_channel_extra(
    *,
    bind_code: str,
    expires_at: datetime,
    qr_data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "bindMode": "qr_inbound",
        "bindingCode": bind_code,
        "expiresAt": expires_at.isoformat(),
        "qr": {
            "qrUrl": qr_data.get("qrUrl"),
            "qrImageUrl": qr_data.get("qrImageUrl"),
            "qrPayload": qr_data.get("qrPayload"),
            "verificationUriComplete": qr_data.get("verificationUriComplete"),
            "gatewayReady": qr_data.get("gatewayReady"),
            "providerRaw": qr_data.get("providerRaw") or {},
        },
    }


async def _disable_duplicate_pending_channels(
    service: UserMessageChannelService,
    channels: list[UserMessageChannel],
    keep_id: int | None,
) -> None:
    for channel in channels:
        if keep_id is not None and channel.id == keep_id:
            continue
        if channel.status == "pending":
            await service.delete(channel)


@router.get("", response_model=ResponseBase[list[UserMessageChannelItem]])
async def list_my_message_channels(current_user: CurrentUser, db: DBSession) -> dict[str, Any]:
    service = UserMessageChannelService(db)
    channels = await service.list_user_channels(user_id=current_user.id)
    return SuccessResponse(data=[service.to_item(item) for item in channels])


@router.post("/manual", response_model=ResponseBase[UserMessageChannelItem])
async def create_manual_message_channel(
    data: UserMessageChannelManualCreateRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    service = UserMessageChannelService(db)
    channel = await service.create_manual_channel(
        user_id=current_user.id,
        channel_type=data.channel_type,
        name=data.name,
        target=data.target,
        secret=data.secret,
        status=data.status,
        is_default=data.is_default,
        message_types=data.message_types,
        extra=data.extra,
    )
    return SuccessResponse(data=service.to_item(channel))


@router.post("/wecom/qrcode/start", response_model=ResponseBase[dict[str, Any]])
async def start_my_wecom_qrcode(current_user: CurrentUser, db: DBSession) -> dict[str, Any]:
    service = UserMessageChannelService(db)
    existing_channels = await service.list_user_channels_by_type(
        user_id=current_user.id,
        channel_type="wecom",
        statuses=["active", "pending"],
    )
    active_channel = next((item for item in existing_channels if item.status == "active"), None)
    if active_channel:
        raise BusinessError(message="企业微信 Channel 已绑定；如需重新绑定，请先解绑/删除现有 Channel")

    data = await fetch_wecom_qrcode()
    expires_at = datetime.fromisoformat(str(data["expiresAt"]).replace("Z", "+00:00"))
    site_brand = await _resolve_current_site_brand(db, current_user)
    bind_code = await _generate_unique_bind_code(service)
    extra = {
        "bindMode": "wecom_qrcode",
        "bindingCode": bind_code,
        "expiresAt": expires_at.isoformat(),
        "wecomBot": {
            "scode": data["scode"],
            "authUrl": data["authUrl"],
            "qrPageUrl": data["qrPageUrl"],
            "qrPayload": data["qrPayload"],
            "source": WECOM_QR_SOURCE,
            "websocketUrl": WECOM_BOT_WS_URL,
            "status": "pending",
        },
        "qr": {
            "qrUrl": data["authUrl"],
            "qrImageUrl": _render_qr_image_data_url(data["authUrl"]),
            "qrPayload": data["qrPayload"],
            "verificationUriComplete": data["qrPageUrl"],
            "gatewayReady": False,
            "providerRaw": {
                "registrationMode": "wecom_qrcode",
                "scode": data["scode"],
                "authUrl": data["authUrl"],
                "qrPageUrl": data["qrPageUrl"],
                "expireIn": WECOM_QR_EXPIRE_SECONDS,
            },
        },
    }
    reusable_channel = next((item for item in existing_channels if item.status == "pending"), None)
    if reusable_channel:
        channel = await service.update(
            reusable_channel,
            {
                "bind_token": bind_code,
                "name": reusable_channel.name or _CHANNEL_DEFAULT_NAMES["wecom"],
                "status": "pending",
                "message_types": reusable_channel.message_types or ["notification"],
                "extra": extra,
                "last_error": None,
            },
        )
    else:
        channel = await service.create_manual_channel(
            user_id=current_user.id,
            channel_type="wecom",
            name=_CHANNEL_DEFAULT_NAMES["wecom"],
            target=None,
            secret=None,
            status="pending",
            is_default=False,
            message_types=["notification"],
            extra=extra,
        )
        channel = await service.update(channel, {"bind_token": bind_code})
    await _disable_duplicate_pending_channels(service, existing_channels, keep_id=channel.id)
    return SuccessResponse(
        data={
            **data,
            "channelId": channel.id,
            "bindToken": bind_code,
            "bindingCode": bind_code,
            "qrText": bind_code,
            "qrUrl": data["authUrl"],
            "qrPayload": data["qrPayload"],
            "verificationUriComplete": data["qrPageUrl"],
            "status": channel.status,
            "qrImageUrl": extra["qr"]["qrImageUrl"],
            "gatewayReady": False,
            "instructions": _bind_instructions("wecom", bind_code, gateway_ready=False, site_brand=site_brand),
        }
    )


@router.get("/wecom/qrcode/status", response_model=ResponseBase[dict[str, Any]])
async def get_my_wecom_qrcode_status(
    scode: str,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    normalized_scode = str(scode or "").strip()
    service = UserMessageChannelService(db)
    channels = await service.list_user_channels_by_type(
        user_id=current_user.id,
        channel_type="wecom",
        statuses=["pending"],
    )
    channel = next(
        (
            item
            for item in channels
            if str((((item.extra or {}).get("wecomBot") or {}).get("scode")) or "").strip() == normalized_scode
        ),
        None,
    )
    if not channel:
        raise NotFoundError(message="企业微信扫码绑定会话不存在或已失效")

    data = await query_wecom_qrcode_status(normalized_scode)
    next_channel = None
    if data["connected"] and data["botId"] and data["secret"]:
        now = datetime.now(UTC)
        bind_expires_at = now + timedelta(minutes=_BIND_CODE_EXPIRE_MINUTES)
        extra = dict(channel.extra or {})
        wecom_bot = dict(extra.get("wecomBot") or {})
        bind_code_ready_at = str(wecom_bot.get("bindCodeReadyAt") or "").strip()
        wecom_bot.update(
            {
                "status": data["status"],
                "connected": True,
                "botId": data["botId"],
                "source": WECOM_QR_SOURCE,
                "websocketUrl": WECOM_BOT_WS_URL,
                "connectedAt": now.isoformat(),
            }
        )
        if not bind_code_ready_at:
            wecom_bot["bindCodeReadyAt"] = now.isoformat()
            wecom_bot["bindCodeExpiresAt"] = bind_expires_at.isoformat()
            extra["expiresAt"] = bind_expires_at.isoformat()
        extra["wecomBot"] = wecom_bot
        extra["lastInbound"] = data["raw"]
        qr = dict(extra.get("qr") or {})
        qr["gatewayReady"] = True
        extra["qr"] = qr
        next_channel = await service.update(
            channel,
            {
                "secret": encrypt_provider_secret(str(data["secret"])),
                "extra": extra,
                "last_error": None,
            },
        )
        with suppress(Exception):
            from app.domain.notifications.wecom_ws_client import start_wecom_channel_ws_account

            await start_wecom_channel_ws_account(
                channel_id=int(next_channel.id),
                bot_id=str(data["botId"]),
                bot_secret=str(data["secret"]),
                ws_url=WECOM_BOT_WS_URL,
            )
    else:
        extra = dict(channel.extra or {})
        wecom_bot = dict(extra.get("wecomBot") or {})
        wecom_bot.update({"status": data["status"], "connected": False})
        extra["wecomBot"] = wecom_bot
        next_channel = await service.update(channel, {"extra": extra})
    return SuccessResponse(
        data={
            "scode": data["scode"],
            "status": data["status"],
            "connected": data["connected"],
            "botId": data["botId"],
            "channel": service.to_item(next_channel or channel),
            "expiresAt": ((next_channel or channel).extra or {}).get("expiresAt"),
            "raw": data["raw"],
        }
    )


@router.post("/bind/start", response_model=ResponseBase[UserMessageChannelBindStartResponse])
async def start_message_channel_bind(
    data: UserMessageChannelBindStartRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    service = UserMessageChannelService(db)
    channel_type = data.channel_type
    if channel_type == "wecom":
        return await start_my_wecom_qrcode(current_user, db)

    existing_channels = await service.list_user_channels_by_type(
        user_id=current_user.id,
        channel_type=channel_type,
        statuses=["active", "pending"],
    )
    active_channel = next((item for item in existing_channels if item.status == "active"), None)
    if active_channel:
        raise BusinessError(message=f"{_CHANNEL_DEFAULT_NAMES[channel_type]} 已绑定；如需重新绑定，请先解绑/删除现有 Channel")
    reusable_channel = next((item for item in existing_channels if item.status == "pending"), None)

    gateway = await MessageGatewayAccountService(db).get_default_active(channel_type)
    site_brand = await _resolve_current_site_brand(db, current_user)
    bind_code = await _generate_unique_bind_code(service)
    if channel_type == "wechat":
        qr_data = await _build_wechat_bind_qr(gateway.extra if gateway else None)
    elif channel_type == "feishu":
        qr_data = await _build_feishu_bind_qr(gateway)
    else:
        raise BusinessError(message="不支持的扫码绑定类型")

    expires_at = _resolve_bind_expires_at(channel_type, qr_data)
    extra = _build_channel_extra(bind_code=bind_code, expires_at=expires_at, qr_data=qr_data)
    provider_raw = qr_data.get("providerRaw") or {}
    if channel_type == "wechat" and not bool(qr_data.get("gatewayReady")):
        qrcode = str(provider_raw.get("qrcode") or provider_raw.get("qrCode") or qr_data.get("qrPayload") or "").strip()
        extra["wechatLogin"] = {
            "qrcode": qrcode,
            "expiresAt": expires_at.isoformat(),
            "lastStatus": "created",
            "pollBaseUrl": "https://ilinkai.weixin.qq.com",
        }
    if channel_type == "feishu" and provider_raw.get("registrationMode") == "feishu_app_registration":
        extra["feishuRegistration"] = {
            "deviceCode": provider_raw.get("deviceCode"),
            "domain": provider_raw.get("domain") or "feishu",
            "interval": provider_raw.get("interval") or 5,
            "expiresAt": expires_at.isoformat(),
        }

    if reusable_channel:
        channel = await service.update(
            reusable_channel,
            {
                "bind_token": bind_code,
                "name": data.name or reusable_channel.name or _CHANNEL_DEFAULT_NAMES[channel_type],
                "status": "pending",
                "message_types": data.message_types or reusable_channel.message_types or ["notification"],
                "extra": extra,
                "last_error": None,
            },
        )
    else:
        channel = await service.create_manual_channel(
            user_id=current_user.id,
            channel_type=channel_type,
            name=data.name or _CHANNEL_DEFAULT_NAMES[channel_type],
            target=None,
            secret=None,
            status="pending",
            is_default=False,
            message_types=data.message_types,
            extra=extra,
        )
        channel = await service.update(channel, {"bind_token": bind_code})
    await _disable_duplicate_pending_channels(service, existing_channels, keep_id=channel.id)

    return SuccessResponse(
        data={
            "channelId": channel.id,
            "bindToken": bind_code,
            "bindingCode": bind_code,
            "qrText": bind_code,
            "qrUrl": qr_data.get("qrUrl"),
            "qrImageUrl": qr_data.get("qrImageUrl"),
            "qrPayload": qr_data.get("qrPayload"),
            "verificationUriComplete": qr_data.get("verificationUriComplete"),
            "expiresAt": expires_at,
            "instructions": _bind_instructions(
                channel_type,
                bind_code,
                gateway_ready=bool(qr_data.get("gatewayReady")),
                site_brand=site_brand,
            ),
            "gatewayReady": bool(qr_data.get("gatewayReady")),
            "status": channel.status,
        }
    )


@router.post("/bind/inbound", response_model=ResponseBase[UserMessageChannelItem])
async def confirm_message_channel_bind(
    data: UserMessageChannelInboundBindRequest,
    request: Request,
    db: DBSession,
) -> dict[str, Any]:
    auth = await authenticate_inbound_gateway_request(
        db,
        channel_type=data.channel_type,
        account_id=request.headers.get("x-aoju-gateway-account-id"),
        timestamp=request.headers.get("x-aoju-gateway-timestamp"),
        nonce=request.headers.get("x-aoju-gateway-nonce"),
        signature=request.headers.get("x-aoju-gateway-signature"),
        body=await request.body(),
    )
    service = UserMessageChannelService(db)
    channel = await service.bind_inbound_message(
        # 鉴权拿到的账号必须带下去：丢掉的话新绑定的渠道会写成 NULL，
        # 而 NULL 是"存量待认领"的语义——等于持续制造新的跨账号冒充窗口。
        gateway_account_id=auth.gateway_account_id,
        bind_token=data.bind_token,
        channel_type=data.channel_type,
        external_user_id=data.external_user_id,
        conversation_id=data.conversation_id,
        context_token=data.context_token,
        display_name=data.display_name,
        avatar=data.avatar,
        raw_payload=data.raw_payload,
        attempt_source=(
            # 已签名请求的限流来源要**按账号**固定。写 None 的话，
            # 攻击者轮换 external user 就能绕开按来源的失败计数。
            f"gateway-account:{auth.gateway_account_id}"
            if auth.signed and auth.gateway_account_id
            else (
                None
                if auth.signed
                else f"unsigned-http:{request.client.host if request.client else 'unknown'}"
            )
        ),
    )
    if not channel:
        # Persist both the accepted nonce and failed-attempt counter before the
        # public 404 is raised (the request dependency rolls exceptions back).
        await db.commit()
        raise NotFoundError(message="绑定请求不存在或已失效")
    return SuccessResponse(data=service.to_item(channel))


@router.put("/{channel_id}", response_model=ResponseBase[UserMessageChannelItem])
async def update_my_message_channel(
    channel_id: int,
    data: UserMessageChannelUpsertRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    service = UserMessageChannelService(db)
    channel = await service.get_user_channel(channel_id, user_id=current_user.id)
    if not channel:
        raise NotFoundError(message="消息 Channel 不存在")
    if data.renewal_reminder is not None:
        # 只动这一个键，不整块覆盖 extra
        await service.merge_extra(channel, {"renewalReminderEnabled": bool(data.renewal_reminder)})
    if data.hold_until_active is not None:
        await service.merge_extra(channel, {"holdUntilActiveEnabled": bool(data.hold_until_active)})
    channel = await service.update_user_channel(
        channel,
        name=data.name,
        target=data.target,
        secret=data.secret,
        status=data.status,
        is_default=data.is_default,
        message_types=data.message_types,
        extra=data.extra,
    )
    return SuccessResponse(data=service.to_item(channel))


@router.delete("/{channel_id}")
async def delete_my_message_channel(channel_id: int, current_user: CurrentUser, db: DBSession) -> dict[str, Any]:
    service = UserMessageChannelService(db)
    channel = await service.get_user_channel(channel_id, user_id=current_user.id)
    if not channel:
        raise NotFoundError(message="消息 Channel 不存在")
    await service.delete(channel)
    return SuccessResponse(message="Deleted")


@router.post("/{channel_id}/test", response_model=ResponseBase[UserMessageChannelTestResponse])
async def test_my_message_channel(
    channel_id: int,
    data: UserMessageChannelTestRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    service = UserMessageChannelService(db)
    channel = await service.get_user_channel(channel_id, user_id=current_user.id)
    if not channel:
        raise NotFoundError(message="消息 Channel 不存在")
    ok, message = await service.test_channel_delivery(
        channel,
        title=data.title,
        content=data.content,
    )
    await service.set_delivery_result(channel, ok=ok, error=None if ok else message)
    if not ok:
        raise BusinessError(message=message)
    return SuccessResponse(data={"ok": True, "message": message})
