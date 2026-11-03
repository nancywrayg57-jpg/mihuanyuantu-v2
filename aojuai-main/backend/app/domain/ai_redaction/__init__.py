"""租户级 AI 出站脱敏策略（版本化、只追加、按 scope 区分）。

引擎在 `app.core.redaction`（业务无关）；这里只管"策略存哪、谁签字、哪版生效"。
业务模块通过 `load_policy(db, tenant_id, scope="<module>", default=<模块默认>)` 取策略：
模块 scope 有就用模块的；没有就用租户通用 scope `*`（实体/白名单/守卫等租户级口径）叠上模块默认的字段级规则；都没有用模块默认。
"""

from app.domain.ai_redaction.models import SHARED_SCOPE, TenantRedactionPolicy
from app.domain.ai_redaction.service import (
    default_shared_policy,
    get_active_policy_row,
    list_policy_versions,
    list_scopes,
    load_policy,
    normalize_scope,
    save_policy,
)

__all__ = [
    "SHARED_SCOPE",
    "TenantRedactionPolicy",
    "default_shared_policy",
    "get_active_policy_row",
    "list_policy_versions",
    "list_scopes",
    "load_policy",
    "normalize_scope",
    "save_policy",
]
