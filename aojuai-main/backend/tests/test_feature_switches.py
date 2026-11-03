import pytest

from app.core import feature_switches
from app.core.exceptions import BusinessError
from app.core.feature_switches import (
    build_default_feature_switches,
    build_feature_catalog_definition,
    canonicalize_module_code,
    clear_module_install_caches,
    get_installed_module_codes,
    is_module_enabled,
    is_module_installed,
    list_capability_catalog,
    list_module_catalog,
    normalize_feature_switches,
    resolve_module_from_api_path,
    resolve_module_from_route_path,
    resolve_modules_from_permissions,
)
from app.core.verification import send_verification_code


def test_feature_catalog_contains_core_modules() -> None:
    modules = list_module_catalog()
    capabilities = list_capability_catalog()

    module_codes = [item["code"] for item in modules]
    capability_codes = [item["code"] for item in capabilities]

    # 只断言**内置**目录，不断言"目录里就这几个"——下游分支装一个能力包
    # 就把基座测试打红，等于"加模块还要改中央文件"，正是装配机制要消灭的摩擦。
    assert module_codes[:3] == ["assistant", "speech", "public_site"]
    assert capability_codes == ["verification_sms", "verification_email"]

    assistant = next(item for item in modules if item["code"] == "assistant")
    assert "ai_assistant" in assistant["aliases"]
    assert "/api/v1/assistant" in assistant["apiPrefixes"]

    speech = next(item for item in modules if item["code"] == "speech")
    assert speech["layer"] == "capability"
    assert "/speech" in speech["routePrefixes"]
    assert "/api/v1/speech" in speech["apiPrefixes"]

    public_site = next(item for item in modules if item["code"] == "public_site")
    assert public_site["layer"] == "capability"

    catalog = build_feature_catalog_definition()
    assert catalog["modules"] == modules
    assert len(catalog["catalogDigest"]) == 64


def test_default_feature_switches_follow_catalog() -> None:
    defaults = build_default_feature_switches()
    # 内置项的默认值是契约；能力包会往 modules 里追加自己的项，
    # 所以这里断言"包含且取值正确"，不断言"就这几项"。
    assert defaults["modules"]["assistant"] is True
    assert defaults["modules"]["speech"] is True
    assert defaults["modules"]["public_site"] is False
    assert defaults["capabilities"] == {
        "verification_sms": True,
        "verification_email": True,
    }


def test_normalize_feature_switches_uses_defaults_and_verification_fallback() -> None:
    config = {
        "feature_switches": {
            "modules": {
                "assistant": False,
            }
        },
        "verification": {
            "sms": {"enabled": False},
            "email": {"enabled": True},
        },
    }

    switches = normalize_feature_switches(config)
    assert switches["modules"]["assistant"] is False
    assert switches["modules"]["speech"] is True
    assert switches["capabilities"]["verification_sms"] is False
    assert switches["capabilities"]["verification_email"] is True
    assert is_module_enabled(config, "assistant") is False
    assert is_module_enabled(config, "speech") is True


def test_normalize_feature_switches_ignores_removed_legacy_modules() -> None:
    config = {
        "featureSwitches": {
            "modules": {
                "removed_module": False,
            }
        }
    }

    switches = normalize_feature_switches(config)
    # 未登记的 removed_module 必须被丢掉；内置项取默认值。
    assert "removed_module" not in switches["modules"]
    assert switches["modules"]["assistant"] is True
    assert switches["modules"]["speech"] is True
    assert switches["modules"]["public_site"] is False
    # Downstream modules must be declared in MODULE_CATALOG. If a branch adds a
    # module but forgets that declaration, the switch protects it instead of
    # silently allowing it through.
    assert is_module_installed("removed-module") is False
    assert is_module_enabled(config, "removed-module") is False
    assert canonicalize_module_code("ai-assistant") == "assistant"
    assert canonicalize_module_code("removed-module") is None

    # None here means a common kernel API that belongs to no module; request
    # guards skip installation checks for this path rather than treating it as
    # an unknown declared module.
    assert resolve_module_from_api_path("/api/v1/users") is None


def test_resolve_module_from_api_path() -> None:
    assert resolve_module_from_api_path("/api/v1/assistant/config") == "assistant"
    assert resolve_module_from_api_path("/api/v1/speech/providers") == "speech"
    assert resolve_module_from_api_path("/api/v1/tenant/profile/settings") is None
    assert resolve_module_from_api_path("/api/v1/users") is None


def test_resolve_modules_from_permissions_and_routes() -> None:
    modules = resolve_modules_from_permissions(
        {
            "assistant:config:read",
            "speech:config:read",
            "users:read",
        }
    )
    assert modules == {"assistant", "speech"}

    assert resolve_module_from_route_path("/system/ai-settings") is None
    assert resolve_module_from_route_path("/system/speech-settings") == "speech"
    assert resolve_module_from_route_path("/#/system/speech-settings?from=menu") == "speech"
    assert resolve_module_from_route_path("/system/user") is None


def test_wildcard_permissions_resolve_installed_core_modules() -> None:
    # 通配权限解析出的是"已安装的模块"，能力包装上后会多出来，故用子集断言。
    assert {"assistant", "speech", "public_site"} <= resolve_modules_from_permissions({"*:*:*"})


def test_foundation_module_stays_available_when_optional_modules_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feature_switches.settings, "AOJ_ENABLED_MODULES", "none")
    clear_module_install_caches()

    try:
        assert get_installed_module_codes() == set()
        modules = list_module_catalog()
        # none 标记下只剩 always_installed 的 assistant（AI 基座，别的模块建在它之上）。
        # speech 已改为可装卸，不再强制常驻。
        assert [item["code"] for item in modules] == ["assistant"]
    finally:
        clear_module_install_caches()


@pytest.mark.asyncio
async def test_send_verification_code_respects_sms_toggle() -> None:
    with pytest.raises(BusinessError) as exc:
        await send_verification_code(
            channel="sms",
            target="+8613800138000",
            code="123456",
            tenant_name="demo",
            tenant_config={
                "feature_switches": {
                    "capabilities": {
                        "verification_sms": False,
                    }
                }
            },
            purpose="bind_phone",
        )

    assert exc.value.code == "FEATURE_DISABLED"


def test_catalog_exposes_translatable_keys() -> None:
    """catalog 必须给前端可翻译的 key，且 key 前缀要能被前端识别。

    前端 resolveMaybeI18n 只翻译 system./common./auth. 开头的值，
    其余原样显示——所以写死中文 label 会导致切语言不生效（线上就是这么发现的）。

    同时 label 本身要保留**服务端显示名**：助手会把它拼进给用户看的自然语言
    （"正在打开语音能力"），那里不能漏出 i18n key。
    """
    for item in list_module_catalog():
        key = item["labelKey"]
        assert key.startswith(("system.", "common.", "auth.")), (
            f"{item['code']}: labelKey={key!r} 前端不会翻译它"
        )
        assert item["descriptionKey"].startswith(("system.", "common.", "auth."))
        # 服务端显示名不能是 key
        assert not item["label"].startswith("system."), (
            f"{item['code']}: label 是给助手拼自然语言用的，不能是 i18n key"
        )

    for item in list_capability_catalog():
        assert item["labelKey"].startswith(("system.", "common.", "auth."))
        assert not item["label"].startswith("system.")
