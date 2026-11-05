from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.invitations.service import InvitationService
from app.domain.users.service import UserService


def _build_invitation_tenant(*, max_invites: int = 10, cost_credits: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        code="demo",
        name="Demo Tenant",
        config={
            "registration": {
                "invitation": {
                    "enabled": True,
                    "maxInvitesPerUser": max_invites,
                    "inviteCodeCostCredits": cost_credits,
                    "inviterRewardCredits": 5,
                    "inviteeRewardCredits": 3,
                    "rewardDelayDays": 7,
                }
            }
        },
    )


@pytest.mark.asyncio
async def test_invitation_service_generate_code_creates_single_use_code() -> None:
    service = InvitationService(SimpleNamespace())
    tenant = _build_invitation_tenant(max_invites=5)
    inviter = SimpleNamespace(id=8)
    created_payload: dict[str, object] = {}
    created_at = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)

    async def fake_create(payload: dict[str, object]) -> SimpleNamespace:
        created_payload.update(payload)
        return SimpleNamespace(
            id=101,
            code=payload["code"],
            status=payload["status"],
            expires_at=payload["expires_at"],
            max_uses=payload["max_uses"],
            used_count=payload["used_count"],
            last_used_at=payload["last_used_at"],
            created_at=created_at,
            extra=payload["extra"],
        )

    service.code_repo = SimpleNamespace(create=fake_create)
    service.count_invited_users = AsyncMock(return_value=2)  # type: ignore[method-assign]
    service.count_active_reserved_uses = AsyncMock(return_value=1)  # type: ignore[method-assign]
    service._generate_unique_code = AsyncMock(return_value="ABCD2345EF")  # type: ignore[method-assign]

    code = await service.generate_code(tenant=tenant, inviter_user=inviter, expires_days=14)

    assert created_payload["max_uses"] == 1
    assert code.max_uses == 1
    assert code.extra["expiresIn"] == 14
    assert code.extra["costCredits"] == 0


@pytest.mark.asyncio
async def test_invitation_service_summary_treats_unused_codes_as_reserved_quota() -> None:
    service = InvitationService(SimpleNamespace())
    tenant = _build_invitation_tenant(max_invites=10)

    service.count_invited_users = AsyncMock(return_value=4)  # type: ignore[method-assign]
    service.count_active_reserved_uses = AsyncMock(return_value=3)  # type: ignore[method-assign]
    service._count_related_records = AsyncMock(return_value=6)  # type: ignore[method-assign]
    service.list_user_codes = AsyncMock(return_value=[])  # type: ignore[method-assign]
    service._sum_reward_amount = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            Decimal("8"),
            Decimal("5"),
            Decimal("3"),
            Decimal("1"),
        ]
    )

    summary = await service.build_user_summary(tenant=tenant, user_id=8)

    assert summary["usedInviteCount"] == 4
    assert summary["activeReservedInviteQuota"] == 3
    assert summary["remainingInviteQuota"] == 3
    assert summary["userCanInvite"] is True


def test_invitation_service_to_code_response_includes_usage_snapshot() -> None:
    service = InvitationService(SimpleNamespace())
    tenant = _build_invitation_tenant()
    invite_code = SimpleNamespace(
        id=11,
        code="CODE123456",
        status="exhausted",
        expires_at=datetime(2026, 4, 30, 0, 0, tzinfo=UTC),
        max_uses=1,
        used_count=1,
        last_used_at=datetime(2026, 4, 14, 0, 0, tzinfo=UTC),
        created_at=datetime(2026, 4, 13, 0, 0, tzinfo=UTC),
        extra={"costCredits": 2, "expiresIn": 7},
    )

    payload = service.to_code_response(
        invite_code,
        tenant=tenant,
        usage={
            "invitedUserId": 99,
            "invitedUsername": "student",
            "invitedNickname": "学员",
            "invitedAt": "2026-04-14T00:00:00+00:00",
        },
    )

    assert payload["invitedUserId"] == 99
    assert payload["invitedUsername"] == "student"
    assert payload["invitedNickname"] == "学员"
    assert payload["invitedAt"] == "2026-04-14T00:00:00+00:00"
    assert payload["canRecycle"] is False


@pytest.mark.asyncio
async def test_invitation_service_recycle_code_disables_unused_code_and_refunds() -> None:
    service = InvitationService(SimpleNamespace())
    tenant = _build_invitation_tenant(max_invites=5, cost_credits=3)
    inviter = SimpleNamespace(id=8)
    invite_code = SimpleNamespace(
        id=15,
        tenant_id=1,
        inviter_user_id=8,
        code="UNUSED1234",
        status="active",
        expires_at=None,
        max_uses=1,
        used_count=0,
        last_used_at=None,
        extra={"costCredits": 3, "purchaseTxId": 99},
    )

    class _ScalarResult:
        def scalar_one_or_none(self) -> SimpleNamespace:
            return invite_code

    class _FakeDB:
        async def execute(self, stmt):  # noqa: ANN001
            return _ScalarResult()

        async def flush(self) -> None:
            return None

    service.db = _FakeDB()  # type: ignore[assignment]

    refund_mock = AsyncMock(return_value=SimpleNamespace(id=201))
    original_credit_service = service.recycle_code.__globals__["CreditService"]
    service.recycle_code.__globals__["CreditService"] = lambda db: SimpleNamespace(refund=refund_mock)
    try:
        recycled = await service.recycle_code(tenant=tenant, inviter_user=inviter, invite_code_id=15)
    finally:
        service.recycle_code.__globals__["CreditService"] = original_credit_service

    assert recycled.status == "disabled"
    assert recycled.extra["refundTxId"] == 201
    assert recycled.extra["refundedCredits"] == 3
    assert recycled.extra["recycledAt"]
    refund_mock.assert_awaited_once()


def test_user_service_response_shapes_include_invitation_context() -> None:
    user = SimpleNamespace(
        id=7,
        username="demo_user",
        nickname="Demo",
        avatar=None,
        email=None,
        phone=None,
        sex=0,
        status=1,
        description=None,
        register_source="invite",
        tenant_id=1,
        organization_id=None,
        remark=None,
        created_at=datetime(2026, 4, 13, 0, 0, tzinfo=UTC),
        last_login_at=None,
        organization=None,
        teams=[],
        roles=[],
        extra={},
    )
    invitation_context = {
        "invitedByUserId": 2,
        "invitedByUsername": "owner",
        "invitedByNickname": "负责人",
        "invitedViaInviteCode": "CODE123456",
        "invitedAt": "2026-04-13T00:00:00+00:00",
    }

    list_item = UserService.to_list_item(user, invitation_context=invitation_context)
    detail = UserService.to_response(user, invitation_context=invitation_context)

    assert list_item["invitedByUsername"] == "owner"
    assert list_item["invitedViaInviteCode"] == "CODE123456"
    assert detail["invitedByNickname"] == "负责人"
    assert detail["invitedAt"] == "2026-04-13T00:00:00+00:00"
