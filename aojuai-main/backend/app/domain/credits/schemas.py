"""
AOJU Backend - Credits Schemas

积分模块 DTO 定义
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


CreditAccountTypeLiteral = Literal["tenant", "user"]
CreditAccountStatusLiteral = Literal["active", "frozen"]
CreditTransactionTypeLiteral = Literal[
    "recharge",
    "consume",
    "refund",
    "transfer",
    "bonus",
    "adjust",
]
CreditTransactionDirectionLiteral = Literal["in", "out"]


class CreditAccountBase(BaseModel):
    """Credit account base schema"""

    user_id: int | None = Field(None, description="关联用户ID（为空表示租户账户）")
    account_type: CreditAccountTypeLiteral = Field(..., description="账户类型 tenant|user")
    balance: Decimal = Field(default=Decimal("0"), description="当前余额")
    total_earned: Decimal = Field(default=Decimal("0"), description="累计获得")
    total_spent: Decimal = Field(default=Decimal("0"), description="累计消费")
    status: CreditAccountStatusLiteral = Field(default="active", description="状态 active|frozen")
    extra: dict[str, Any] = Field(default_factory=dict, description="扩展字段")


class CreditAccountListItem(CreditAccountBase):
    """Credit account list item"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    username: str | None = None
    nickname: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    email: str | None = None
    phone: str | None = None
    team_names: list[str] = Field(default_factory=list, alias="teamNames")
    created_at: str | None = None
    updated_at: str | None = None


class CreditAccountResponse(CreditAccountListItem):
    """Credit account detail response"""

    pass


class CreditAccountStatusUpdate(BaseModel):
    """Update credit account status"""

    status: CreditAccountStatusLiteral = Field(..., description="状态 active|frozen")


class CreditRechargeRequest(BaseModel):
    """Recharge credits request (admin)"""

    account_id: int = Field(..., alias="accountId", description="账户ID")
    amount: Decimal = Field(..., gt=0, description="充值积分（正数）")
    remark: str | None = Field(None, description="备注")
    reference_type: str | None = Field(None, alias="referenceType", description="业务类型")
    reference_id: int | None = Field(None, alias="referenceId", description="业务ID")
    extra: dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    model_config = ConfigDict(populate_by_name=True)


class CreditTransactionBase(BaseModel):
    """Credit transaction base schema"""

    account_id: int = Field(..., description="账户ID")
    transaction_type: CreditTransactionTypeLiteral = Field(..., description="交易类型")
    amount: Decimal = Field(..., description="金额（正数）")
    direction: CreditTransactionDirectionLiteral = Field(..., description="方向 in|out")
    balance_before: Decimal = Field(..., description="交易前余额")
    balance_after: Decimal = Field(..., description="交易后余额")
    reference_type: str | None = Field(None, description="关联业务类型")
    reference_id: int | None = Field(None, description="关联业务ID")
    remark: str | None = Field(None, description="备注")
    operator_id: int | None = Field(None, description="操作人ID")
    extra: dict[str, Any] = Field(default_factory=dict, description="扩展字段")


class CreditTransactionListItem(CreditTransactionBase):
    """Credit transaction list item"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    account_type: str | None = Field(None, alias="accountType")
    account_user_id: int | None = Field(None, alias="accountUserId")
    account_username: str | None = Field(None, alias="accountUsername")
    account_nickname: str | None = Field(None, alias="accountNickname")
    account_display_name: str | None = Field(None, alias="accountDisplayName")
    operator_username: str | None = Field(None, alias="operatorUsername")
    operator_nickname: str | None = Field(None, alias="operatorNickname")
    operator_display_name: str | None = Field(None, alias="operatorDisplayName")
    created_at: str | None = None


class CreditTransactionResponse(CreditTransactionListItem):
    """Credit transaction detail response"""

    pass


class CreditBulkRechargeRequest(BaseModel):
    """Bulk recharge credits request (tenant admin)"""

    user_ids: list[int] = Field(default_factory=list, alias="userIds", description="目标用户ID列表")
    team_ids: list[int] = Field(default_factory=list, alias="teamIds", description="目标团队ID列表")
    include_children: bool = Field(True, alias="includeChildren", description="团队是否包含子团队")

    amount: Decimal = Field(..., gt=0, description="充值积分（正数）")
    remark: str | None = Field(None, description="备注")
    reference_type: str | None = Field(None, alias="referenceType", description="业务类型")
    reference_id: int | None = Field(None, alias="referenceId", description="业务ID")
    extra: dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    model_config = ConfigDict(populate_by_name=True)


class CreditBulkRechargeFailure(BaseModel):
    """Bulk recharge failure item"""

    user_id: int = Field(..., alias="userId")
    reason: str

    model_config = ConfigDict(populate_by_name=True)


class CreditBulkRechargeResponse(BaseModel):
    """Bulk recharge response"""

    requested: int = Field(..., description="请求的目标用户数")
    succeeded: int = Field(..., description="成功数量")
    failed: int = Field(..., description="失败数量")
    failures: list[CreditBulkRechargeFailure] = Field(default_factory=list)


class CreditUserOption(BaseModel):
    """Credit user option for selector/search."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    username: str
    nickname: str | None = None
    label: str
    email: str | None = None
    phone: str | None = None
    status: int = 1
    team_names: list[str] = Field(default_factory=list, alias="teamNames")


class CreditTeamOption(BaseModel):
    """Credit team option for selector/search."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    code: str | None = None
    label: str
    status: int = 1
    parent_id: int | None = Field(None, alias="parentId")


class CreditUserBalanceListItem(BaseModel):
    """Tenant user credit balance view item."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(..., alias="userId")
    username: str
    nickname: str | None = None
    display_name: str = Field(..., alias="displayName")
    email: str | None = None
    phone: str | None = None
    user_status: int = Field(..., alias="userStatus")
    team_names: list[str] = Field(default_factory=list, alias="teamNames")
    account_id: int | None = Field(None, alias="accountId")
    has_account: bool = Field(False, alias="hasAccount")
    account_status: str = Field("uninitialized", alias="accountStatus")
    balance: Decimal = Field(default=Decimal("0"))
    total_earned: Decimal = Field(default=Decimal("0"), alias="totalEarned")
    total_spent: Decimal = Field(default=Decimal("0"), alias="totalSpent")
    created_at: str | None = Field(None, alias="createdAt")
    updated_at: str | None = Field(None, alias="updatedAt")


class CreditStatsResponse(BaseModel):
    """Credits summary for tenant admin page."""

    model_config = ConfigDict(populate_by_name=True)

    total_users: int = Field(0, alias="totalUsers")
    initialized_user_accounts: int = Field(0, alias="initializedUserAccounts")
    active_accounts: int = Field(0, alias="activeAccounts")
    frozen_accounts: int = Field(0, alias="frozenAccounts")
    total_user_balance: Decimal = Field(default=Decimal("0"), alias="totalUserBalance")
    tenant_balance: Decimal = Field(default=Decimal("0"), alias="tenantBalance")
    total_transactions: int = Field(0, alias="totalTransactions")
