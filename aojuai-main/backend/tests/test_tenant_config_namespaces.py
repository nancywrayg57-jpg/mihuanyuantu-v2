from app.core.tenant_config_namespaces import (
    get_tenant_config_namespace,
    safe_tenant_config_dict,
    set_tenant_config_namespace,
)


def test_safe_tenant_config_dict_returns_empty_dict_for_non_objects() -> None:
    assert safe_tenant_config_dict(None) == {}
    assert safe_tenant_config_dict([]) == {}


def test_get_tenant_config_namespace_returns_empty_dict_for_missing_or_invalid_path() -> None:
    assert get_tenant_config_namespace(None, ("integrations", "ai")) == {}
    assert get_tenant_config_namespace({"integrations": []}, ("integrations", "ai")) == {}


def test_set_tenant_config_namespace_preserves_unrelated_keys_and_siblings() -> None:
    original = {
        "theme": "default",
        "integrations": {
            "speech": {"enabled": True},
            "assistant": {"model": "base-model"},
        },
    }

    updated = set_tenant_config_namespace(
        original,
        ("integrations", "assistant"),
        {"model": "next-model", "baseUrl": "https://ai.example.com/v1"},
    )

    assert updated["theme"] == "default"
    assert updated["integrations"]["speech"] == {"enabled": True}
    assert updated["integrations"]["assistant"] == {"model": "next-model", "baseUrl": "https://ai.example.com/v1"}
    assert original["integrations"]["assistant"] == {"model": "base-model"}


def test_set_tenant_config_namespace_supports_top_level_namespaces() -> None:
    updated = set_tenant_config_namespace(
        {"theme": "default"},
        ("assistant",),
        {"model": "base-model"},
    )

    assert updated["theme"] == "default"
    assert updated["assistant"] == {"model": "base-model"}
