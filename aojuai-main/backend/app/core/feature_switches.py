"""
AOJU Backend - Tenant Feature Switches

Centralized feature/module switch helpers for plugin-style rollout.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from app.core.capability_registry import discover_capabilities
from app.core.config import settings
from app.core.module_manifest import module_code_is_present
from app.infrastructure.database.dialect import get_dialect


@dataclass(frozen=True)
class ModuleCatalogItem:
    code: str
    label: str
    description: str
    # 前端展示用的 i18n key。label/description 保留中文**服务端显示名**——
    # 助手会把它拼进给用户看的自然语言（"正在打开语音能力"），那里不能出现 key。
    label_key: str = ""
    description_key: str = ""
    layer: Literal["kernel", "capability", "pack", "sample"] = "capability"
    default_enabled: bool = True
    always_installed: bool = False
    aliases: tuple[str, ...] = ()
    route_prefixes: tuple[str, ...] = ()
    api_prefixes: tuple[str, ...] = ()
    permission_prefixes: tuple[str, ...] = ()
    #: 依赖 PostgreSQL 专有能力的模块：SQLite 轻量档下视为未安装（目录/路由/菜单一起消失，见 core/dialect_features.py）
    requires_postgresql: bool = False


@dataclass(frozen=True)
class CapabilityCatalogItem:
    code: str
    label: str
    description: str
    label_key: str = ""
    description_key: str = ""
    default_enabled: bool = True


_BUILTIN_MODULE_CATALOG: tuple[ModuleCatalogItem, ...] = (
    ModuleCatalogItem(
        code="assistant",
        label="AI 助手",
        description="租户级 AI 助手配置基座，提供统一的模型、密钥与提示词基线",
        label_key="system.moduleCatalog.assistant.label",
        description_key="system.moduleCatalog.assistant.description",
        layer="capability",
        # assistant 是 AI 基座（cms_ai、tenant_profile 的模型配置都建在它上面），
        # always_installed 只保证"装着就常驻"；硬卸载（删代码）仍然让它整条消失。
        always_installed=True,
        aliases=("ai_assistant", "ai-assistant"),
        route_prefixes=("/assistant",),
        api_prefixes=("/api/v1/assistant", "/api/v1/ai-config"),
        permission_prefixes=("assistant",),
    ),
    ModuleCatalogItem(
        code="speech",
        label="语音能力",
        description="基础语音能力，规范入口统一收口到租户设置的语音 tab",
        label_key="system.moduleCatalog.speech.label",
        description_key="system.moduleCatalog.speech.description",
        layer="capability",
        # 不再 always_installed：语音是可动态装卸的能力。
        # default_enabled 保持 True——装上之后租户默认可用，符合"底座能力"的语义；
        # 不想要就在部署侧不装（AOJ_ENABLED_MODULES 不列它）。
        always_installed=False,
        route_prefixes=("/speech", "/system/speech-settings"),
        api_prefixes=("/api/v1/speech",),
        permission_prefixes=("speech",),
    ),
    # CMS / public marketing site. DEFAULT-OFF, opt-in capability — not bundled
    # as an always-on base feature. Downstream branches (e.g. logistics) enable it.
    ModuleCatalogItem(
        code="public_site",
        label="公开站 / CMS",
        description="可选的公开营销站点与内容管理（页面/文章/导航/语言/留言）。默认关闭；启用后接管公开首页。",
        label_key="system.moduleCatalog.publicSite.label",
        description_key="system.moduleCatalog.publicSite.description",
        layer="capability",
        default_enabled=False,
        always_installed=False,
        aliases=("cms", "site_cms"),
        route_prefixes=("/cms",),
        api_prefixes=("/api/v1/cms", "/api/v1/site/cms"),
        permission_prefixes=("cms",),
    ),
)


# 硬安装过滤：代码被物理删除的内置模块，整条从目录里消失——没有开关项、
# 没有路由/权限前缀映射、菜单也筛不出来。物理边界的声明在 module_manifest，
# 那里是叶子模块，app/domain 与 alembic/env 也要用（见该文件顶部注释）。
MODULE_CATALOG: tuple[ModuleCatalogItem, ...] = tuple(
    item for item in _BUILTIN_MODULE_CATALOG if module_code_is_present(item.code)
) + tuple(
    ModuleCatalogItem(
        code=definition.code,
        label=definition.label,
        description=definition.description,
        label_key=definition.label_key,
        description_key=definition.description_key,
        layer=definition.layer,
        default_enabled=definition.default_enabled,
        route_prefixes=definition.route_prefixes,
        api_prefixes=(f"/api/v1{definition.api_prefix}",),
        permission_prefixes=definition.permission_prefixes,
    )
    for definition in discover_capabilities()
    if not (settings.ENV == "production" and definition.production_blocked)
)


CAPABILITY_CATALOG: tuple[CapabilityCatalogItem, ...] = (
    CapabilityCatalogItem(
        code="verification_sms",
        label="手机号验证码",
        description="登录后绑定手机号验证码发送",
        label_key="system.capabilityCatalog.verificationSms.label",
        description_key="system.capabilityCatalog.verificationSms.description",
    ),
    CapabilityCatalogItem(
        code="verification_email",
        label="邮箱验证码",
        description="登录后绑定邮箱验证码发送",
        label_key="system.capabilityCatalog.verificationEmail.label",
        description_key="system.capabilityCatalog.verificationEmail.description",
    ),
)


# 模块开关默认值（true = 默认开启）
MODULE_SWITCH_DEFAULTS: dict[str, bool] = {
    item.code: bool(item.default_enabled)
    for item in MODULE_CATALOG
}


# 细粒度能力开关默认值
CAPABILITY_SWITCH_DEFAULTS: dict[str, bool] = {
    item.code: bool(item.default_enabled)
    for item in CAPABILITY_CATALOG
}


MODULE_LABELS: dict[str, str] = {
    item.code: item.label
    for item in MODULE_CATALOG
}


def _normalize_switch_key(value: str | None) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _normalize_prefix_path(value: str | None) -> str:
    path = str(value or "").strip().lower()
    if not path:
        return ""

    if "#/" in path:
        path = "/" + path.split("#/", 1)[1].strip()
    elif "#" in path:
        path = path.split("#", 1)[0].strip()

    if "?" in path:
        path = path.split("?", 1)[0].strip()

    if not path.startswith("/"):
        path = f"/{path.lstrip('/')}"

    if len(path) > 1:
        path = path.rstrip("/")

    return path


# 历史模块标识（分支遗留）-> 统一模块编码
MODULE_SWITCH_ALIASES: dict[str, str] = {}
for item in MODULE_CATALOG:
    for alias in item.aliases:
        alias_key = _normalize_switch_key(alias)
        if alias_key:
            MODULE_SWITCH_ALIASES[alias_key] = item.code

# 组合模块标识（用于部署时快速选择模块组合）。
# 展开结果按目录过滤：代码被硬卸载的模块不会被组合标识"复活"。
_RAW_MODULE_SWITCH_EXPANSIONS: dict[str, tuple[str, ...]] = {
    # 历史部署标识兼容：nextjs-base 仅保留 assistant + speech 两层基座能力。
    "aidev": ("assistant", "speech"),
    "base": ("assistant", "speech"),
}
MODULE_SWITCH_EXPANSIONS: dict[str, tuple[str, ...]] = {
    marker: tuple(code for code in codes if code in MODULE_LABELS)
    for marker, codes in _RAW_MODULE_SWITCH_EXPANSIONS.items()
}


# 前缀映射用**未过滤**的目录，硬卸载的模块也留在里面。
#
# 这三张表的用途是"这个路径归谁管"，答案不该随模块装没装而消失。
# 用过滤后的 MODULE_CATALOG 会造成 **fail-open**：硬卸载 knowledge_base 之后，
# `/api/v1/documents/*`（它是 knowledge_base 的子域，代码在别的目录里、
# 仍然挂着 11 条路由）解析不到模块，门禁把"解析不到"当成公共/内核 API 放行——
# 能力还在，门禁没了。实测过，不是推演。
#
# 留在映射里之后：前缀仍解析到 knowledge_base，`is_module_enabled()` 查到
# 它未安装直接返回 False，请求被拒。**fail closed**。
# 模块自己的路由本来就没挂载（404），所以这一改不影响它们。
_PREFIX_CATALOG: tuple[ModuleCatalogItem, ...] = _BUILTIN_MODULE_CATALOG + tuple(
    item for item in MODULE_CATALOG if item not in _BUILTIN_MODULE_CATALOG
)


# 路由前缀 -> 模块
ROUTE_PREFIX_MODULES: tuple[tuple[str, str], ...] = tuple(
    (_normalize_prefix_path(prefix), item.code)
    for item in _PREFIX_CATALOG
    for prefix in item.route_prefixes
    if _normalize_prefix_path(prefix)
)


# API 路径前缀 -> 模块
API_PREFIX_MODULES: tuple[tuple[str, str], ...] = tuple(
    (_normalize_prefix_path(prefix), item.code)
    for item in _PREFIX_CATALOG
    for prefix in item.api_prefixes
    if _normalize_prefix_path(prefix)
)


# 权限前缀 -> 模块
PERMISSION_PREFIX_MODULES: dict[str, str] = {
    _normalize_switch_key(prefix): item.code
    for item in _PREFIX_CATALOG
    for prefix in item.permission_prefixes
    if _normalize_switch_key(prefix)
}


def list_module_catalog(*, include_uninstalled: bool = False) -> list[dict[str, Any]]:
    installed = _installed_module_codes()
    return [
        {
            "code": item.code,
            "label": item.label,
            "description": item.description,
            "labelKey": item.label_key or item.label,
            "descriptionKey": item.description_key or item.description,
            "layer": item.layer,
            "defaultEnabled": bool(item.default_enabled),
            "aliases": list(
                dict.fromkeys(_normalize_switch_key(alias) for alias in item.aliases)
            ),
            "routePrefixes": list(item.route_prefixes),
            "apiPrefixes": list(item.api_prefixes),
            "permissionPrefixes": [_normalize_switch_key(prefix) for prefix in item.permission_prefixes],
        }
        for item in MODULE_CATALOG
        if include_uninstalled or _is_catalog_item_installed(item, installed)
    ]


def build_feature_catalog_definition(*, include_uninstalled: bool = False) -> dict[str, Any]:
    """Build the stable catalog shared by the API and generated frontend fallback."""
    catalog: dict[str, Any] = {
        "modules": list_module_catalog(include_uninstalled=include_uninstalled),
        "capabilities": list_capability_catalog(),
    }
    encoded = json.dumps(
        catalog,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    from app.core.dialect_features import database_dialect, unavailable_features

    return {
        **catalog,
        "catalogDigest": hashlib.sha256(encoded).hexdigest(),
        # 方言信息不进 digest：同一份目录在 PG / SQLite 下都成立，只是部分功能入口要隐藏
        "databaseDialect": database_dialect(),
        "unavailableFeatures": unavailable_features(),
    }


def list_capability_catalog() -> list[dict[str, Any]]:
    return [
        {
            "code": item.code,
            "label": item.label,
            "description": item.description,
            "labelKey": item.label_key or item.label,
            "descriptionKey": item.description_key or item.description,
            "defaultEnabled": bool(item.default_enabled),
        }
        for item in CAPABILITY_CATALOG
    ]


def build_default_feature_switches() -> dict[str, dict[str, bool]]:
    """Build canonical default switches for tenant config/bootstrap flows."""
    return {
        "modules": dict(_available_module_defaults()),
        "capabilities": dict(CAPABILITY_SWITCH_DEFAULTS),
    }


def _read_feature_switches_raw(config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}

    feature_switches = config.get("feature_switches")
    if not isinstance(feature_switches, dict):
        feature_switches = config.get("featureSwitches")
    if not isinstance(feature_switches, dict):
        feature_switches = {}

    return feature_switches


def _canonical_module_code(module_code: str | None) -> str | None:
    value = _normalize_switch_key(module_code)
    if not value:
        return None
    if value in MODULE_SWITCH_DEFAULTS:
        return value
    return MODULE_SWITCH_ALIASES.get(value)


def canonicalize_module_code(module_code: str | None) -> str | None:
    return _canonical_module_code(module_code)


@lru_cache(maxsize=1)
def _installed_module_codes() -> set[str] | None:
    """
    Parse globally installed modules from `AOJ_ENABLED_MODULES`.

    Semantics:
    - empty / all / * => no installation filter (all available)
    - none / off / disabled / core => no optional business modules installed
    - comma-separated values => allowlist (supports aliases + legacy expansion)

    Foundation modules marked as `always_installed` stay available regardless
    of this environment variable.
    """
    raw = str(getattr(settings, "AOJ_ENABLED_MODULES", "") or "").strip()
    if not raw:
        return None

    normalized_all = _normalize_switch_key(raw)
    if normalized_all in {"all", "*"}:
        return None

    installed: set[str] = set()
    explicit_none = False
    saw_candidate = False
    for part in raw.replace(";", ",").split(","):
        token = _normalize_switch_key(part)
        if not token:
            continue
        saw_candidate = True
        if token in {"none", "off", "disabled", "core"}:
            explicit_none = True
            continue

        key = _canonical_module_code(token)
        if key:
            installed.add(key)

        expansion_keys = {token}
        if key:
            expansion_keys.add(key)
        for expansion_key in expansion_keys:
            installed.update(MODULE_SWITCH_EXPANSIONS.get(expansion_key, ()))

    if installed:
        return installed
    if explicit_none or saw_candidate:
        return set()
    return None


def clear_module_install_caches() -> None:
    _installed_module_codes.cache_clear()
    _available_module_defaults.cache_clear()


def get_installed_module_codes() -> set[str] | None:
    return _installed_module_codes()


def _is_catalog_item_installed(item: ModuleCatalogItem, installed: set[str] | None) -> bool:
    if item.requires_postgresql and get_dialect().name != "postgresql":
        return False
    if item.always_installed:
        return True
    # Samples are executable documentation and must be explicitly allowlisted;
    # the legacy empty-value meaning (all normal modules) must never publish one.
    if item.layer == "sample" and installed is None:
        return False
    return installed is None or item.code in installed


@lru_cache(maxsize=1)
def _available_module_defaults() -> dict[str, bool]:
    installed = _installed_module_codes()
    return {
        key: bool(default)
        for key, default in MODULE_SWITCH_DEFAULTS.items()
        if _is_catalog_item_installed(
            next(item for item in MODULE_CATALOG if item.code == key),
            installed,
        )
    }


def normalize_feature_switches(config: dict[str, Any] | None) -> dict[str, Any]:
    feature_switches = _read_feature_switches_raw(config)
    available_defaults = _available_module_defaults()

    modules_raw = feature_switches.get("modules")
    if not isinstance(modules_raw, dict):
        modules_raw = {}

    modules: dict[str, bool] = {}
    for raw_key, raw_value in modules_raw.items():
        key = _canonical_module_code(raw_key)
        if key is None or key not in available_defaults:
            continue
        modules[key] = bool(raw_value)

    for key, default in available_defaults.items():
        modules.setdefault(key, bool(default))

    capabilities_raw = feature_switches.get("capabilities")
    if not isinstance(capabilities_raw, dict):
        capabilities_raw = {}

    capabilities: dict[str, bool] = {}
    for key, default in CAPABILITY_SWITCH_DEFAULTS.items():
        if key in capabilities_raw:
            capabilities[key] = bool(capabilities_raw.get(key))
        else:
            capabilities[key] = bool(default)

    verification = config.get("verification") if isinstance(config, dict) else {}
    verification = verification if isinstance(verification, dict) else {}
    sms_cfg = verification.get("sms") if isinstance(verification.get("sms"), dict) else {}
    email_cfg = verification.get("email") if isinstance(verification.get("email"), dict) else {}

    if "verification_sms" not in capabilities_raw and "enabled" in sms_cfg:
        capabilities["verification_sms"] = bool(sms_cfg.get("enabled"))
    if "verification_email" not in capabilities_raw and "enabled" in email_cfg:
        capabilities["verification_email"] = bool(email_cfg.get("enabled"))

    return {
        "modules": modules,
        "capabilities": capabilities,
    }


def merge_feature_switches(
    *,
    config: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = normalize_feature_switches(config)
    available_defaults = _available_module_defaults()
    if not isinstance(incoming, dict):
        return normalized

    incoming_modules = incoming.get("modules")
    if isinstance(incoming_modules, dict):
        for raw_key, raw_value in incoming_modules.items():
            key = _canonical_module_code(raw_key)
            if key is None or key not in available_defaults:
                continue
            normalized["modules"][key] = bool(raw_value)

    incoming_capabilities = incoming.get("capabilities")
    if isinstance(incoming_capabilities, dict):
        for key in CAPABILITY_SWITCH_DEFAULTS:
            if key in incoming_capabilities:
                normalized["capabilities"][key] = bool(incoming_capabilities.get(key))

    return normalized


def is_module_installed(module_code: str) -> bool:
    """Return whether a declared module is installed.

    Callers that resolve a request path must keep treating a ``None`` resolution
    as a kernel/common API path and skip this check. A non-empty module code
    passed here, however, is an explicit module claim and therefore fails closed
    when the catalog does not know it.
    """
    key = _canonical_module_code(module_code)
    if key is None:
        return False
    installed = _installed_module_codes()
    item = next((catalog_item for catalog_item in MODULE_CATALOG if catalog_item.code == key), None)
    if item is None:
        return False
    return _is_catalog_item_installed(item, installed)


def is_module_enabled(config: dict[str, Any] | None, module_code: str) -> bool:
    key = _canonical_module_code(module_code)
    if key is None:
        return False
    if not is_module_installed(key):
        return False
    switches = normalize_feature_switches(config)
    return bool(switches["modules"].get(key, True))


def is_capability_enabled(config: dict[str, Any] | None, capability_code: str) -> bool:
    if capability_code not in CAPABILITY_SWITCH_DEFAULTS:
        return True
    switches = normalize_feature_switches(config)
    return bool(switches["capabilities"].get(capability_code, True))


def resolve_module_from_permission(permission: str | None) -> str | None:
    value = str(permission or "").strip().lower()
    if not value:
        return None
    prefix = _normalize_switch_key(value.split(":", 1)[0].strip())
    return PERMISSION_PREFIX_MODULES.get(prefix)


def resolve_modules_from_permissions(permissions: set[str] | list[str] | tuple[str, ...]) -> set[str]:
    normalized_permissions = {
        str(permission).strip()
        for permission in permissions
        if str(permission).strip()
    }
    if "*:*:*" in normalized_permissions or "*.*.*" in normalized_permissions:
        return {
            item.code
            for item in MODULE_CATALOG
            if is_module_installed(item.code)
        }

    modules: set[str] = set()
    for permission in normalized_permissions:
        module_code = resolve_module_from_permission(permission)
        if module_code and is_module_installed(module_code):
            modules.add(module_code)
    return modules


def resolve_module_from_route_path(path: str | None) -> str | None:
    normalized_path = _normalize_prefix_path(path)
    if not normalized_path:
        return None

    for prefix, module_code in ROUTE_PREFIX_MODULES:
        if normalized_path == prefix or normalized_path.startswith(f"{prefix}/"):
            return module_code
    return None


def resolve_module_from_api_path(path: str | None) -> str | None:
    normalized_path = _normalize_prefix_path(path)
    if not normalized_path:
        return None

    for prefix, module_code in API_PREFIX_MODULES:
        if normalized_path == prefix or normalized_path.startswith(f"{prefix}/"):
            return module_code
    return None


def label_for_module(module_code: str) -> str:
    key = _canonical_module_code(module_code)
    if key is None:
        return module_code
    return MODULE_LABELS.get(key, key)
