"""
AOJU Backend - Operation Log Middleware

Automatically persists critical operation logs (multi-tenant isolated) into DB.
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from fastapi import Request
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.background import BackgroundTask, BackgroundTasks
from starlette.responses import Response

from app.core.auth_cookies import get_access_cookie
from app.core.config import settings
from app.core.exceptions import AOJUException
from app.domain.operation_logs.recorder import log_operation
from app.core.security import decode_token
from app.domain.users.models import User
from app.infrastructure.database import get_db_context

_MAX_BODY_BYTES = 50_000


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_access_token(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if auth:
        parts = auth.split(" ", 1)
        if len(parts) == 2:
            scheme, token = parts[0].strip(), parts[1].strip()
            if scheme.lower() == "bearer" and token:
                return token
    return get_access_cookie(request)


def _should_log_request(request: Request) -> bool:
    path = request.url.path
    if path == "/health":
        return False
    if not path.startswith(settings.API_V1_PREFIX):
        return False

    method = request.method.upper()
    if method in {"PUT", "PATCH", "DELETE"}:
        return True

    if method != "POST":
        return False

    allowed_exact = {
        f"{settings.API_V1_PREFIX}/notifications",
        f"{settings.API_V1_PREFIX}/teams",
    }
    if path in allowed_exact:
        return True

    allowed_suffixes = (
        "/create",
        "/login",
        "/logout",
        "/register",
        "/audit",
        "/reset-password",
        "/change-password",
        "/init",
        "/recharge",
        "/bulk",
        "/broadcast",
    )
    return any(path.endswith(suffix) for suffix in allowed_suffixes)


def _split_path(path: str) -> list[str]:
    prefix = settings.API_V1_PREFIX.rstrip("/")
    if path.startswith(prefix):
        path = path[len(prefix) :]
    return [p for p in path.strip("/").split("/") if p]


def _derive_module(parts: list[str]) -> str:
    if not parts:
        return "unknown"
    return parts[0]


def _derive_action(*, method: str, parts: list[str]) -> str:
    method_upper = method.upper()
    if not parts:
        return method_lower(method_upper)

    module = parts[0]
    if module == "auth" and len(parts) >= 2:
        leaf = parts[1]
        if leaf == "login":
            return "login"
        if leaf == "logout":
            return "logout"
        if leaf == "register":
            return "register"
        if leaf == "refresh-token":
            return "refresh_token"

    if module == "credits":
        if "recharge" in parts:
            return "recharge"
        if parts[:2] == ["credits", "accounts"] and parts[-1] == "init":
            return "account_init"
        if parts[:2] == ["credits", "accounts"] and parts[-1] == "status":
            return "account_status_update"

    if module == "notifications":
        if method_upper == "POST":
            if len(parts) == 1:
                return "send"
            if parts[-1] == "bulk":
                return "bulk_send"
            if parts[-1] == "broadcast":
                return "broadcast"

    if method_upper == "POST":
        if parts[-1] == "create":
            return "create"
        if module == "teams" and len(parts) == 1:
            return "create"
        if parts[-1] == "audit":
            return "audit"
        if parts[-1] == "reset-password":
            return "reset_password"
        if parts[-1] == "change-password":
            return "change_password"
        if parts[-1] == "init":
            return "init"
        if parts[-1] == "recharge":
            return "recharge"
        if parts[-1] == "bulk":
            return "bulk"
        return "read"

    if method_upper in {"PUT", "PATCH"}:
        return "update"
    if method_upper == "DELETE":
        return "delete"
    return "read"


def method_lower(method_upper: str) -> str:
    return method_upper.lower()


def _derive_target(*, module: str, parts: list[str]) -> tuple[str | None, int | None]:
    target_type_map = {
        "users": "User",
        "roles": "Role",
        "menus": "Menu",
        "teams": "Team",
        "credits": "Credits",
        "notifications": "Notification",
        "operation-logs": "OperationLog",
        "tenants": "Tenant",
        "tenant": "Tenant",
    }
    target_type = target_type_map.get(module)

    target_id: int | None = None
    for part in parts[1:]:
        if part.isdigit():
            target_id = int(part)
            break
    return target_type, target_id


async def _maybe_read_json_body(request: Request) -> dict[str, Any] | None:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        return None

    body = await request.body()
    if not body:
        return None
    if len(body) > _MAX_BODY_BYTES:
        return {"_truncated": True}

    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:
        return None
    if isinstance(parsed, dict):
        return parsed
    return {"_payload": parsed}


async def _resolve_actor(
    request: Request,
    *,
    db,
    parts: list[str],
    request_data: dict[str, Any] | None,
) -> tuple[int | None, str | None, int | None, bool]:
    """
    Resolve (user_id, username, tenant_id, is_superuser).

    Returns tenant_id as the *target tenant* for logging.
    """
    token = _resolve_access_token(request)
    user: User | None = None

    if token:
        try:
            payload = decode_token(token)
        except Exception:
            payload = None
        if payload and payload.get("type") == "access":
            user_id = _parse_int(payload.get("sub"))
            if user_id:
                result = await db.execute(
                    select(User).where(User.id == user_id, User.deleted_at.is_(None))
                )
                user = result.scalar_one_or_none()

    # Special-case: login is unauthenticated; try resolve by username.
    if not user and parts[:2] == ["auth", "login"] and request_data:
        username = request_data.get("username")
        if isinstance(username, str) and username.strip():
            result = await db.execute(
                select(User).where(User.username == username.strip(), User.deleted_at.is_(None))
            )
            user = result.scalar_one_or_none()

    if not user:
        return None, None, None, False

    tenant_id = int(user.tenant_id)
    if user.is_superuser:
        header_tenant_id = _parse_int(request.headers.get("x-tenant-id"))
        if header_tenant_id is not None:
            tenant_id = header_tenant_id
        else:
            param_tenant_id = _parse_int(request.query_params.get("tenant_id"))
            if param_tenant_id is not None:
                tenant_id = param_tenant_id
            else:
                param_tenant_id_camel = _parse_int(request.query_params.get("tenantId"))
                if param_tenant_id_camel is not None:
                    tenant_id = param_tenant_id_camel

    return int(user.id), user.username, tenant_id, bool(user.is_superuser)


class OperationLogMiddleware(BaseHTTPMiddleware):
    """Persist critical operation logs to DB (best-effort)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not _should_log_request(request):
            return await call_next(request)

        start = perf_counter()
        parts = _split_path(request.url.path)
        module = _derive_module(parts)
        action = _derive_action(method=request.method, parts=parts)
        target_type, target_id = _derive_target(module=module, parts=parts)

        request_data: dict[str, Any] | None = None
        try:
            if request.method.upper() in {"POST", "PUT", "PATCH"}:
                request_data = await _maybe_read_json_body(request)
        except Exception:
            request_data = None

        status_code: int | None = None
        error_message: str | None = None
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = int(getattr(response, "status_code", 200))
            return response
        except Exception as exc:
            if isinstance(exc, AOJUException):
                status_code = exc.status_code
                error_message = exc.message
            else:
                status_code = 500
                error_message = type(exc).__name__
            raise
        finally:
            duration_ms = int((perf_counter() - start) * 1000)
            status = "success" if (status_code or 500) < 400 else "failure"

            async def _persist() -> None:
                try:
                    async with get_db_context() as db:
                        user_id, username, tenant_id, _ = await _resolve_actor(
                            request,
                            db=db,
                            parts=parts,
                            request_data=request_data,
                        )
                        if tenant_id is not None:
                            await log_operation(
                                db,
                                tenant_id=tenant_id,
                                user_id=user_id,
                                username=username,
                                module=module,
                                action=action,
                                target_type=target_type,
                                target_id=target_id,
                                method=request.method,
                                path=request.url.path,
                                ip=(request.client.host if request.client else None),
                                user_agent=request.headers.get("user-agent"),
                                status=status,
                                status_code=status_code,
                                error_message=error_message,
                                request_data=request_data,
                                response_data=None,
                                duration_ms=duration_ms,
                                extra={"query": dict(request.query_params)},
                            )
                except Exception:
                    # Never block request due to logging failures.
                    pass

            if response is not None:
                # 日志写入挂到响应的 background：等响应发出、请求自己的会话（yield 依赖）提交之后再开
                # 第二个会话。否则这里会在请求事务仍未提交时并行写库——PG 上只是顺序不理想，
                # SQLite 单写者下是自锁：BEGIN IMMEDIATE 等 busy_timeout 30 秒后失败，每个写请求都慢 30 秒。
                existing = response.background
                task = BackgroundTask(_persist)
                if existing is None:
                    response.background = task
                else:
                    combined = BackgroundTasks()
                    combined.add_task(existing)
                    combined.add_task(task)
                    response.background = combined
            else:
                await _persist()
