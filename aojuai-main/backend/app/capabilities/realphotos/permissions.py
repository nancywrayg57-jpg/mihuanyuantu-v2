"""Permission codes for realphotos (S0 subset)."""

WORKSPACE_READ = "realphotos:workspace:read"
WALLET_READ = "realphotos:wallet:read"
WALLET_ADJUST = "realphotos:wallet:adjust"
GATEWAY_READ = "realphotos:gateway:read"
JOBS_READ = "realphotos:jobs:read"
JOBS_ENQUEUE = "realphotos:jobs:enqueue"
ORDER_SUPPORT_READ = "realphotos:order_support:read"
ADMIN_READ = "realphotos:admin:read"
TECH_DESK_READ = "realphotos:tech_desk:read"

ALL_PERMISSIONS = (
    WORKSPACE_READ,
    WALLET_READ,
    WALLET_ADJUST,
    GATEWAY_READ,
    JOBS_READ,
    JOBS_ENQUEUE,
    ORDER_SUPPORT_READ,
    ADMIN_READ,
    TECH_DESK_READ,
)

# 岗位角色码（与 access / bootstrap 对齐）
ROLE_MERCHANT = "rp_merchant"
ROLE_ORDER_SUPPORT = "rp_order_support"
ROLE_ADMIN = "rp_admin"
ROLE_TECH_SUPPORT = "rp_tech_support"  # S6 完整台；S0 仅登记码

__all__ = [
    "ADMIN_READ",
    "ALL_PERMISSIONS",
    "GATEWAY_READ",
    "JOBS_ENQUEUE",
    "JOBS_READ",
    "ORDER_SUPPORT_READ",
    "ROLE_ADMIN",
    "ROLE_MERCHANT",
    "ROLE_ORDER_SUPPORT",
    "ROLE_TECH_SUPPORT",
    "TECH_DESK_READ",
    "WALLET_ADJUST",
    "WALLET_READ",
    "WORKSPACE_READ",
]
