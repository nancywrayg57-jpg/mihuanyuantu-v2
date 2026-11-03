from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.users.profile_schema import (
    UserProfileFieldsConfig,
    build_user_profile_completion_state,
    sanitize_user_profile_payload,
)


def _build_profile_config() -> UserProfileFieldsConfig:
    return UserProfileFieldsConfig.model_validate(
        {
            "enabled": True,
            "version": 3,
            "fields": [
                {
                    "key": "department",
                    "label": "Department",
                    "type": "select",
                    "required": True,
                    "filterable": True,
                    "sort": 30,
                    "options": [
                        {"label": "HR", "value": "hr"},
                        {"label": "Ops", "value": "ops"},
                    ],
                },
                {
                    "key": "Company Name",
                    "label": "Company",
                    "type": "text",
                    "required": True,
                    "listVisible": True,
                    "sort": 20,
                },
                {
                    "key": "skills",
                    "label": "Skills",
                    "type": "multi_select",
                    "sort": 40,
                    "options": [
                        {"label": "Sales", "value": "sales"},
                        {"label": "Support", "value": "support"},
                    ],
                },
                {
                    "key": "age",
                    "label": "Age",
                    "type": "number",
                    "sort": 10,
                },
            ],
        }
    )


def test_profile_config_normalizes_keys_and_sorts_fields() -> None:
    config = _build_profile_config()

    assert [field.key for field in config.fields] == [
        "age",
        "company_name",
        "department",
        "skills",
    ]


def test_profile_config_rejects_duplicate_keys_after_normalization() -> None:
    with pytest.raises(ValidationError, match="存在重复字段 key: company_name"):
        UserProfileFieldsConfig.model_validate(
            {
                "enabled": True,
                "fields": [
                    {"key": "company-name", "label": "Company A"},
                    {"key": "Company Name", "label": "Company B"},
                ],
            }
        )


def test_sanitize_user_profile_payload_normalizes_values_and_reports_errors() -> None:
    config = _build_profile_config()

    sanitized, errors = sanitize_user_profile_payload(
        {
            "company_name": "  AOJU  ",
            "department": "invalid",
            "skills": ["sales", "sales", "support"],
            "age": " 32 ",
            "unknown": "ignored",
        },
        config,
    )

    assert sanitized == {
        "company_name": "AOJU",
        "skills": ["sales", "support"],
        "age": 32,
    }
    assert errors == ["Department: 选项不在允许范围内"]


def test_completion_state_uses_current_required_fields() -> None:
    config = _build_profile_config()

    state = build_user_profile_completion_state(
        config,
        {"company_name": "AOJU"},
        existing_meta={"lastCompletedAt": "2026-03-01T00:00:00+00:00", "source": "register"},
    )

    assert state.enabled is True
    assert state.schema_version == 3
    assert state.completed is False
    assert state.required_keys == ["company_name", "department"]
    assert state.missing_required_keys == ["department"]
    assert state.last_completed_at == "2026-03-01T00:00:00+00:00"
    assert state.source == "register"


def test_completion_state_sets_timestamp_when_profile_is_complete() -> None:
    config = _build_profile_config()

    state = build_user_profile_completion_state(
        config,
        {"company_name": "AOJU", "department": "ops"},
        source="profile_required",
    )

    assert state.completed is True
    assert state.missing_required_keys == []
    assert state.last_completed_at is not None
    assert state.source == "profile_required"
