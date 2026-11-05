import pytest

from app.core import modules
from app.core.config import settings


@pytest.fixture(autouse=True)
def reset_enabled_modules_state():
    settings.AOJ_ENABLED_MODULES = ""
    modules.clear_module_install_caches()
    yield
    settings.AOJ_ENABLED_MODULES = ""
    modules.clear_module_install_caches()


def test_enabled_modules_default_all():
    settings.AOJ_ENABLED_MODULES = None
    modules.clear_module_install_caches()

    assert modules.is_module_enabled("assistant") is True
    assert modules.is_module_enabled("ai-assistant") is True
    assert modules.is_module_enabled("speech") is True
    assert modules.is_module_enabled("public_site") is True


def test_only_assistant_survives_none_marker():
    """`none` 之后只剩 assistant 常驻。

    speech 从 always_installed 改成可装卸：它有自己的表与 provider 运行时，
    没有理由强制每个部署都带着。assistant 仍常驻——它是 AI 基座，
    cms_ai / tenant_profile 等都建在它之上。
    """
    settings.AOJ_ENABLED_MODULES = "none"
    modules.clear_module_install_caches()

    assert modules.is_module_enabled("assistant") is True
    assert modules.is_module_enabled("speech") is False
    assert modules.is_module_enabled("public_site") is False
    assert modules.is_module_enabled("cms") is False


def test_cms_allowlist_and_alias_normalization():
    settings.AOJ_ENABLED_MODULES = "cms"
    modules.clear_module_install_caches()

    assert modules.is_module_enabled("public_site") is True
    assert modules.is_module_enabled("site_cms") is True
    assert modules.is_module_enabled("assistant") is True
    # allowlist 只列了 cms，speech 不在其中 → 不装
    assert modules.is_module_enabled("speech") is False


def test_base_expansion_marker():
    settings.AOJ_ENABLED_MODULES = "base"
    modules.clear_module_install_caches()

    assert modules.get_enabled_module_ids() == {"assistant", "speech"}
    assert modules.is_module_enabled("public_site") is False


def test_disabled_module_id_for_path():
    settings.AOJ_ENABLED_MODULES = "none"
    modules.clear_module_install_caches()

    assert modules.get_disabled_module_id_for_path("/cms/pages") == "public_site"
    assert modules.get_disabled_module_id_for_path("/assistant/session") is None
    assert modules.get_disabled_module_id_for_path("/speech/tts") == "speech"
    assert modules.get_disabled_module_id_for_path(None) is None
