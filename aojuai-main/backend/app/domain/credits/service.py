"""
AOJU Backend - Credits Service

积分业务逻辑：
- 账户初始化、冻结/解冻
- 充值（管理员）
- 消费/退款/赠送（供其他模块调用）

约束：
- 所有查询必须 tenant_id 过滤
- 金额 amount 必须为正数 Decimal
- 账户冻结时禁止变更余额
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.core.logger import get_logger
from app.domain.credits.migration_guard import raise_if_credits_schema_not_upgraded
from app.domain.credits.models import (
    CreditAccount,
    CreditAccountStatus,
    CreditAccountType,
    CreditTransaction,
    CreditTransactionDirection,
    CreditTransactionType,
)
from app.domain.teams.models import Team
from app.domain.users.models import User, UserTeam
from app.infrastructure.repository import RepositoryBase
from app.domain.credits.usage import current_usage_collector, usage_snapshot_for_extra
from app.infrastructure.database.portable_sql import escalate_to_write_lock

logger = get_logger(__name__)


class CreditService(RepositoryBase[CreditAccount]):
    """Credits business service"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, CreditAccount)
        self._account_options = [selectinload(CreditAccount.transactions)]

    @staticmethod
    def _compose_display_name(username: str | None, nickname: str | None) -> str:
        normalized_username = str(username or "").strip()
        normalized_nickname = str(nickname or "").strip()
        if normalized_nickname:
            return normalized_nickname
        if normalized_username:
            return normalized_username
        return "-"

    @classmethod
    def _compose_user_label(cls, username: str | None, nickname: str | None) -> str:
        normalized_username = str(username or "").strip()
        normalized_nickname = str(nickname or "").strip()
        if normalized_nickname and normalized_username and normalized_nickname != normalized_username:
            return f"{normalized_nickname}（{normalized_username}）"
        return normalized_nickname or normalized_username or "-"

    async def _load_team_names_by_user_ids(self, *, tenant_id: int, user_ids: list[int]) -> dict[int, list[str]]:
        normalized_user_ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        if not normalized_user_ids:
            return {}

        stmt = (
            select(UserTeam.user_id, Team.name)
            .select_from(UserTeam)
            .join(Team, Team.id == UserTeam.team_id)
            .where(
                UserTeam.user_id.in_(normalized_user_ids),
                Team.tenant_id == tenant_id,
                Team.deleted_at.is_(None),
            )
            .order_by(UserTeam.user_id.asc(), Team.sort_order.asc().nullslast(), Team.id.asc())
        )
        result = await self.db.execute(stmt)
        team_names: dict[int, list[str]] = defaultdict(list)
        for user_id, team_name in result.all():
            normalized_user_id = int(user_id)
            normalized_team_name = str(team_name or "").strip()
            if not normalized_team_name:
                continue
            if normalized_team_name in team_names[normalized_user_id]:
                continue
            team_names[normalized_user_id].append(normalized_team_name)
        return dict(team_names)

    async def _load_user_context_map(self, *, tenant_id: int, user_ids: list[int]) -> dict[int, dict[str, Any]]:
        normalized_user_ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        if not normalized_user_ids:
            return {}

        stmt = (
            select(User.id, User.username, User.nickname, User.email, User.phone, User.status)
            .where(
                User.tenant_id == tenant_id,
                User.id.in_(normalized_user_ids),
                User.deleted_at.is_(None),
            )
            .order_by(User.id.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        team_names_map = await self._load_team_names_by_user_ids(tenant_id=tenant_id, user_ids=normalized_user_ids)
        context_map: dict[int, dict[str, Any]] = {}
        for row in rows:
            row_map = row._mapping
            user_id = int(row_map["id"])
            username = row_map["username"]
            nickname = row_map["nickname"]
            context_map[user_id] = {
                "userId": user_id,
                "username": username,
                "nickname": nickname,
                "displayName": self._compose_display_name(username, nickname),
                "label": self._compose_user_label(username, nickname),
                "email": row_map["email"],
                "phone": row_map["phone"],
                "status": int(row_map["status"] or 0),
                "teamNames": team_names_map.get(user_id, []),
            }
        return context_map

    async def enrich_accounts(self, *, tenant_id: int, accounts: list[CreditAccount]) -> list[CreditAccount]:
        user_ids = [int(account.user_id) for account in accounts if account.user_id]
        if not user_ids:
            return accounts

        user_context_map = await self._load_user_context_map(tenant_id=tenant_id, user_ids=user_ids)
        for account in accounts:
            if not account.user_id:
                continue
            user_context = user_context_map.get(int(account.user_id))
            if not user_context:
                continue
            account.username = user_context.get("username")  # type: ignore[attr-defined]
            account.nickname = user_context.get("nickname")  # type: ignore[attr-defined]
            account.display_name = user_context.get("displayName")  # type: ignore[attr-defined]
            account.email = user_context.get("email")  # type: ignore[attr-defined]
            account.phone = user_context.get("phone")  # type: ignore[attr-defined]
            account.team_names = user_context.get("teamNames", [])  # type: ignore[attr-defined]
        return accounts

    async def enrich_transactions(self, *, tenant_id: int, transactions: list[CreditTransaction]) -> list[CreditTransaction]:
        normalized_transactions = list(transactions)
        if not normalized_transactions:
            return normalized_transactions

        account_ids = sorted({int(tx.account_id) for tx in normalized_transactions if int(tx.account_id) > 0})
        account_map: dict[int, CreditAccount] = {}
        if account_ids:
            stmt = (
                select(CreditAccount)
                .where(
                    CreditAccount.tenant_id == tenant_id,
                    CreditAccount.id.in_(account_ids),
                    CreditAccount.deleted_at.is_(None),
                )
                .order_by(CreditAccount.id.asc())
            )
            result = await self.db.execute(stmt)
            account_map = {int(account.id): account for account in result.scalars().all()}

        user_ids = {
            int(account.user_id)
            for account in account_map.values()
            if account.user_id is not None and int(account.user_id) > 0
        }
        user_ids.update(int(tx.operator_id) for tx in normalized_transactions if tx.operator_id is not None and int(tx.operator_id) > 0)
        user_context_map = await self._load_user_context_map(tenant_id=tenant_id, user_ids=list(user_ids))

        for tx in normalized_transactions:
            account = account_map.get(int(tx.account_id))
            if account:
                tx.account_type = account.account_type  # type: ignore[attr-defined]
                tx.account_user_id = account.user_id  # type: ignore[attr-defined]
                if account.user_id:
                    account_user_context = user_context_map.get(int(account.user_id))
                    if account_user_context:
                        tx.account_username = account_user_context.get("username")  # type: ignore[attr-defined]
                        tx.account_nickname = account_user_context.get("nickname")  # type: ignore[attr-defined]
                        tx.account_display_name = account_user_context.get("displayName")  # type: ignore[attr-defined]
            if tx.operator_id:
                operator_context = user_context_map.get(int(tx.operator_id))
                if operator_context:
                    tx.operator_username = operator_context.get("username")  # type: ignore[attr-defined]
                    tx.operator_nickname = operator_context.get("nickname")  # type: ignore[attr-defined]
                    tx.operator_display_name = operator_context.get("displayName")  # type: ignore[attr-defined]

        return normalized_transactions

    async def get_credit_stats(self, *, tenant_id: int) -> dict[str, Any]:
        total_users_stmt = select(func.count(User.id)).where(
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
        total_users = int((await self.db.execute(total_users_stmt)).scalar_one() or 0)

        user_account_stmt = (
            select(
                func.count(CreditAccount.id),
                func.count(CreditAccount.id).filter(CreditAccount.status == CreditAccountStatus.ACTIVE.value),
                func.count(CreditAccount.id).filter(CreditAccount.status == CreditAccountStatus.FROZEN.value),
                func.coalesce(func.sum(CreditAccount.balance), Decimal("0")),
            )
            .where(
                CreditAccount.tenant_id == tenant_id,
                CreditAccount.account_type == CreditAccountType.USER.value,
                CreditAccount.deleted_at.is_(None),
            )
        )
        initialized_user_accounts, active_accounts, frozen_accounts, total_user_balance = (
            await self.db.execute(user_account_stmt)
        ).one()

        tenant_balance_stmt = select(func.coalesce(func.sum(CreditAccount.balance), Decimal("0"))).where(
            CreditAccount.tenant_id == tenant_id,
            CreditAccount.account_type == CreditAccountType.TENANT.value,
            CreditAccount.deleted_at.is_(None),
        )
        tenant_balance = (await self.db.execute(tenant_balance_stmt)).scalar_one() or Decimal("0")

        total_transactions_stmt = select(func.count(CreditTransaction.id)).where(
            CreditTransaction.tenant_id == tenant_id,
            CreditTransaction.deleted_at.is_(None),
        )
        total_transactions = int((await self.db.execute(total_transactions_stmt)).scalar_one() or 0)

        return {
            "totalUsers": total_users,
            "initializedUserAccounts": int(initialized_user_accounts or 0),
            "activeAccounts": int(active_accounts or 0),
            "frozenAccounts": int(frozen_accounts or 0),
            "totalUserBalance": self._decimal_str(total_user_balance),
            "tenantBalance": self._decimal_str(tenant_balance),
            "totalTransactions": total_transactions,
        }

    async def list_credit_user_options(
        self,
        *,
        tenant_id: int,
        keyword: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 20), 100))
        normalized_keyword = str(keyword or "").strip()

        stmt = (
            select(User)
            .options(selectinload(User.teams))
            .where(User.tenant_id == tenant_id, User.deleted_at.is_(None))
            .order_by(User.status.desc(), User.id.desc())
            .limit(normalized_limit)
        )
        if normalized_keyword:
            like_pattern = f"%{normalized_keyword}%"
            stmt = stmt.where(
                or_(
                    User.username.ilike(like_pattern),
                    User.nickname.ilike(like_pattern),
                    User.email.ilike(like_pattern),
                    User.phone.ilike(like_pattern),
                )
            )

        result = await self.db.execute(stmt)
        users = list(result.scalars().unique().all())
        options: list[dict[str, Any]] = []
        for user in users:
            team_names = [str(team.name) for team in (user.teams or []) if getattr(team, "name", None)]
            options.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "label": self._compose_user_label(user.username, user.nickname),
                    "email": user.email,
                    "phone": user.phone,
                    "status": int(user.status or 0),
                    "teamNames": team_names,
                }
            )
        return options

    async def list_credit_team_options(
        self,
        *,
        tenant_id: int,
        keyword: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 20), 100))
        normalized_keyword = str(keyword or "").strip()

        stmt = (
            select(Team)
            .where(Team.tenant_id == tenant_id, Team.deleted_at.is_(None))
            .order_by(Team.sort_order.asc().nullslast(), Team.id.asc())
            .limit(normalized_limit)
        )
        if normalized_keyword:
            like_pattern = f"%{normalized_keyword}%"
            stmt = stmt.where(or_(Team.name.ilike(like_pattern), Team.code.ilike(like_pattern)))

        result = await self.db.execute(stmt)
        teams = list(result.scalars().all())
        return [
            {
                "id": team.id,
                "name": team.name,
                "code": team.code,
                "label": f"{team.name}（{team.code}）" if team.code else team.name,
                "status": int(team.status or 0),
                "parentId": team.parent_id,
            }
            for team in teams
        ]

    async def list_user_balances(
        self,
        *,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        user_status: int | None = None,
        account_status: str | None = None,
        team_ids: list[int] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        normalized_page = max(1, int(page or 1))
        normalized_page_size = max(1, min(int(page_size or 20), 100))
        normalized_keyword = str(keyword or "").strip()
        normalized_team_ids = sorted({int(team_id) for team_id in (team_ids or []) if int(team_id) > 0})

        where = [User.tenant_id == tenant_id, User.deleted_at.is_(None)]
        if normalized_keyword:
            like_pattern = f"%{normalized_keyword}%"
            where.append(
                or_(
                    User.username.ilike(like_pattern),
                    User.nickname.ilike(like_pattern),
                    User.email.ilike(like_pattern),
                    User.phone.ilike(like_pattern),
                )
            )
        if user_status is not None:
            where.append(User.status == user_status)
        if normalized_team_ids:
            where.append(User.id.in_(select(UserTeam.user_id).where(UserTeam.team_id.in_(normalized_team_ids))))

        if account_status == "uninitialized":
            where.append(
                ~User.id.in_(
                    select(CreditAccount.user_id).where(
                        CreditAccount.tenant_id == tenant_id,
                        CreditAccount.account_type == CreditAccountType.USER.value,
                        CreditAccount.deleted_at.is_(None),
                    )
                )
            )
        elif account_status in {CreditAccountStatus.ACTIVE.value, CreditAccountStatus.FROZEN.value}:
            where.append(
                User.id.in_(
                    select(CreditAccount.user_id).where(
                        CreditAccount.tenant_id == tenant_id,
                        CreditAccount.account_type == CreditAccountType.USER.value,
                        CreditAccount.status == account_status,
                        CreditAccount.deleted_at.is_(None),
                    )
                )
            )

        total_stmt = select(func.count(User.id)).where(*where)
        total = int((await self.db.execute(total_stmt)).scalar_one() or 0)

        stmt = (
            select(User)
            .options(selectinload(User.teams))
            .where(*where)
            .order_by(User.id.desc())
            .offset((normalized_page - 1) * normalized_page_size)
            .limit(normalized_page_size)
        )
        result = await self.db.execute(stmt)
        users = list(result.scalars().unique().all())
        user_ids = [int(user.id) for user in users]

        account_map: dict[int, CreditAccount] = {}
        if user_ids:
            account_stmt = (
                select(CreditAccount)
                .where(
                    CreditAccount.tenant_id == tenant_id,
                    CreditAccount.account_type == CreditAccountType.USER.value,
                    CreditAccount.user_id.in_(user_ids),
                    CreditAccount.deleted_at.is_(None),
                )
                .order_by(CreditAccount.id.asc())
            )
            account_result = await self.db.execute(account_stmt)
            account_map = {
                int(account.user_id): account
                for account in account_result.scalars().all()
                if account.user_id is not None
            }

        rows: list[dict[str, Any]] = []
        for user in users:
            account = account_map.get(int(user.id))
            team_names = [str(team.name) for team in (user.teams or []) if getattr(team, "name", None)]
            rows.append(
                {
                    "userId": user.id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "displayName": self._compose_display_name(user.username, user.nickname),
                    "email": user.email,
                    "phone": user.phone,
                    "userStatus": int(user.status or 0),
                    "teamNames": team_names,
                    "accountId": account.id if account else None,
                    "hasAccount": account is not None,
                    "accountStatus": account.status if account else "uninitialized",
                    "balance": self._decimal_str(account.balance if account else Decimal("0")),
                    "totalEarned": self._decimal_str(account.total_earned if account else Decimal("0")),
                    "totalSpent": self._decimal_str(account.total_spent if account else Decimal("0")),
                    "createdAt": account.created_at.isoformat() if account and getattr(account, "created_at", None) else None,
                    "updatedAt": account.updated_at.isoformat() if account and getattr(account, "updated_at", None) else None,
                }
            )

        return rows, total

    # ==================== Accounts ====================

    async def get_account_by_id(self, account_id: int, tenant_id: int) -> CreditAccount | None:
        """Get credit account by ID (tenant-scoped)"""
        account = await self.get_one(where=[CreditAccount.id == account_id, CreditAccount.tenant_id == tenant_id])
        if account:
            await self.enrich_accounts(tenant_id=tenant_id, accounts=[account])
        return account

    async def get_tenant_account(self, tenant_id: int) -> CreditAccount | None:
        """Get tenant account (tenant-scoped)"""
        return await self.get_one(
            where=[
                CreditAccount.tenant_id == tenant_id,
                CreditAccount.account_type == CreditAccountType.TENANT.value,
                CreditAccount.user_id.is_(None),
            ]
        )

    async def get_user_account(self, *, tenant_id: int, user_id: int) -> CreditAccount | None:
        """Get user credit account (tenant-scoped)."""
        return await self.get_one(
            where=[
                CreditAccount.tenant_id == tenant_id,
                CreditAccount.account_type == CreditAccountType.USER.value,
                CreditAccount.user_id == user_id,
            ]
        )

    async def init_tenant_account(self, tenant_id: int, operator_id: int | None = None) -> CreditAccount:
        """
        Initialize tenant credit account (idempotent)

        Uses DB-level uniqueness (partial index) to avoid duplicates under concurrency.
        """
        existing = await self.get_tenant_account(tenant_id)
        if existing:
            return existing

        try:
            account = await self.create(
                {
                    "tenant_id": tenant_id,
                    "user_id": None,
                    "account_type": CreditAccountType.TENANT.value,
                    "balance": Decimal("0"),
                    "total_earned": Decimal("0"),
                    "total_spent": Decimal("0"),
                    "status": CreditAccountStatus.ACTIVE.value,
                    "extra": {},
                }
            )
        except IntegrityError:
            # concurrent init: fetch again
            await self.db.rollback()
            account = await self.get_tenant_account(tenant_id)
            if not account:
                raise
        logger.info("credit_tenant_account_initialized", tenant_id=tenant_id, operator_id=operator_id, account_id=account.id)
        return account

    async def init_user_account(self, *, tenant_id: int, user_id: int, operator_id: int | None = None) -> CreditAccount:
        """
        Initialize user credit account (idempotent)

        Uses DB-level uniqueness (partial index) to avoid duplicates under concurrency.
        """
        existing = await self.get_user_account(tenant_id=tenant_id, user_id=user_id)
        if existing:
            return existing

        try:
            account = await self.create(
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "account_type": CreditAccountType.USER.value,
                    "balance": Decimal("0"),
                    "total_earned": Decimal("0"),
                    "total_spent": Decimal("0"),
                    "status": CreditAccountStatus.ACTIVE.value,
                    "extra": {},
                }
            )
        except IntegrityError:
            await self.db.rollback()
            account = await self.get_user_account(tenant_id=tenant_id, user_id=user_id)
            if not account:
                raise

        logger.info(
            "credit_user_account_initialized",
            tenant_id=tenant_id,
            user_id=user_id,
            operator_id=operator_id,
            account_id=account.id,
        )
        return account

    async def list_accounts(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 10,
        account_type: str | None = None,
        status: str | None = None,
        user_id: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[CreditAccount], int]:
        """List credit accounts (tenant-scoped, paginated)"""
        where = [CreditAccount.tenant_id == tenant_id]
        if account_type:
            where.append(CreditAccount.account_type == account_type)
        if status:
            where.append(CreditAccount.status == status)
        if user_id is not None:
            where.append(CreditAccount.user_id == user_id)

        # 排序处理
        allowed_sort_fields = {"id", "balance", "created_at"}
        order_field = sort_by if sort_by in allowed_sort_fields else "id"
        order_desc = sort_order and sort_order.lower() == "desc"

        accounts, total = await self.get_list(
            page=page,
            page_size=page_size,
            where=where,
            return_total=True,
            order_by=order_field,
            order_desc=order_desc,
        )
        await self.enrich_accounts(tenant_id=tenant_id, accounts=accounts)
        return accounts, total

    async def update_account_status(
        self,
        account_id: int,
        tenant_id: int,
        status: str,
        *,
        operator_id: int | None = None,
    ) -> CreditAccount:
        """Freeze/unfreeze credit account"""
        account = await self.get_account_by_id(account_id, tenant_id)
        if not account:
            raise NotFoundError(message="积分账户不存在")
        await self.update(account, {"status": status}, exclude_unset=False)
        logger.info(
            "credit_account_status_updated",
            tenant_id=tenant_id,
            account_id=account_id,
            status=status,
            operator_id=operator_id,
        )
        return account

    # ==================== Transactions ====================

    async def get_transaction_by_id(self, tx_id: int, tenant_id: int) -> CreditTransaction | None:
        """Get credit transaction by ID (tenant-scoped)"""
        tx_repo = RepositoryBase(self.db, CreditTransaction)
        try:
            tx = await tx_repo.get_one(where=[CreditTransaction.id == tx_id, CreditTransaction.tenant_id == tenant_id])
            if tx:
                await self.enrich_transactions(tenant_id=tenant_id, transactions=[tx])
            return tx
        except Exception as exc:
            raise_if_credits_schema_not_upgraded(exc)
            raise

    async def get_transaction_by_idempotency_key(
        self,
        *,
        tenant_id: int,
        idempotency_key: str,
    ) -> CreditTransaction | None:
        """Get credit transaction by idempotency key (tenant-scoped)."""
        if not str(idempotency_key or "").strip():
            return None
        tx_repo = RepositoryBase(self.db, CreditTransaction)
        try:
            return await tx_repo.get_one(
                where=[
                    CreditTransaction.tenant_id == tenant_id,
                    CreditTransaction.idempotency_key == str(idempotency_key).strip(),
                ]
            )
        except Exception as exc:
            raise_if_credits_schema_not_upgraded(exc)
            raise

    async def list_transactions(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 10,
        account_id: int | None = None,
        account_user_id: int | None = None,
        transaction_type: str | None = None,
        direction: str | None = None,
        created_between: tuple[Any, Any] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[CreditTransaction], int]:
        """List transactions (tenant-scoped, paginated)"""
        tx_repo = RepositoryBase(self.db, CreditTransaction)
        where = [CreditTransaction.tenant_id == tenant_id]
        if account_id is not None:
            where.append(CreditTransaction.account_id == account_id)
        if account_user_id is not None:
            where.append(
                CreditTransaction.account_id.in_(
                    select(CreditAccount.id).where(
                        CreditAccount.tenant_id == tenant_id,
                        CreditAccount.account_type == CreditAccountType.USER.value,
                        CreditAccount.user_id == account_user_id,
                        CreditAccount.deleted_at.is_(None),
                    )
                )
            )
        if transaction_type:
            where.append(CreditTransaction.transaction_type == transaction_type)
        if direction:
            where.append(CreditTransaction.direction == direction)
        if created_between:
            start_at, end_at = created_between
            if start_at:
                where.append(CreditTransaction.created_at >= start_at)
            if end_at:
                where.append(CreditTransaction.created_at <= end_at)

        # 排序处理：默认按最新流水优先，便于个人中心与后台列表直接看到最近扣费。
        allowed_sort_fields = {"id", "amount", "created_at"}
        order_field = sort_by if sort_by in allowed_sort_fields else "created_at"
        order_desc = True if not sort_order else sort_order.lower() == "desc"

        try:
            transactions, total = await tx_repo.get_list(
                page=page,
                page_size=page_size,
                where=where,
                order_by=order_field,
                order_desc=order_desc,
                return_total=True,
            )
            await self.enrich_transactions(tenant_id=tenant_id, transactions=transactions)
            return transactions, total
        except Exception as exc:
            raise_if_credits_schema_not_upgraded(exc)
            raise

    # ==================== Credit Operations ====================

    @staticmethod
    def _normalize_amount(amount: Decimal | int | str) -> Decimal:
        try:
            value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        except (InvalidOperation, TypeError) as exc:
            raise BusinessError(message="无效的积分金额") from exc
        if value <= 0:
            raise BusinessError(message="积分金额必须为正数")
        return value

    async def _get_account_for_update(self, account_id: int, tenant_id: int) -> CreditAccount:
        stmt = (
            select(CreditAccount)
            .where(CreditAccount.id == account_id, CreditAccount.tenant_id == tenant_id, CreditAccount.deleted_at.is_(None))
            .with_for_update()
            # 行锁拿到后必须用数据库里的最新值覆盖会话身份映射里的旧对象：同一会话此前
            # 已加载过该账户时，不加 populate_existing 会拿到锁前快照 → 并发扣费丢失更新
            # （2026-08-26 aippt 三并发预扣实测：三笔 balance_before 相同，余额只减了一笔）
            .execution_options(populate_existing=True)
        )
        await escalate_to_write_lock(self.db)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError(message="积分账户不存在")
        return account

    @staticmethod
    def _assert_account_active(account: CreditAccount) -> None:
        if account.status != CreditAccountStatus.ACTIVE.value:
            raise BusinessError(message="积分账户已冻结，无法操作", code="CREDIT_ACCOUNT_FROZEN")

    async def _apply_transaction(
        self,
        *,
        account: CreditAccount,
        amount: Decimal,
        transaction_type: str,
        direction: str,
        reference_type: str | None,
        reference_id: int | None,
        idempotency_key: str | None,
        remark: str | None,
        operator_id: int | None,
        extra: dict[str, Any] | None = None,
    ) -> CreditTransaction:
        self._assert_account_active(account)

        before = account.balance or Decimal("0")
        if direction == CreditTransactionDirection.IN.value:
            after = before + amount
            account.balance = after
            account.total_earned = (account.total_earned or Decimal("0")) + amount
        elif direction == CreditTransactionDirection.OUT.value:
            after = before - amount
            if after < 0:
                raise BusinessError(message="积分余额不足", code="INSUFFICIENT_CREDITS")
            account.balance = after
            account.total_spent = (account.total_spent or Decimal("0")) + amount
        else:
            raise BusinessError(message="无效的积分方向")

        tx = CreditTransaction(
            tenant_id=account.tenant_id,
            account_id=account.id,
            transaction_type=transaction_type,
            amount=amount,
            direction=direction,
            balance_before=before,
            balance_after=after,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            remark=remark,
            operator_id=operator_id,
            extra=extra or {},
        )
        self.db.add(tx)
        try:
            await self.db.flush()
            await self.db.refresh(tx)
            await self.db.refresh(account)
        except Exception as exc:
            raise_if_credits_schema_not_upgraded(exc)
            raise
        return tx

    async def recharge(
        self,
        *,
        tenant_id: int,
        account_id: int,
        amount: Decimal,
        operator_id: int | None,
        remark: str | None = None,
        reference_type: str | None = None,
        reference_id: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> CreditTransaction:
        """Admin recharge (in)"""
        normalized = self._normalize_amount(amount)
        account = await self._get_account_for_update(account_id, tenant_id)
        tx = await self._apply_transaction(
            account=account,
            amount=normalized,
            transaction_type=CreditTransactionType.RECHARGE.value,
            direction=CreditTransactionDirection.IN.value,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=None,
            remark=remark,
            operator_id=operator_id,
            extra=extra,
        )
        logger.info(
            "credit_recharged",
            tenant_id=tenant_id,
            account_id=account_id,
            amount=str(normalized),
            operator_id=operator_id,
            tx_id=tx.id,
        )
        return tx

    async def bonus(
        self,
        *,
        tenant_id: int,
        account_id: int,
        amount: Decimal,
        operator_id: int | None,
        remark: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> CreditTransaction:
        """Bonus (in)"""
        normalized = self._normalize_amount(amount)
        account = await self._get_account_for_update(account_id, tenant_id)
        tx = await self._apply_transaction(
            account=account,
            amount=normalized,
            transaction_type=CreditTransactionType.BONUS.value,
            direction=CreditTransactionDirection.IN.value,
            reference_type=None,
            reference_id=None,
            idempotency_key=None,
            remark=remark,
            operator_id=operator_id,
            extra=extra,
        )
        logger.info(
            "credit_bonus_granted",
            tenant_id=tenant_id,
            account_id=account_id,
            amount=str(normalized),
            operator_id=operator_id,
            tx_id=tx.id,
        )
        return tx

    async def consume(
        self,
        *,
        tenant_id: int,
        account_id: int,
        amount: Decimal,
        reference_type: str,
        reference_id: int | None = None,
        idempotency_key: str | None = None,
        remark: str | None = None,
        operator_id: int | None = None,
        extra: dict[str, Any] | None = None,
        capture_usage: bool = True,
    ) -> CreditTransaction:
        """Consume credits (out) - for other modules

        ``capture_usage=False``：本笔流水不再抢占根动作的用量快照（补扣 / 分阶段扣费等
        由上层自行决定谁携带 usage 时使用），避免同一根动作的快照被第二笔流水消费掉。
        """
        # SQLite：整笔扣费是"读幂等键→锁账户→写"，必须在第一条读之前进入写事务（PG no-op）
        await escalate_to_write_lock(self.db)
        usage_collector = current_usage_collector() if capture_usage else None
        usage_snapshot = usage_snapshot_for_extra(root_only=True, once=True) if capture_usage else None
        if usage_snapshot is not None:
            # 计量层：只有业务根动作、且每个根动作只一次，把按模型/按阶段的真实用量随流水
            # 落账（先记账不计价）。子阶段收集器与同一根动作内的后续流水不重复携带。
            extra = {**(extra or {}), "usage": usage_snapshot}
        normalized = self._normalize_amount(amount)
        if not reference_type:
            raise BusinessError(message="reference_type 不能为空")
        normalized_idempotency_key = str(idempotency_key or "").strip() or None
        if normalized_idempotency_key:
            existing = await self.get_transaction_by_idempotency_key(
                tenant_id=tenant_id,
                idempotency_key=normalized_idempotency_key,
            )
            if existing:
                self._ensure_existing_consume_matches(
                    tx=existing,
                    account_id=account_id,
                    amount=normalized,
                    reference_type=reference_type,
                    reference_id=reference_id,
                )
                return existing
        account = await self._get_account_for_update(account_id, tenant_id)
        if normalized_idempotency_key:
            existing = await self.get_transaction_by_idempotency_key(
                tenant_id=tenant_id,
                idempotency_key=normalized_idempotency_key,
            )
            if existing:
                self._ensure_existing_consume_matches(
                    tx=existing,
                    account_id=account_id,
                    amount=normalized,
                    reference_type=reference_type,
                    reference_id=reference_id,
                )
                return existing
        tx = await self._apply_transaction(
            account=account,
            amount=normalized,
            transaction_type=CreditTransactionType.CONSUME.value,
            direction=CreditTransactionDirection.OUT.value,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=normalized_idempotency_key,
            remark=remark,
            operator_id=operator_id,
            extra=extra,
        )
        logger.info(
            "credit_consumed",
            tenant_id=tenant_id,
            account_id=account_id,
            amount=str(normalized),
            reference_type=reference_type,
            reference_id=reference_id,
            operator_id=operator_id,
            tx_id=tx.id,
        )
        if usage_collector is not None:
            # 一段用量只归一笔流水：本收集器（含冒泡上来的子级事件）标为已由本笔结算
            usage_collector.mark_settled(int(tx.id))
        return tx

    async def refund(
        self,
        *,
        tenant_id: int,
        transaction_id: int,
        amount: Decimal,
        idempotency_key: str | None = None,
        remark: str | None = None,
        operator_id: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> CreditTransaction:
        """Refund credits for a previous out transaction (in)"""
        normalized = self._normalize_amount(amount)

        original = await self.get_transaction_by_id(transaction_id, tenant_id)
        if not original:
            raise NotFoundError(message="原交易不存在")
        if original.direction != CreditTransactionDirection.OUT.value:
            raise BusinessError(message="仅支持对扣减类型交易退款")
        normalized_idempotency_key = str(idempotency_key or "").strip() or None
        if normalized_idempotency_key:
            existing = await self.get_transaction_by_idempotency_key(
                tenant_id=tenant_id,
                idempotency_key=normalized_idempotency_key,
            )
            if existing:
                self._ensure_existing_refund_matches(tx=existing, original=original, amount=normalized)
                return existing

        # 统计已退款金额：credit_transactions.extra.original_transaction_id == transaction_id
        stmt = select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
            CreditTransaction.tenant_id == tenant_id,
            CreditTransaction.transaction_type == CreditTransactionType.REFUND.value,
            CreditTransaction.deleted_at.is_(None),
            CreditTransaction.extra["original_transaction_id"].as_integer() == int(transaction_id),  # SQLite JSON_EXTRACT 数字返回整数
        )
        result = await self.db.execute(stmt)
        refunded_total = result.scalar() or Decimal("0")

        refundable = (original.amount or Decimal("0")) - Decimal(str(refunded_total))
        if normalized > refundable:
            raise BusinessError(message="退款金额超过可退款余额")

        account = await self._get_account_for_update(original.account_id, tenant_id)
        if normalized_idempotency_key:
            existing = await self.get_transaction_by_idempotency_key(
                tenant_id=tenant_id,
                idempotency_key=normalized_idempotency_key,
            )
            if existing:
                self._ensure_existing_refund_matches(tx=existing, original=original, amount=normalized)
                return existing
        merged_extra = {"original_transaction_id": original.id}
        if extra:
            merged_extra.update(extra)

        tx = await self._apply_transaction(
            account=account,
            amount=normalized,
            transaction_type=CreditTransactionType.REFUND.value,
            direction=CreditTransactionDirection.IN.value,
            reference_type=original.reference_type,
            reference_id=original.reference_id,
            idempotency_key=normalized_idempotency_key,
            remark=remark,
            operator_id=operator_id,
            extra=merged_extra,
        )
        logger.info(
            "credit_refunded",
            tenant_id=tenant_id,
            account_id=account.id,
            original_tx_id=original.id,
            amount=str(normalized),
            operator_id=operator_id,
            tx_id=tx.id,
        )
        return tx

    @staticmethod
    def _ensure_existing_consume_matches(
        *,
        tx: CreditTransaction,
        account_id: int,
        amount: Decimal,
        reference_type: str,
        reference_id: int | None,
    ) -> None:
        if tx.transaction_type != CreditTransactionType.CONSUME.value or tx.direction != CreditTransactionDirection.OUT.value:
            raise BusinessError(message="积分幂等键已被非扣费交易占用")
        if int(tx.account_id) != int(account_id):
            raise BusinessError(message="积分幂等键已绑定到其他账户")
        if Decimal(str(tx.amount or "0")) != amount:
            raise BusinessError(message="积分幂等键重复使用时金额不一致")
        if str(tx.reference_type or "") != str(reference_type or ""):
            raise BusinessError(message="积分幂等键重复使用时业务类型不一致")
        current_reference_id = int(tx.reference_id) if tx.reference_id is not None else None
        if current_reference_id != reference_id:
            raise BusinessError(message="积分幂等键重复使用时业务ID不一致")

    @staticmethod
    def _ensure_existing_refund_matches(
        *,
        tx: CreditTransaction,
        original: CreditTransaction,
        amount: Decimal,
    ) -> None:
        if tx.transaction_type != CreditTransactionType.REFUND.value or tx.direction != CreditTransactionDirection.IN.value:
            raise BusinessError(message="积分退款幂等键已被非退款交易占用")
        if Decimal(str(tx.amount or "0")) != amount:
            raise BusinessError(message="积分退款幂等键重复使用时金额不一致")
        if str(tx.reference_type or "") != str(original.reference_type or ""):
            raise BusinessError(message="积分退款幂等键重复使用时业务类型不一致")
        current_reference_id = int(tx.reference_id) if tx.reference_id is not None else None
        original_reference_id = int(original.reference_id) if original.reference_id is not None else None
        if current_reference_id != original_reference_id:
            raise BusinessError(message="积分退款幂等键重复使用时业务ID不一致")
        if int(dict(tx.extra or {}).get("original_transaction_id") or 0) != int(original.id):
            raise BusinessError(message="积分退款幂等键重复使用时原交易不一致")

    # ==================== Response Converters ====================

    @staticmethod
    def _decimal_str(value: Decimal | None) -> str:
        """Convert Decimal to JSON-safe string."""
        return str(value if value is not None else Decimal("0"))

    @staticmethod
    def to_account_response(account: CreditAccount) -> dict[str, Any]:
        """Convert CreditAccount to camelCase response dict (ORJSON-safe)."""
        return {
            "id": account.id,
            "tenantId": account.tenant_id,
            "userId": account.user_id,
            "accountType": account.account_type,
            "balance": CreditService._decimal_str(account.balance),
            "totalEarned": CreditService._decimal_str(account.total_earned),
            "totalSpent": CreditService._decimal_str(account.total_spent),
            "status": account.status,
            "extra": account.extra or {},
            "username": getattr(account, "username", None),
            "nickname": getattr(account, "nickname", None),
            "displayName": getattr(account, "display_name", None),
            "email": getattr(account, "email", None),
            "phone": getattr(account, "phone", None),
            "teamNames": getattr(account, "team_names", []),
            "createdAt": account.created_at.isoformat() if getattr(account, "created_at", None) else None,
            "updatedAt": account.updated_at.isoformat() if getattr(account, "updated_at", None) else None,
        }

    @staticmethod
    def to_transaction_response(tx: CreditTransaction) -> dict[str, Any]:
        """Convert CreditTransaction to camelCase response dict (ORJSON-safe)."""
        return {
            "id": tx.id,
            "tenantId": tx.tenant_id,
            "accountId": tx.account_id,
            "transactionType": tx.transaction_type,
            "amount": CreditService._decimal_str(tx.amount),
            "direction": tx.direction,
            "balanceBefore": CreditService._decimal_str(tx.balance_before),
            "balanceAfter": CreditService._decimal_str(tx.balance_after),
            "referenceType": tx.reference_type,
            "referenceId": tx.reference_id,
            "remark": tx.remark,
            "operatorId": tx.operator_id,
            "extra": tx.extra or {},
            "accountType": getattr(tx, "account_type", None),
            "accountUserId": getattr(tx, "account_user_id", None),
            "accountUsername": getattr(tx, "account_username", None),
            "accountNickname": getattr(tx, "account_nickname", None),
            "accountDisplayName": getattr(tx, "account_display_name", None),
            "operatorUsername": getattr(tx, "operator_username", None),
            "operatorNickname": getattr(tx, "operator_nickname", None),
            "operatorDisplayName": getattr(tx, "operator_display_name", None),
            "createdAt": tx.created_at.isoformat() if getattr(tx, "created_at", None) else None,
        }
