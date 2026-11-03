from app.domain.assistant.config_schemas import AssistantConfigUpsertRequest, AssistantConfigView
from app.domain.assistant_bridge import assistant_config_to_view, merge_assistant_config


def test_assistant_bridge_view_exposes_default_capabilities() -> None:
    payload = assistant_config_to_view({})

    assert payload["enabled"] is False
    assert payload["isEnabled"] is False
    assert payload["apiKeySet"] is False
    assert payload["apiKeyMasked"] is None
    assert payload["capabilities"]["policy"]["requireConfirmationForWrites"] is True
    assert payload["capabilities"]["policy"]["maxVisibleTools"] == 8
    assert payload["capabilities"]["toolBindings"][0]["id"] == "time.now"
    assert payload["capabilities"]["skillBindings"][0]["id"] == "core.context_reader"
    assert payload["capabilities"]["moduleSkillGovernance"]["modules"][0]["moduleCode"] == "default"
    assert payload["moduleSkillCatalog"][0]["moduleCode"] == "default"


def test_assistant_bridge_merge_deep_merges_capabilities_without_dropping_defaults() -> None:
    merged = merge_assistant_config(
        {},
        {
            "capabilities": {
                "policy": {
                    "maxVisibleTools": 5,
                },
                "memory": {
                    "profile": {
                        "preferredStyle": "简洁直接",
                    }
                },
            }
        },
    )

    assert merged["capabilities"]["policy"]["maxVisibleTools"] == 5
    assert merged["capabilities"]["policy"]["requireConfirmationForWrites"] is True
    assert merged["capabilities"]["memory"]["profile"]["preferredStyle"] == "简洁直接"
    assert merged["capabilities"]["toolBindings"][1]["id"] == "time.range.resolve"


def test_assistant_bridge_merge_preserves_module_skill_governance() -> None:
    merged = merge_assistant_config(
        {},
        {
            "capabilities": {
                "moduleSkillGovernance": {
                    "modules": [
                        {
                            "moduleCode": "default",
                            "skillRules": [
                                {
                                    "skillId": "default.page_orienter",
                                    "enabled": False,
                                    "rank": 7,
                                }
                            ],
                        }
                    ]
                }
            }
        },
    )

    assert merged["capabilities"]["moduleSkillGovernance"]["modules"][0]["moduleCode"] == "default"
    assert merged["capabilities"]["moduleSkillGovernance"]["modules"][0]["skillRules"][0]["enabled"] is False
    assert merged["capabilities"]["moduleSkillGovernance"]["modules"][0]["skillRules"][0]["rank"] == 7


def test_assistant_bridge_view_masks_api_key() -> None:
    payload = assistant_config_to_view({"apiKey": "sk-abcdef1234567890"})

    assert payload["apiKeySet"] is True
    assert payload["apiKeyMasked"] == "sk-a***********7890"


def test_assistant_schema_accepts_legacy_enabled_alias_and_trims_text() -> None:
    payload = AssistantConfigUpsertRequest.model_validate(
        {
            "isEnabled": True,
            "baseUrl": " https://example.com/v1 ",
            "model": " gpt-test ",
            "apiKey": "  sk-abc123  ",
        }
    )

    assert payload.enabled is True
    assert payload.base_url == "https://example.com/v1"
    assert payload.model == "gpt-test"
    assert payload.api_key == "sk-abc123"


def test_assistant_view_exposes_is_enabled_alias() -> None:
    payload = AssistantConfigView(enabled=True).model_dump(by_alias=True)

    assert payload["enabled"] is True
    assert payload["isEnabled"] is True
