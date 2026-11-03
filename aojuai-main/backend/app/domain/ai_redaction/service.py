from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError
from app.core.redaction import RedactionPolicy
from app.domain.ai_redaction.models import SHARED_SCOPE, TenantRedactionPolicy

_SCOPE_RE = re.compile(r"^(\*|[a-z][a-z0-9_]{0,63})$")


def normalize_scope(scope: str | None) -> str:
    value = (scope or SHARED_SCOPE).strip()
    if not _SCOPE_RE.fullmatch(value):
        raise BusinessError(message=f"非法的策略 scope: {scope!r}（通用用 *，模块用小写模块码）")
    return value


def default_shared_policy() -> RedactionPolicy:
    """租户通用默认：不放行任何字段（`rule_for` 缺省 BLOCK），只定实体/守卫口径。模块默认由各模块自己给。"""
    payload = RedactionPolicy.preset("standard").to_json()
    payload["note"] = "内置通用默认策略，尚未经业务方签字确认"
    return RedactionPolicy.from_json(payload, version=0)


async def _active_row(db: AsyncSession, *, tenant_id: int, scope: str) -> TenantRedactionPolicy | None:
    return await db.scalar(
        select(TenantRedactionPolicy)
        .where(
            TenantRedactionPolicy.tenant_id == tenant_id,
            TenantRedactionPolicy.scope == scope,
            TenantRedactionPolicy.is_active.is_(True),
            TenantRedactionPolicy.deleted_at.is_(None),
        )
        .order_by(TenantRedactionPolicy.version.desc())
        .limit(1)
    )


async def get_active_policy_row(
    db: AsyncSession, *, tenant_id: int, scope: str = SHARED_SCOPE
) -> TenantRedactionPolicy | None:
    """返回某 scope 显式保存的 active 行；不做通用/模块默认回退。"""
    return await _active_row(db, tenant_id=tenant_id, scope=normalize_scope(scope))


async def load_policy(
    db: AsyncSession,
    *,
    tenant_id: int,
    scope: str = SHARED_SCOPE,
    default: RedactionPolicy | None = None,
) -> RedactionPolicy:
    """取某模块生效的策略。

    优先级：模块 scope 的 active 版本 → 租户通用 `*`（叠上模块默认的字段级规则）→ 模块默认 → 内置通用默认。
    通用策略里不含字段级放行是刻意的：哪些字段能出去只有模块自己知道。
    """
    scope = normalize_scope(scope)
    fallback = default or default_shared_policy()
    row = await _active_row(db, tenant_id=tenant_id, scope=scope)
    if row is not None:
        return RedactionPolicy.from_json(dict(row.rules or {}), version=row.version)
    if scope != SHARED_SCOPE:
        shared = await _active_row(db, tenant_id=tenant_id, scope=SHARED_SCOPE)
        if shared is not None:
            merged = dict(shared.rules or {})
            if not merged.get("fieldRules") and fallback.field_rules:
                merged["fieldRules"] = fallback.to_json().get("fieldRules", {})
            return RedactionPolicy.from_json(merged, version=shared.version)
    return fallback


async def save_policy(
    db: AsyncSession,
    *,
    tenant_id: int,
    scope: str,
    rules: dict[str, Any],
    approved_by: str,
    note: str = "",
) -> TenantRedactionPolicy:
    """新增一个版本并置为 active。**旧版本保留**。认不出的动作在 `from_json` 里降级成 BLOCK，不会因拼错而放行。"""
    scope = normalize_scope(scope)
    approved_by = (approved_by or "").strip()
    if not approved_by:
        raise BusinessError(message="策略必须有签字人（approvedBy）")
    incoming = dict(rules or {})
    if str(incoming.get("level") or "custom") == "custom" and not incoming.get("baseLevel"):
        incoming["level"] = "custom"
        incoming["baseLevel"] = "standard"
    normalized = RedactionPolicy.from_json(incoming).to_json()
    if normalized["level"] == "off" and scope != SHARED_SCOPE:
        raise BusinessError(message="off 只能在租户通用 scope（*）显式签字设置")

    current = await db.scalar(
        select(TenantRedactionPolicy)
        .where(
            TenantRedactionPolicy.tenant_id == tenant_id,
            TenantRedactionPolicy.scope == scope,
            TenantRedactionPolicy.deleted_at.is_(None),
        )
        .order_by(TenantRedactionPolicy.version.desc())
        .limit(1)
    )
    for row in (
        await db.scalars(
            select(TenantRedactionPolicy).where(
                TenantRedactionPolicy.tenant_id == tenant_id,
                TenantRedactionPolicy.scope == scope,
                TenantRedactionPolicy.is_active.is_(True),
                TenantRedactionPolicy.deleted_at.is_(None),
            )
        )
    ).all():
        row.is_active = False
    normalized["approvedBy"] = approved_by
    normalized["approvedAt"] = datetime.now(UTC).isoformat()
    normalized["note"] = note or ""
    row = TenantRedactionPolicy(
        tenant_id=tenant_id,
        scope=scope,
        version=(current.version + 1) if current else 1,
        rules=normalized,
        approved_by=approved_by,
        note=note or None,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def list_policy_versions(
    db: AsyncSession, *, tenant_id: int, scope: str = SHARED_SCOPE, limit: int = 20
) -> list[TenantRedactionPolicy]:
    scope = normalize_scope(scope)
    rows = await db.scalars(
        select(TenantRedactionPolicy)
        .where(
            TenantRedactionPolicy.tenant_id == tenant_id,
            TenantRedactionPolicy.scope == scope,
            TenantRedactionPolicy.deleted_at.is_(None),
        )
        .order_by(TenantRedactionPolicy.version.desc())
        .limit(max(1, min(limit, 100)))
    )
    return list(rows.all())


async def list_scopes(db: AsyncSession, *, tenant_id: int) -> list[str]:
    rows = await db.scalars(
        select(TenantRedactionPolicy.scope)
        .where(
            TenantRedactionPolicy.tenant_id == tenant_id,
            TenantRedactionPolicy.deleted_at.is_(None),
        )
        .distinct()
    )
    return sorted(set(rows.all()) | {SHARED_SCOPE})
