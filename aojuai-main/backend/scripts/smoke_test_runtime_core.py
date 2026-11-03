"""
Runtime smoke test for nextjs-base backend flows.

Purpose:
  Validate the deployed base runtime still works end-to-end for the
  reusable foundation layer: auth, menus, assistant, credits and
  invitations.

Example:
  uv run python backend/scripts/smoke_test_runtime_core.py \
    --base-url http://127.0.0.1:8000 \
    --username admin \
    --password Admin@123456 \
    --pretty
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any

import httpx


class SmokeTestError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    username: str
    roles: list[str]
    permissions: list[str]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runtime smoke test for nextjs-base backend flows")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--username", default="admin", help="Login username")
    parser.add_argument("--password", default="Admin@123456", help="Login password")
    parser.add_argument("--ordinary-username", default="test", help="Ordinary user login username")
    parser.add_argument("--ordinary-password", default="Test@123456", help="Ordinary user login password")
    parser.add_argument(
        "--skip-ordinary-user",
        action="store_true",
        help="Skip ordinary user menu route coverage",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--skip-assistant-chat",
        action="store_true",
        help="Skip the assistant /chat streaming check when live model latency is not desired",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    return parser.parse_args()


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestError(message)


def _request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    token: str | None = None,
    expect_success: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    headers = dict(kwargs.pop("headers", {}) or {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = client.request(method, url, headers=headers, **kwargs)
    response.raise_for_status()
    payload = response.json()
    if expect_success:
        _ensure(bool(payload.get("success")), f"{method} {url} failed: {payload}")
    return payload


def _parse_sse_payloads(raw_text: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for line in raw_text.splitlines():
        if not line.startswith("data: "):
            continue
        payloads.append(json.loads(line[6:]))
    return payloads


def _count_routes(routes: list[dict[str, Any]]) -> int:
    total = 0
    for route in routes:
        total += 1
        children = route.get("children") or []
        if isinstance(children, list):
            total += _count_routes(children)
    return total


def _login(client: httpx.Client, base_url: str, username: str, password: str) -> AuthSession:
    payload = _request_json(
        client,
        "POST",
        f"{base_url}/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    data = payload.get("data") or {}
    access_token = str(data.get("accessToken") or "")
    refresh_token = str(data.get("refreshToken") or "")
    _ensure(bool(access_token), "login response missing access token")
    _ensure(bool(refresh_token), "login response missing refresh token")
    return AuthSession(
        access_token=access_token,
        refresh_token=refresh_token,
        username=str(data.get("username") or ""),
        roles=[str(item) for item in (data.get("roles") or [])],
        permissions=[str(item) for item in (data.get("permissions") or [])],
    )


def _check_assistant_chat(client: httpx.Client, base_url: str, token: str) -> dict[str, Any]:
    response = client.post(
        f"{base_url}/api/v1/assistant/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "请基于当前页面告诉我你能做什么，只返回简短总结。",
            "routePath": "/dashboard",
            "contextParams": {"tab": "overview"},
        },
    )
    response.raise_for_status()
    payloads = _parse_sse_payloads(response.text)
    _ensure(bool(payloads), "assistant chat returned no SSE payloads")
    done_payload = next((item for item in reversed(payloads) if item.get("type") == "done"), None)
    _ensure(done_payload is not None, "assistant chat stream missing done payload")
    _ensure(bool(str(done_payload.get("reply") or "").strip()), "assistant chat done payload missing reply")
    return {
        "usedAi": bool(done_payload.get("usedAi")),
        "moduleCode": done_payload.get("moduleCode"),
        "routePath": done_payload.get("routePath"),
    }


def main() -> int:
    args = _parse_args()
    base_url = args.base_url.rstrip("/")

    with httpx.Client(timeout=args.timeout, follow_redirects=True) as client:
        health = client.get(f"{base_url}/health")
        _ensure(health.status_code == 200, f"health check failed: {health.status_code}")

        auth = _login(client, base_url, args.username, args.password)

        session_cookie = _request_json(client, "GET", f"{base_url}/api/v1/auth/session")
        session_bearer = _request_json(
            client,
            "GET",
            f"{base_url}/api/v1/auth/session",
            token=auth.access_token,
        )
        _ensure((session_cookie.get("data") or {}).get("username") == auth.username, "cookie session username mismatch")
        _ensure((session_bearer.get("data") or {}).get("username") == auth.username, "bearer session username mismatch")

        mine_payload = _request_json(client, "GET", f"{base_url}/api/v1/auth/mine", token=auth.access_token)
        mine_data = mine_payload.get("data") or {}
        _ensure(mine_data.get("username") == auth.username, "auth/mine username mismatch")

        routes_payload = _request_json(client, "GET", f"{base_url}/api/v1/menus/routes", token=auth.access_token)
        routes = routes_payload.get("data") or []
        _ensure(isinstance(routes, list), "menus/routes response invalid")
        route_count = _count_routes(routes)
        _ensure(route_count > 0, "menus/routes returned no routes")
        ordinary_summary: dict[str, Any] | None = None
        if not args.skip_ordinary_user:
            ordinary_auth = _login(client, base_url, args.ordinary_username, args.ordinary_password)
            ordinary_session = _request_json(
                client,
                "GET",
                f"{base_url}/api/v1/auth/session",
                token=ordinary_auth.access_token,
            )
            _ensure(
                (ordinary_session.get("data") or {}).get("username") == ordinary_auth.username,
                "ordinary session username mismatch",
            )
            ordinary_routes_payload = _request_json(
                client,
                "GET",
                f"{base_url}/api/v1/menus/routes",
                token=ordinary_auth.access_token,
            )
            ordinary_routes = ordinary_routes_payload.get("data") or []
            _ensure(isinstance(ordinary_routes, list), "ordinary menus/routes response invalid")
            ordinary_route_count = _count_routes(ordinary_routes)
            _ensure(ordinary_route_count > 0, "ordinary menus/routes returned no routes")
            ordinary_summary = {
                "username": ordinary_auth.username,
                "roles": ordinary_auth.roles,
                "permissionsCount": len(ordinary_auth.permissions),
                "routesCount": ordinary_route_count,
            }

        assistant_context = _request_json(
            client,
            "GET",
            f"{base_url}/api/v1/assistant/context",
            token=auth.access_token,
            params={"route": "/dashboard", "context": "{}"},
        )
        assistant_presets = _request_json(
            client,
            "GET",
            f"{base_url}/api/v1/assistant/presets",
            token=auth.access_token,
            params={"route": "/dashboard", "context": "{}"},
        )
        context_data = assistant_context.get("data") or {}
        presets_data = assistant_presets.get("data") or {}
        _ensure(bool(context_data.get("moduleCode")), "assistant/context missing moduleCode")
        _ensure(bool(context_data.get("moduleName")), "assistant/context missing moduleName")
        _ensure(isinstance(presets_data.get("presets"), list), "assistant/presets missing presets list")

        assistant_chat_summary: dict[str, Any] | None = None
        if not args.skip_assistant_chat:
            assistant_chat_summary = _check_assistant_chat(client, base_url, auth.access_token)

        credits_payload = _request_json(client, "GET", f"{base_url}/api/v1/credits/my/account", token=auth.access_token)
        credits_data = credits_payload.get("data") or {}
        _ensure(bool(credits_data.get("id")), "credits/my/account missing account id")

        invitation_payload = _request_json(
            client,
            "GET",
            f"{base_url}/api/v1/invitations/my/summary",
            token=auth.access_token,
        )
        invitation_data = invitation_payload.get("data") or {}
        _ensure(isinstance(invitation_data, dict) and bool(invitation_data), "invitations/my/summary response invalid")

        summary = {
            "baseUrl": base_url,
            "username": auth.username,
            "roles": auth.roles,
            "permissionsCount": len(auth.permissions),
            "routesCount": route_count,
            "assistant": {
                "moduleCode": context_data.get("moduleCode"),
                "moduleName": context_data.get("moduleName"),
                "presetCount": len(presets_data.get("presets") or []),
                "chat": assistant_chat_summary,
            },
            "credits": {
                "accountId": credits_data.get("id"),
                "balance": credits_data.get("balance"),
            },
            "invitations": {
                "remainingQuota": invitation_data.get("remainingQuota"),
                "issuedCodes": invitation_data.get("issuedCodeCount"),
            },
            "checks": {
                "health": "ok",
                "login": "ok",
                "sessionCookie": "ok",
                "sessionBearer": "ok",
                "mine": "ok",
                "menus": "ok",
                "ordinaryMenus": "skipped" if args.skip_ordinary_user else "ok",
                "assistantContext": "ok",
                "assistantPresets": "ok",
                "assistantChat": "skipped" if args.skip_assistant_chat else "ok",
                "creditsMyAccount": "ok",
                "invitationsMySummary": "ok",
            },
            "ordinaryUser": ordinary_summary,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeTestError as exc:
        print(f"[runtime-smoke] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
