"""AOJU Backend - Domain Package

Import all models here to ensure SQLAlchemy can resolve relationships correctly.

分两段：
- **内核域**照旧静态 import。它们不可卸载，写死最清楚。
- **可硬卸载的内置能力**（assistant / speech / cms）改为按代码存在与否动态注册。
  这个文件原来是硬卸载的最后一道坎：删掉 app/domain/speech/ 之后，任何
  `import app.domain` 都会 ModuleNotFoundError，整个应用起不来——
  "不安装就不加载"到这一层就断了。

注意判定用的是**代码在不在**，不是 `AOJ_ENABLED_MODULES`：
同一份 checkout 的 SQLAlchemy 元数据必须稳定，否则同一次 alembic autogenerate
会随环境变量给出不同结果。部署级开关只决定路由挂不挂载。
"""

# Import all models to register them with SQLAlchemy
from app.core.module_manifest import import_present_model_modules
from app.domain.ai_redaction.models import TenantRedactionPolicy
from app.domain.auth.api_key_models import ApiKey
from app.domain.auth.models import Tenant
from app.domain.organizations.models import Organization
from app.domain.users.models import User, UserRole
from app.domain.roles.models import Role, RoleMenu, RoleTeam
from app.domain.menus.models import Menu
from app.domain.user_groups.models import UserGroup, UserGroupMember
from app.domain.teams.models import Team
from app.domain.credits.models import CreditAccount, CreditPriceItem, CreditRule, CreditTransaction
from app.domain.invitations.models import InviteCode, InviteRegistration
from app.domain.operation_logs.models import OperationLog
from app.domain.notifications.models import Notification
from app.domain.verification.models import VerificationCode

# 可硬卸载的内置能力：清单在 app/core/module_manifest.py，删目录即卸载。
REGISTERED_MODULE_MODELS: tuple[str, ...] = import_present_model_modules()

__all__ = [
    "ApiKey",
    "TenantRedactionPolicy",
    "Tenant",
    "Organization",
    "User",
    "UserRole",
    "Role",
    "RoleMenu",
    "RoleTeam",
    "Menu",
    "UserGroup",
    "UserGroupMember",
    "Team",
    "CreditAccount",
    "CreditTransaction",
    "CreditPriceItem",
    "CreditRule",
    "InviteCode",
    "InviteRegistration",
    "OperationLog",
    "Notification",
    "VerificationCode",
    "REGISTERED_MODULE_MODELS",
]
