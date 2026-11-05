"""
AOJU Backend - Credits Endpoints

积分模块（系统级基础能力，多租户隔离）：
- 账户管理（分页、详情、初始化租户账户、冻结/解冻）
- 管理员充值
- 交易流水查询

权限建议（可在菜单/权限中配置）：
- credits:account:list / credits:read
- credits:account:init
- credits:account:update
- credits:recharge
- credits:transaction:list
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx, _get_user_tenant_id
from app.core.dialect_features import require_postgresql
from app.core.exceptions import BusinessError, NotFoundError
from app.core.logger import get_logger
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.credits.schemas import (
    CreditAccountListItem,
    CreditAccountResponse,
    CreditAccountStatusUpdate,
    CreditBulkRechargeRequest,
    CreditBulkRechargeResponse,
    CreditRechargeRequest,
    CreditStatsResponse,
    CreditTeamOption,
    CreditTransactionListItem,
    CreditTransactionResponse,
    CreditUserBalanceListItem,
    CreditUserOption,
)
from app.domain.credits.service import CreditService
from app.domain.teams.models import Team
from app.domain.teams.service import TeamService
from app.domain.users.models import User
from app.domain.users.service import UserService

logger = get_logger(__name__)

router = APIRouter()


def _snapshot_current_user(current_user: Any) -> tuple[int, int]:
    """Capture stable scalar values before awaited service calls."""
    user_id = int(getattr(current_user, "id", 0) or 0)
    tenant_id = int(getattr(current_user, "tenant_id", 0) or 0)
    if tenant_id <= 0:
        tenant_id = _get_user_tenant_id(current_user)
    return user_id, tenant_id


class CreditAccountListQuery(BaseModel):
    """Credit account list query parameters (GET)"""

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    account_type: str | None = Field(None, alias="accountType")
    status: str | None = None
    user_id: int | None = Field(None, alias="userId")
    # 排序参数
    sort_by: str | None = Field(
        None,
        alias="sortBy",
        description="排序字段: id, balance, created_at",
    )
    sort_order: str | None = Field(
        None,
        alias="sortOrder",
        description="排序方向: asc, desc",
    )

    model_config = ConfigDict(populate_by_name=True)


class CreditTransactionListQuery(BaseModel):
    """Credit transaction list query parameters (GET)"""

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        10,
        ge=1,
        le=200,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    account_id: int | None = Field(None, alias="accountId")
    user_id: int | None = Field(None, alias="userId")
    transaction_type: str | None = Field(None, alias="transactionType")
    direction: str | None = None
    start_at: datetime | None = Field(
        None,
        alias="startAt",
        validation_alias=AliasChoices("startAt", "startDate", "startTime"),
    )
    end_at: datetime | None = Field(
        None,
        alias="endAt",
        validation_alias=AliasChoices("endAt", "endDate", "endTime"),
    )
    # 排序参数
    sort_by: str | None = Field(
        None,
        alias="sortBy",
        description="排序字段: id, amount, created_at",
    )
    sort_order: str | None = Field(
        None,
        alias="sortOrder",
        description="排序方向: asc, desc",
    )

    model_config = ConfigDict(populate_by_name=True)


class CreditOptionQuery(BaseModel):
    """Credit option query parameters."""

    keyword: str | None = Field(None, alias="keyword", validation_alias=AliasChoices("keyword", "q"))
    limit: int = Field(20, ge=1, le=100)

    model_config = ConfigDict(populate_by_name=True)


class CreditUserBalanceListQuery(BaseModel):
    """Credit user balance query parameters."""

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        20,
        ge=1,
        le=100,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    keyword: str | None = Field(None, alias="keyword", validation_alias=AliasChoices("keyword", "q"))
    user_status: int | None = Field(None, alias="userStatus")
    account_status: str | None = Field(None, alias="accountStatus")
    team_id: int | None = Field(None, alias="teamId")

    model_config = ConfigDict(populate_by_name=True)


# ==================== Summary / Options ====================


@router.get("/stats", response_model=ResponseBase[CreditStatsResponse])
async def get_credit_stats(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:read", "credits:account:list"])),
) -> dict[str, Any]:
    """Get credits summary for current tenant."""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)
    stats = await service.get_credit_stats(tenant_id=tenant_ctx.tenant_id)
    logger.info(
        "credit_stats_retrieved",
        user_id=current_user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
    )
    return SuccessResponse(data=stats)


@router.get("/options/users", response_model=ResponseBase[list[CreditUserOption]])
async def list_credit_user_options(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: CreditOptionQuery = Depends(),
    _: None = Depends(PermissionChecker(["credits:read", "credits:recharge", "credits:account:list"])),
) -> dict[str, Any]:
    """List tenant users for credits selector/search."""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)
    options = await service.list_credit_user_options(
        tenant_id=tenant_ctx.tenant_id,
        keyword=query.keyword,
        limit=query.limit,
    )
    logger.info(
        "credit_user_options_retrieved",
        user_id=current_user_id,
        tenant_id=tenant_ctx.tenant_id,
        count=len(options),
    )
    return SuccessResponse(data=options)


@router.get("/options/teams", response_model=ResponseBase[list[CreditTeamOption]])
async def list_credit_team_options(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: CreditOptionQuery = Depends(),
    _: None = Depends(PermissionChecker(["credits:read", "credits:recharge", "credits:account:list"])),
) -> dict[str, Any]:
    """List tenant teams for credits selector/search."""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)
    options = await service.list_credit_team_options(
        tenant_id=tenant_ctx.tenant_id,
        keyword=query.keyword,
        limit=query.limit,
    )
    logger.info(
        "credit_team_options_retrieved",
        user_id=current_user_id,
        tenant_id=tenant_ctx.tenant_id,
        count=len(options),
    )
    return SuccessResponse(data=options)


@router.get("/user-balances", response_model=ResponseBase[PageResponse[CreditUserBalanceListItem]])
async def list_credit_user_balances(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: CreditUserBalanceListQuery = Depends(),
    _: None = Depends(PermissionChecker(["credits:read", "credits:account:list"])),
) -> dict[str, Any]:
    """List tenant users with current credit balances."""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)
    rows, total = await service.list_user_balances(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        keyword=query.keyword,
        user_status=query.user_status,
        account_status=query.account_status,
        team_ids=[query.team_id] if query.team_id else None,
    )
    logger.info(
        "credit_user_balances_retrieved",
        user_id=current_user_id,
        tenant_id=tenant_ctx.tenant_id,
        count=len(rows),
        total=total,
    )
    return SuccessResponse(
        data={
            "list": rows,
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


# ==================== Accounts ====================


@router.get("/accounts", response_model=ResponseBase[PageResponse[CreditAccountListItem]])
async def list_credit_accounts(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: CreditAccountListQuery = Depends(),
    _: None = Depends(PermissionChecker(["credits:read", "credits:account:list"])),
) -> dict[str, Any]:
    """Get credit account list (paginated, tenant-scoped)"""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)

    accounts, total = await service.list_accounts(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        account_type=query.account_type,
        status=query.status,
        user_id=query.user_id,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    logger.info(
        "credit_accounts_list_retrieved",
        user_id=current_user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(accounts),
        total=total,
    )

    return SuccessResponse(
        data={
            "list": [CreditService.to_account_response(a) for a in accounts],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/accounts/{account_id}", response_model=ResponseBase[CreditAccountResponse])
async def get_credit_account(
    account_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:read", "credits:account:list"])),
) -> dict[str, Any]:
    """Get credit account detail (tenant-scoped)"""
    service = CreditService(db)
    account = await service.get_account_by_id(account_id, tenant_ctx.tenant_id)
    if not account:
        raise NotFoundError(message="积分账户不存在")
    return SuccessResponse(data=CreditService.to_account_response(account))


@router.post("/accounts/init", response_model=ResponseBase[CreditAccountResponse])
async def init_tenant_credit_account(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:account:init"])),
) -> dict[str, Any]:
    """Initialize tenant credit account (idempotent)"""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)
    account = await service.init_tenant_account(tenant_id=tenant_ctx.tenant_id, operator_id=current_user_id)
    return SuccessResponse(data=CreditService.to_account_response(account), message="租户积分账户已初始化")


@router.put("/accounts/{account_id}/status", response_model=ResponseBase[CreditAccountResponse])
async def update_credit_account_status(
    account_id: int,
    data: CreditAccountStatusUpdate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:account:update"])),
) -> dict[str, Any]:
    """Freeze/unfreeze credit account"""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)
    account = await service.update_account_status(
        account_id=account_id,
        tenant_id=tenant_ctx.tenant_id,
        status=data.status,
        operator_id=current_user_id,
    )
    return SuccessResponse(data=CreditService.to_account_response(account), message="账户状态更新成功")


# ==================== Recharge ====================


@router.post("/recharge", response_model=ResponseBase[CreditTransactionResponse])
async def recharge_credits(
    data: CreditRechargeRequest,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:recharge"])),
) -> dict[str, Any]:
    """Recharge credits by admin"""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)
    tx = await service.recharge(
        tenant_id=tenant_ctx.tenant_id,
        account_id=data.account_id,
        amount=data.amount,
        operator_id=current_user_id,
        remark=data.remark,
        reference_type=data.reference_type,
        reference_id=data.reference_id,
        extra=data.extra,
    )
    return SuccessResponse(data=CreditService.to_transaction_response(tx), message="充值成功")


@router.post("/recharge/bulk", response_model=ResponseBase[CreditBulkRechargeResponse])
async def bulk_recharge_credits(
    data: CreditBulkRechargeRequest,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:recharge"])),
) -> dict[str, Any]:
    """Bulk recharge credits for users or teams (tenant-scoped)."""
    current_user_id, _ = _snapshot_current_user(current_user)
    requested_user_ids: set[int] = {int(uid) for uid in (data.user_ids or [])}

    if data.team_ids:
        team_ids = [int(tid) for tid in data.team_ids]
        stmt = select(Team.id).where(
            Team.tenant_id == tenant_ctx.tenant_id,
            Team.id.in_(team_ids),
            Team.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        existing_team_ids = {int(row[0]) for row in result.all()}
        missing_team_ids = sorted(set(team_ids) - existing_team_ids)
        if missing_team_ids:
            raise NotFoundError(message=f"团队不存在: {missing_team_ids}")

        team_service = TeamService(db)
        effective_team_ids: set[int] = set()
        for team_id in existing_team_ids:
            if data.include_children:
                child_ids = await team_service.get_children_ids(team_id, tenant_ctx.tenant_id, include_self=True)
                effective_team_ids.update(int(x) for x in child_ids)
            else:
                effective_team_ids.add(int(team_id))

        if effective_team_ids:
            user_service = UserService(db)
            users, _ = await user_service.list_users(
                tenant_id=tenant_ctx.tenant_id,
                page_size=0,
                team_ids=sorted(effective_team_ids),
            )
            requested_user_ids.update(int(u.id) for u in users)

    if not requested_user_ids:
        raise BusinessError(message="请选择目标用户或团队")

    # Validate users exist (tenant-scoped)
    stmt_users = select(User.id).where(
        User.tenant_id == tenant_ctx.tenant_id,
        User.id.in_(sorted(requested_user_ids)),
        User.deleted_at.is_(None),
    )
    result_users = await db.execute(stmt_users)
    existing_user_ids = {int(row[0]) for row in result_users.all()}
    missing_user_ids = sorted(requested_user_ids - existing_user_ids)

    failures: list[dict[str, Any]] = [{"userId": uid, "reason": "用户不存在"} for uid in missing_user_ids]

    service = CreditService(db)
    succeeded = 0
    for user_id in sorted(existing_user_ids):
        try:
            async with db.begin_nested():
                account = await service.init_user_account(
                    tenant_id=tenant_ctx.tenant_id,
                    user_id=user_id,
                    operator_id=current_user_id,
                )
                await service.recharge(
                    tenant_id=tenant_ctx.tenant_id,
                    account_id=account.id,
                    amount=data.amount,
                    operator_id=current_user_id,
                    remark=data.remark,
                    reference_type=data.reference_type,
                    reference_id=data.reference_id,
                    extra=data.extra,
                )
            succeeded += 1
        except BusinessError as exc:
            failures.append({"userId": user_id, "reason": exc.message})
        except Exception:
            failures.append({"userId": user_id, "reason": "充值失败"})

    response: dict[str, Any] = {
        "requested": len(requested_user_ids),
        "succeeded": succeeded,
        "failed": len(failures),
        "failures": failures,
    }
    return SuccessResponse(data=response, message="批量充值完成")


# ==================== Transactions ====================


@router.get("/transactions", response_model=ResponseBase[PageResponse[CreditTransactionListItem]])
async def list_credit_transactions(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    query: CreditTransactionListQuery = Depends(),
    _: None = Depends(PermissionChecker(["credits:read", "credits:transaction:list"])),
) -> dict[str, Any]:
    """Get credit transaction list (paginated, tenant-scoped)"""
    current_user_id, _ = _snapshot_current_user(current_user)
    service = CreditService(db)
    transactions, total = await service.list_transactions(
        tenant_id=tenant_ctx.tenant_id,
        page=query.page,
        page_size=query.page_size,
        account_id=query.account_id,
        account_user_id=query.user_id,
        transaction_type=query.transaction_type,
        direction=query.direction,
        created_between=(query.start_at, query.end_at) if (query.start_at or query.end_at) else None,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    logger.info(
        "credit_transactions_list_retrieved",
        user_id=current_user_id,
        tenant_id=tenant_ctx.tenant_id,
        is_cross_tenant=tenant_ctx.is_cross_tenant,
        count=len(transactions),
        total=total,
    )

    return SuccessResponse(
        data={
            "list": [CreditService.to_transaction_response(tx) for tx in transactions],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/transactions/{tx_id}", response_model=ResponseBase[CreditTransactionResponse])
async def get_credit_transaction(
    tx_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:read", "credits:transaction:list"])),
) -> dict[str, Any]:
    """Get credit transaction detail (tenant-scoped)"""
    service = CreditService(db)
    tx = await service.get_transaction_by_id(tx_id, tenant_ctx.tenant_id)
    if not tx:
        raise NotFoundError(message="交易不存在")
    return SuccessResponse(data=CreditService.to_transaction_response(tx))


# ==================== My Data (No Permission Required) ====================


@router.get("/my/account", response_model=ResponseBase[CreditAccountResponse])
async def get_my_credit_account(
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """获取当前用户的积分账户（无需权限，必要时自动初始化）"""
    current_user_id, current_tenant_id = _snapshot_current_user(current_user)
    service = CreditService(db)
    account = await service.get_user_account(
        tenant_id=current_tenant_id,
        user_id=current_user_id,
    )
    if not account:
        account = await service.init_user_account(
            tenant_id=current_tenant_id,
            user_id=current_user_id,
            operator_id=current_user_id,
        )
    return SuccessResponse(data=CreditService.to_account_response(account))


@router.get("/my/transactions", response_model=ResponseBase[PageResponse[CreditTransactionListItem]])
async def list_my_credit_transactions(
    current_user: CurrentUser,
    db: DBSession,
    query: CreditTransactionListQuery = Depends(),
) -> dict[str, Any]:
    """获取当前用户的积分流水（无需权限）"""
    current_user_id, current_tenant_id = _snapshot_current_user(current_user)
    service = CreditService(db)

    # 先获取用户账户
    account = await service.get_user_account(
        tenant_id=current_tenant_id,
        user_id=current_user_id,
    )
    if not account:
        account = await service.init_user_account(
            tenant_id=current_tenant_id,
            user_id=current_user_id,
            operator_id=current_user_id,
        )

    transactions, total = await service.list_transactions(
        tenant_id=current_tenant_id,
        page=query.page,
        page_size=query.page_size,
        account_id=account.id,
        transaction_type=query.transaction_type,
        direction=query.direction,
        created_between=(query.start_at, query.end_at) if (query.start_at or query.end_at) else None,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    logger.info(
        "my_credit_transactions_retrieved",
        user_id=current_user_id,
        account_id=account.id,
        count=len(transactions),
        total=total,
    )

    return SuccessResponse(
        data={
            "list": [CreditService.to_transaction_response(tx) for tx in transactions],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


# ---------------------------------------------------------------------------
# 统一积分策略：计价模式 + 费率（平台 pricebook + 租户覆盖）
# 方案：devdocs/plans/UNIFIED_CREDIT_PRICING_PLAN_20260826.md
# ---------------------------------------------------------------------------
from app.domain.credits.price_service import (  # noqa: E402
    delete_tenant_price_item,
    list_price_rows,
    price_row_to_view,
    pricebook_items,
    pricebook_version,
    upsert_tenant_price_item,
)
from app.domain.credits.pricing import PRICE_ITEM_TYPES  # noqa: E402
from app.domain.credits.pricing_mode import (  # noqa: E402
    PRICEBOOK_BASE_MARGIN_PERCENT,
    PRICING_MODES,
    get_tenant_price_adjustment,
    get_tenant_pricing_mode,
    set_tenant_price_adjustment,
    set_tenant_pricing_mode,
)


class CreditPricingModeUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pricing_mode: str = Field(validation_alias=AliasChoices("pricingMode", "pricing_mode"))


class CreditPriceItemUpsert(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    item_type: str = Field(validation_alias=AliasChoices("itemType", "item_type"))
    match_key: str = Field(validation_alias=AliasChoices("matchKey", "match_key"), min_length=1, max_length=200)
    input_points_per_1k: str | float | int | None = Field(default=None, validation_alias=AliasChoices("inputPointsPer1k", "input_points_per_1k"))
    output_points_per_1k: str | float | int | None = Field(default=None, validation_alias=AliasChoices("outputPointsPer1k", "output_points_per_1k"))
    cached_points_per_1k: str | float | int | None = Field(default=None, validation_alias=AliasChoices("cachedPointsPer1k", "cached_points_per_1k"))
    cache_write_points_per_1k: str | float | int | None = Field(default=None, validation_alias=AliasChoices("cacheWritePointsPer1k", "cache_write_points_per_1k"))
    points_per_unit: str | float | int | None = Field(default=None, validation_alias=AliasChoices("pointsPerUnit", "points_per_unit"))
    unit_divisor: str | float | int | None = Field(default=None, validation_alias=AliasChoices("unitDivisor", "unit_divisor"))
    priority: int = 0
    is_active: bool = Field(default=True, validation_alias=AliasChoices("isActive", "is_active"))
    remark: str = ""
    rate_schedule: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("rateSchedule", "rate_schedule"),
    )


def _pricebook_item_view(item: Any) -> dict[str, Any]:
    rate_schedule = dict(item.rate_schedule or {})
    return {
        "id": None,
        "tenantId": None,
        "scope": "platform",
        "itemType": item.item_type,
        "matchKey": item.match_key,
        "inputPointsPer1k": str(item.input_points_per_1k),
        "outputPointsPer1k": str(item.output_points_per_1k),
        "cachedPointsPer1k": str(item.cached_points_per_1k) if item.cached_points_per_1k is not None else None,
        "cacheWritePointsPer1k": str(item.cache_write_points_per_1k) if item.cache_write_points_per_1k is not None else None,
        "pointsPerUnit": str(item.points_per_unit),
        "unitDivisor": str(item.unit_divisor) if item.unit_divisor is not None else None,
        "priority": int(item.priority or 0),
        "isActive": bool(item.is_active),
        "remark": item.remark or "",
        "rateSchedule": rate_schedule or None,
        "updatedAt": None,
    }


async def _pricing_overview(db: DBSession, tenant_id: int) -> dict[str, Any]:
    from app.core.tenant_time import get_tenant_timezone, tenant_now

    overrides = [price_row_to_view(row) for row in await list_price_rows(db, tenant_id=tenant_id)]
    timezone_name = await get_tenant_timezone(db, tenant_id=tenant_id)
    return {
        "pricingMode": await get_tenant_pricing_mode(db, tenant_id=tenant_id),
        "marginPercent": str((await get_tenant_price_adjustment(db, tenant_id=tenant_id))[0]),
        "cachedBilling": (await get_tenant_price_adjustment(db, tenant_id=tenant_id))[1],
        "pricebookBaseMarginPercent": PRICEBOOK_BASE_MARGIN_PERCENT,
        "availableModes": list(PRICING_MODES),
        "pricebookVersion": pricebook_version(),
        "itemTypes": list(PRICE_ITEM_TYPES),
        "tenantTimezone": timezone_name,
        "currentTenantTime": tenant_now(timezone_name).isoformat(),
        "platformItems": [_pricebook_item_view(item) for item in pricebook_items()],
        "tenantOverrides": overrides,
    }


@router.get("/pricing", response_model=ResponseBase[dict[str, Any]])
async def get_credit_pricing(
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:read"])),
) -> dict[str, Any]:
    """计价模式 + 平台默认费率（版本化 pricebook）+ 本租户覆盖项。"""
    return SuccessResponse(data=await _pricing_overview(db, tenant_ctx.tenant_id))


@router.put("/pricing/mode", response_model=ResponseBase[dict[str, Any]])
async def update_credit_pricing_mode(
    payload: CreditPricingModeUpdate,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:pricing:update"])),
) -> dict[str, Any]:
    current_user_id, _ = _snapshot_current_user(current_user)
    mode = await set_tenant_pricing_mode(db, tenant_id=tenant_ctx.tenant_id, mode=payload.pricing_mode)
    await db.commit()
    logger.info("credit_pricing_mode_updated", tenant_id=tenant_ctx.tenant_id, user_id=current_user_id, pricing_mode=mode)
    return SuccessResponse(data=await _pricing_overview(db, tenant_ctx.tenant_id))


class CreditPriceAdjustmentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    margin_percent: str | float | int | None = Field(default=None, validation_alias=AliasChoices("marginPercent", "margin_percent"))
    cached_billing: str | None = Field(default=None, validation_alias=AliasChoices("cachedBilling", "cached_billing"))


@router.put("/pricing/margin", response_model=ResponseBase[dict[str, Any]])
async def update_credit_price_adjustment(
    data: CreditPriceAdjustmentUpdate,
    tenant_ctx: TenantCtx,
    db: DBSession,
    current_user: CurrentUser,
    _: None = Depends(PermissionChecker(["credits:pricing:update"])),
):
    """租户毛利（%）与缓存计费方式。平台标价内置 30% 毛利；m=30 即平台默认价。

    full_price：缓存命中仍按输入价向客户计费，缓存节省归平台；passthrough（缺省）：按官方缓存价，折扣让给客户。
    """
    margin, cached = await set_tenant_price_adjustment(
        db, tenant_id=tenant_ctx.tenant_id, margin_percent=data.margin_percent, cached_billing=data.cached_billing
    )
    await db.commit()
    logger.info("credit_price_adjustment_updated", tenant_id=tenant_ctx.tenant_id, user_id=current_user.id, margin=str(margin), cached_billing=cached)
    return SuccessResponse(data={"marginPercent": str(margin), "cachedBilling": cached})



@router.put("/pricing/items", response_model=ResponseBase[dict[str, Any]])
async def upsert_credit_price_item(
    payload: CreditPriceItemUpsert,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:pricing:update"])),
) -> dict[str, Any]:
    """新增/更新本租户的一条费率覆盖（同 itemType+matchKey 覆盖而非新增）。"""
    current_user_id, _ = _snapshot_current_user(current_user)
    row = await upsert_tenant_price_item(db, tenant_id=tenant_ctx.tenant_id, payload=payload.model_dump(by_alias=False))
    await db.commit()
    logger.info("credit_price_item_upserted", tenant_id=tenant_ctx.tenant_id, user_id=current_user_id, item_id=row.id, item_type=row.item_type, match_key=row.match_key)
    return SuccessResponse(data=price_row_to_view(row))


@router.delete("/pricing/items/{item_id}", response_model=ResponseBase[dict[str, Any]])
async def delete_credit_price_item(
    item_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker(["credits:pricing:update"])),
) -> dict[str, Any]:
    current_user_id, _ = _snapshot_current_user(current_user)
    removed = await delete_tenant_price_item(db, tenant_id=tenant_ctx.tenant_id, item_id=item_id)
    if not removed:
        raise NotFoundError(message="费率覆盖项不存在")
    await db.commit()
    logger.info("credit_price_item_deleted", tenant_id=tenant_ctx.tenant_id, user_id=current_user_id, item_id=item_id)
    return SuccessResponse(data={"deleted": True, "id": item_id})


@router.get(
    "/pricing/reconciliation",
    response_model=ResponseBase[dict[str, Any]],
    dependencies=[Depends(require_postgresql("credits.pricing_reconciliation"))],
)
async def get_credit_pricing_reconciliation(
    tenant_ctx: TenantCtx,
    db: DBSession,
    days: int = 7,
    _: None = Depends(PermissionChecker(["credits:read"])),
) -> dict[str, Any]:
    """shadow/unified 灰度对账：按 reference_type 汇总旧口径金额 vs 统一费率结果，以及计量覆盖率指标。

    指标口径（codex 评审 P3-2）：事件覆盖率（有 billing 明细的流水占比）、估算率、兜底费率命中率、
    flat 兜底占比、legacy 与 unified 差额。只读 credit_transactions.extra，不建新表。
    """
    from sqlalchemy import text as sql_text

    window_days = max(1, min(90, int(days or 7)))
    params = {"tenant_id": int(tenant_ctx.tenant_id), "days": str(window_days)}  # asyncpg 文本拼接参数需为 str
    by_type = (
        await db.execute(
            sql_text(
                """
                SELECT
                  reference_type,
                  COUNT(*)                                                                             AS tx_count,
                  COUNT(*) FILTER (WHERE extra ? 'billing')                                             AS with_billing,
                  COUNT(*) FILTER (WHERE extra->'billing'->>'pricingMode' = 'legacy' OR NOT (extra ? 'billing')) AS legacy_rows,
                  COUNT(*) FILTER (WHERE extra->'billing'->>'pricingMode' = 'shadow')                   AS shadow_rows,
                  COUNT(*) FILTER (WHERE extra->'billing'->>'pricingMode' = 'unified')                  AS unified_rows,
                  COUNT(*) FILTER (WHERE extra->'billing'->>'basis' = 'flat_fallback')                  AS flat_fallback_rows,
                  COUNT(*) FILTER (WHERE COALESCE(extra->'billing'->'shadow'->>'fallbackRate', extra->'billing'->>'fallbackRate') = 'true') AS fallback_rate_rows,
                  COALESCE(SUM(amount) FILTER (WHERE direction = 'out'), 0)                              AS charged_out,
                  COALESCE(SUM((extra->'billing'->>'legacyAmount')::numeric) FILTER (WHERE extra->'billing'->>'pricingMode' = 'shadow'), 0) AS shadow_legacy_sum,
                  COALESCE(SUM((extra->'billing'->'shadow'->>'points')::numeric) FILTER (WHERE extra->'billing'->>'pricingMode' = 'shadow'), 0) AS shadow_unified_sum
                FROM credit_transactions
                WHERE tenant_id = :tenant_id AND deleted_at IS NULL AND transaction_type = 'consume'
                  AND created_at >= now() - (:days || ' days')::interval
                GROUP BY reference_type
                ORDER BY tx_count DESC
                """
            ),
            params,
        )
    ).mappings().all()
    estimated = (
        await db.execute(
            sql_text(
                """
                SELECT
                  COUNT(*) AS items,
                  COUNT(*) FILTER (WHERE (item->>'estimated') = 'true') AS estimated_items,
                  COUNT(*) FILTER (WHERE COALESCE(item->>'model', '') = '') AS empty_model_items
                FROM credit_transactions t,
                     jsonb_array_elements(COALESCE(t.extra->'billing'->'items', t.extra->'billing'->'shadow'->'items', t.extra->'usage'->'items', '[]'::jsonb)) AS item
                WHERE t.tenant_id = :tenant_id AND t.deleted_at IS NULL AND t.transaction_type = 'consume'
                  AND t.created_at >= now() - (:days || ' days')::interval
                """
            ),
            params,
        )
    ).mappings().first()
    rows = [
        {
            "referenceType": r["reference_type"],
            "txCount": int(r["tx_count"]),
            "withBilling": int(r["with_billing"]),
            "legacyRows": int(r["legacy_rows"]),
            "shadowRows": int(r["shadow_rows"]),
            "unifiedRows": int(r["unified_rows"]),
            "flatFallbackRows": int(r["flat_fallback_rows"]),
            "fallbackRateRows": int(r["fallback_rate_rows"]),
            "chargedOut": str(r["charged_out"]),
            "shadowLegacySum": str(r["shadow_legacy_sum"]),
            "shadowUnifiedSum": str(r["shadow_unified_sum"]),
            "shadowDelta": str(Decimal(str(r["shadow_unified_sum"])) - Decimal(str(r["shadow_legacy_sum"]))),
        }
        for r in by_type
    ]
    total_tx = sum(r["txCount"] for r in rows)
    with_billing = sum(r["withBilling"] for r in rows)
    return SuccessResponse(
        data={
            "days": window_days,
            "pricebookVersion": pricebook_version(),
            "rows": rows,
            "coverage": {
                "txCount": total_tx,
                "withBilling": with_billing,
                "billingCoverage": (float(with_billing) / total_tx) if total_tx else None,
                "usageItems": int((estimated or {}).get("items") or 0),
                "estimatedItems": int((estimated or {}).get("estimated_items") or 0),
                "emptyModelItems": int((estimated or {}).get("empty_model_items") or 0),
                "fallbackRateRows": sum(r["fallbackRateRows"] for r in rows),
                "flatFallbackRows": sum(r["flatFallbackRows"] for r in rows),
            },
        }
    )
