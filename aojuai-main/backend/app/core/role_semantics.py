from __future__ import annotations

TENANT_ADMIN_ROLE_CODES: tuple[str, ...] = ("tenant_admin", "admin")


def is_tenant_admin_role_code(role_code: str | None) -> bool:
    return str(role_code or "").strip().lower() in TENANT_ADMIN_ROLE_CODES


def has_tenant_admin_role(role_codes: list[str] | tuple[str, ...] | set[str] | None) -> bool:
    return any(is_tenant_admin_role_code(role_code) for role_code in (role_codes or ()))
