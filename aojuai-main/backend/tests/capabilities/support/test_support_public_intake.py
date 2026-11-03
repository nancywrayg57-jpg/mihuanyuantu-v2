"""匿名提单入口的三条防护。

这条路径是**未认证的写入**，所以每条防护都要有测试盯着：
蜜罐命中静默接受、限流按窗口拒绝、以及 Redis 不可用时**拒绝**而不是放行。
最后一条是重点：best-effort 计数器（失败返回 0）会让 Redis 一挂限流就等于没有。
"""

from __future__ import annotations

import pytest

from app.capabilities.support import api as support_api
from app.capabilities.support import public_intake
from app.capabilities.support.constants import PUBLIC_SUBMIT_MAX_PER_WINDOW
from app.capabilities.support.models import ANONYMOUS_REQUESTER_ID
from app.capabilities.support.schemas import PublicTicketCreate
from app.capabilities.support.service import SupportService
from app.core.exceptions import TooManyRequestsError

TENANT = 4001


def _body(response) -> dict:
    """`SuccessResponse` 是 ORJSONResponse，不是 dict：取 body 再解一次。"""
    import orjson

    return orjson.loads(response.body)


class _CountingCache:
    """Stand-in for the Redis strict counter."""

    def __init__(self, value: int | None) -> None:
        self.value = value
        self.calls: list[tuple[str, int]] = []

    async def incr_with_ttl_strict(self, key: str, *, ttl_seconds: int) -> int | None:
        self.calls.append((key, ttl_seconds))
        if self.value is None:
            return None
        current = self.value
        self.value += 1
        return current


def _use_cache(monkeypatch: pytest.MonkeyPatch, cache: _CountingCache) -> None:
    monkeypatch.setattr(public_intake, "get_redis_cache", lambda: cache)


def _payload(**overrides) -> PublicTicketCreate:
    data = {
        "name": "Dana",
        "email": "dana@example.com",
        "message": "the export never finishes",
        "category": "incident",
    }
    data.update(overrides)
    return PublicTicketCreate(**data)


def _resolve_to(monkeypatch: pytest.MonkeyPatch, tenant_id: int) -> None:
    class _Tenant:
        id = tenant_id

    class _Resolved:
        tenant = _Tenant()

    async def _fake(*, request, db, module_code):  # noqa: ANN001
        assert module_code == "support", "匿名入口必须校验**自己**的模块开关"
        return _Resolved()

    monkeypatch.setattr(support_api, "resolve_public_tenant_for_module", _fake)


def test_honeypot_detects_a_filled_hidden_field() -> None:
    assert public_intake.is_honeypot_hit(None) is False
    assert public_intake.is_honeypot_hit("") is False
    assert public_intake.is_honeypot_hit("   ") is False
    assert public_intake.is_honeypot_hit("http://spam.example") is True


@pytest.mark.asyncio
async def test_rate_limit_allows_the_window_then_rejects(
    monkeypatch: pytest.MonkeyPatch, anonymous_request
) -> None:
    cache = _CountingCache(1)
    _use_cache(monkeypatch, cache)

    for _ in range(PUBLIC_SUBMIT_MAX_PER_WINDOW):
        await public_intake.enforce_public_submit_rate_limit(
            tenant_id=TENANT, request=anonymous_request
        )

    with pytest.raises(TooManyRequestsError):
        await public_intake.enforce_public_submit_rate_limit(
            tenant_id=TENANT, request=anonymous_request
        )


@pytest.mark.asyncio
async def test_rate_limit_key_is_scoped_by_tenant_and_client(
    monkeypatch: pytest.MonkeyPatch, anonymous_request
) -> None:
    cache = _CountingCache(1)
    _use_cache(monkeypatch, cache)

    await public_intake.enforce_public_submit_rate_limit(
        tenant_id=TENANT, request=anonymous_request
    )

    key, ttl = cache.calls[0]
    assert key == f"support:public_submit:{TENANT}:203.0.113.9"
    assert ttl > 0


@pytest.mark.asyncio
async def test_rate_limit_fails_closed_when_the_counter_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, anonymous_request
) -> None:
    """Redis 不可用 => `incr_with_ttl_strict` 返回 None => 必须**拒绝**。"""
    _use_cache(monkeypatch, _CountingCache(None))

    with pytest.raises(TooManyRequestsError):
        await public_intake.enforce_public_submit_rate_limit(
            tenant_id=TENANT, request=anonymous_request
        )


@pytest.mark.asyncio
async def test_the_pack_uses_the_strict_counter_not_the_best_effort_one() -> None:
    """写死这条：把 `incr_with_ttl_strict` 换成 `incr` 时上面的 fail-closed 用例仍会过，
    因为 `incr` 在故障时返回 0——所以这里直接盯住调用的是哪一个原语。"""
    import inspect

    source = inspect.getsource(public_intake)
    assert "incr_with_ttl_strict" in source
    assert ".incr(" not in source


@pytest.mark.asyncio
async def test_honeypot_hit_accepts_silently_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, anonymous_request, db
) -> None:
    _resolve_to(monkeypatch, TENANT)
    cache = _CountingCache(1)
    _use_cache(monkeypatch, cache)

    response = await support_api.submit_public_ticket(
        data=_payload(website="http://spam.example"),
        request=anonymous_request,
        db=db,
    )

    payload = _body(response)["data"]
    assert payload["accepted"] is True
    assert payload["ticketId"] is None
    # 报错等于告诉对方这里有防护；也不该把机器人的请求算进真人的限流额度。
    assert cache.calls == []
    _, total = await SupportService(db).list_tickets(tenant_id=TENANT, page=1, page_size=20)
    assert total == 0


@pytest.mark.asyncio
async def test_public_submission_creates_an_anonymous_ticket(
    monkeypatch: pytest.MonkeyPatch, anonymous_request, db
) -> None:
    _resolve_to(monkeypatch, TENANT)
    _use_cache(monkeypatch, _CountingCache(1))

    response = await support_api.submit_public_ticket(
        data=_payload(source_page="/pricing"),
        request=anonymous_request,
        db=db,
    )

    payload = _body(response)["data"]
    ticket_id = payload["ticketId"]
    assert ticket_id is not None
    assert payload["ticketNo"].startswith(f"SUP-{TENANT}-")

    ticket = await SupportService(db).get_ticket(tenant_id=TENANT, ticket_id=ticket_id)
    assert ticket.requester_user_id == ANONYMOUS_REQUESTER_ID
    # 客服要能看到联系方式，否则匿名工单无法回复。
    assert "dana@example.com" in ticket.description
    assert ticket.extra["contact"]["sourcePage"] == "/pricing"


@pytest.mark.asyncio
async def test_public_submission_is_rejected_when_the_counter_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, anonymous_request, db
) -> None:
    _resolve_to(monkeypatch, TENANT)
    _use_cache(monkeypatch, _CountingCache(None))

    with pytest.raises(TooManyRequestsError):
        await support_api.submit_public_ticket(
            data=_payload(), request=anonymous_request, db=db
        )

    _, total = await SupportService(db).list_tickets(tenant_id=TENANT, page=1, page_size=20)
    assert total == 0
