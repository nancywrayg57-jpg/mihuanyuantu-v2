from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.api import deps
from app.api.v1.endpoints import tenant_profile
from app.core.exceptions import BusinessError
from app.core.redaction import (
    Action,
    EntityKind,
    FieldRule,
    RedactionPolicy,
    Redactor,
    enforce,
)
from app.domain.ai_redaction import (
    TenantRedactionPolicy,
    list_policy_versions,
    load_policy,
    normalize_scope,
    save_policy,
)
from app.infrastructure.database.session import async_session_factory

TEST_TENANT_ID = 9_082_800_001


@pytest.fixture
async def policy_db():
    async with async_session_factory() as db:
        await db.execute(
            delete(TenantRedactionPolicy).where(
                TenantRedactionPolicy.tenant_id == TEST_TENANT_ID
            )
        )
        await db.commit()
        try:
            yield db
        finally:
            await db.rollback()
            await db.execute(
                delete(TenantRedactionPolicy).where(
                    TenantRedactionPolicy.tenant_id == TEST_TENANT_ID
                )
            )
            await db.commit()


def test_presets_have_expected_protection_levels() -> None:
    off = RedactionPolicy.preset("off")
    assert off.detectors == frozenset()
    assert off.derive_person_aliases is False
    assert off.derive_org_prefixes is False
    assert off.generalize_amount_in_text is False

    strong = {
        EntityKind.PHONE,
        EntityKind.ID_CARD,
        EntityKind.BANK_CARD,
        EntityKind.EMAIL,
    }
    basic = RedactionPolicy.preset("basic")
    assert basic.detectors == strong
    assert basic.derive_person_aliases is False
    assert basic.derive_org_prefixes is False
    assert basic.generalize_amount_in_text is False
    assert basic.guard_on_violation == "warn"
    assert basic.field_rules == {}

    standard = RedactionPolicy.preset("standard")
    assert standard.detectors == strong | {
        EntityKind.PERSON,
        EntityKind.ORG,
        EntityKind.ADDRESS,
        EntityKind.SERIAL,
    }
    assert standard.derive_person_aliases is True
    assert standard.derive_org_prefixes is True
    assert standard.generalize_amount_in_text is False
    assert standard.guard_on_violation == "reject"

    strict = RedactionPolicy.preset("strict")
    assert strict.detectors == standard.detectors
    assert strict.generalize_amount_in_text is True
    assert strict.allow_terms == frozenset()
    assert strict.guard_on_violation == "reject"
    assert strict.rule_for("undeclared").action == Action.BLOCK


def test_level_json_uses_preset_then_applies_overrides_and_round_trips() -> None:
    policy = RedactionPolicy.from_json(
        {
            "level": "custom",
            "baseLevel": "basic",
            "fieldRules": {
                "summary": {"action": "pass", "kind": None, "note": "可出站"},
            },
            "derivePersonAliases": True,
            "allowTerms": ["AOJU"],
            "approvedBy": "安全负责人",
            "approvedAt": "2026-08-28T12:00:00+00:00",
            "note": "高级覆盖",
        },
        version=7,
    )
    assert policy.level == "custom"
    assert policy.base_level == "basic"
    assert policy.detectors == RedactionPolicy.preset("basic").detectors
    assert policy.derive_person_aliases is True
    assert policy.rule_for("summary").action == Action.PASS

    serialized = policy.to_json()
    assert serialized["level"] == "custom"
    assert serialized["baseLevel"] == "basic"
    restored = RedactionPolicy.from_json(serialized, version=7)
    assert restored == policy


def test_named_level_json_inherits_unspecified_preset_values() -> None:
    policy = RedactionPolicy.from_json(
        {"level": "strict", "fieldRules": {"summary": {"action": "pass"}}}
    )
    assert policy.level == "strict"
    assert policy.generalize_amount_in_text is True
    assert policy.derive_person_aliases is True
    assert policy.guard_on_violation == "reject"


def test_off_is_a_true_passthrough_and_audits_level_and_version() -> None:
    policy = replace(RedactionPolicy.preset("off"), version=12)
    source = {
        "undeclared": "客户手机１３８００１３８０００",
        "identity": "11010519491231002X",
    }
    result = Redactor(policy).redact_document(fields=source)
    assert result.fields == source
    assert result.redacted is False
    assert result.blocked_fields == []
    assert result.audit_summary()["policyVersion"] == 12
    assert result.audit_summary()["level"] == "off"
    assert enforce(source, policy) is source


@pytest.mark.requires_database  # 真库集成测试，没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.asyncio
async def test_load_policy_three_level_fallback(policy_db) -> None:
    module_default = RedactionPolicy(
        version=0,
        level="custom",
        field_rules={"summary": FieldRule(action=Action.PASS)},
    )

    fallback = await load_policy(
        policy_db,
        tenant_id=TEST_TENANT_ID,
        scope="reports",
        default=module_default,
    )
    assert fallback is module_default

    await save_policy(
        policy_db,
        tenant_id=TEST_TENANT_ID,
        scope="*",
        rules=RedactionPolicy.preset("basic").to_json(),
        approved_by="负责人甲",
    )
    inherited = await load_policy(
        policy_db,
        tenant_id=TEST_TENANT_ID,
        scope="reports",
        default=module_default,
    )
    assert inherited.level == "basic"
    assert inherited.rule_for("summary").action == Action.PASS

    module_rules = RedactionPolicy.preset("strict").to_json()
    module_rules["fieldRules"] = {
        "moduleOnly": {"action": "pass", "kind": None, "note": ""}
    }
    await save_policy(
        policy_db,
        tenant_id=TEST_TENANT_ID,
        scope="reports",
        rules=module_rules,
        approved_by="负责人乙",
    )
    explicit = await load_policy(
        policy_db,
        tenant_id=TEST_TENANT_ID,
        scope="reports",
        default=module_default,
    )
    assert explicit.level == "strict"
    assert explicit.rule_for("moduleOnly").action == Action.PASS
    assert explicit.rule_for("summary").action == Action.BLOCK


@pytest.mark.requires_database  # 真库集成测试，没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.asyncio
async def test_save_increments_version_and_deactivates_old_row(policy_db) -> None:
    first = await save_policy(
        policy_db,
        tenant_id=TEST_TENANT_ID,
        scope="*",
        rules=RedactionPolicy.preset("standard").to_json(),
        approved_by="负责人甲",
        note="第一版",
    )
    second = await save_policy(
        policy_db,
        tenant_id=TEST_TENANT_ID,
        scope="*",
        rules=RedactionPolicy.preset("strict").to_json(),
        approved_by="负责人乙",
        note="第二版",
    )
    assert (first.version, second.version) == (1, 2)
    assert first.is_active is False
    assert second.is_active is True

    history = await list_policy_versions(
        policy_db, tenant_id=TEST_TENANT_ID, scope="*"
    )
    assert [item.version for item in history] == [2, 1]
    assert [item.is_active for item in history] == [True, False]


def test_scope_validation() -> None:
    assert normalize_scope(None) == "*"
    assert normalize_scope(" reports ") == "reports"
    for invalid in ("Reports", "daily-reports", "../reports", "a" * 65):
        with pytest.raises(BusinessError):
            normalize_scope(invalid)


@pytest.mark.requires_database  # 真库集成测试，没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.asyncio
async def test_off_can_only_be_saved_on_signed_shared_scope(policy_db) -> None:
    with pytest.raises(BusinessError, match="off 只能"):
        await save_policy(
            policy_db,
            tenant_id=TEST_TENANT_ID,
            scope="reports",
            rules=RedactionPolicy.preset("off").to_json(),
            approved_by="负责人",
        )
    with pytest.raises(BusinessError, match="签字人"):
        await save_policy(
            policy_db,
            tenant_id=TEST_TENANT_ID,
            scope="*",
            rules=RedactionPolicy.preset("off").to_json(),
            approved_by=" ",
        )


def _build_api_app(db) -> FastAPI:
    app = FastAPI()
    app.include_router(tenant_profile.router, prefix="/api/v1/tenant/profile")

    async def override_tenant_admin():
        return SimpleNamespace(id=77, tenant_id=TEST_TENANT_ID, is_superuser=False)

    async def override_tenant_ctx():
        return SimpleNamespace(
            tenant_id=TEST_TENANT_ID,
            user_tenant_id=TEST_TENANT_ID,
            is_superuser=False,
        )

    async def override_db():
        yield db

    app.dependency_overrides[deps.get_current_tenant_admin] = override_tenant_admin
    app.dependency_overrides[deps.get_tenant_context] = override_tenant_ctx
    app.dependency_overrides[deps.get_db] = override_db
    return app


@pytest.mark.requires_database  # 真库集成测试，没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.asyncio
async def test_ai_redaction_api_contract(policy_db) -> None:
    app = _build_api_app(policy_db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initial_response = await client.get(
            "/api/v1/tenant/profile/settings/ai-redaction?scope=*"
        )
        assert initial_response.status_code == 200, initial_response.text
        initial = initial_response.json()["data"]
        assert initial["scope"] == "*"
        assert initial["scopes"] == ["*"]
        assert initial["active"] is None
        assert initial["effective"]["level"] == "standard"
        assert set(initial["presets"]) == {"basic", "standard", "strict"}

        update_response = await client.put(
            "/api/v1/tenant/profile/settings/ai-redaction",
            json={
                "scope": "*",
                "level": "basic",
                "rules": {
                    "allowTerms": ["AOJU"],
                    "fieldRules": {
                        "summary": {"action": "pass", "kind": None, "note": ""}
                    },
                },
                "approvedBy": "安全负责人",
                "note": "首版签字",
            },
        )
        assert update_response.status_code == 200, update_response.text
        updated = update_response.json()["data"]
        assert updated["active"]["version"] == 1
        assert updated["active"]["level"] == "basic"
        assert updated["active"]["approvedBy"] == "安全负责人"
        assert updated["active"]["approvedAt"]
        assert updated["active"]["note"] == "首版签字"
        assert updated["active"]["rules"]["derivePersonAliases"] is False

        versions_response = await client.get(
            "/api/v1/tenant/profile/settings/ai-redaction/versions?scope=*&limit=10"
        )
        assert versions_response.status_code == 200, versions_response.text
        versions = versions_response.json()["data"]
        assert len(versions) == 1
        assert versions[0]["version"] == 1
        assert versions[0]["level"] == "basic"
        assert versions[0]["approvedBy"] == "安全负责人"


def test_non_custom_api_rules_cannot_override_preset_security_fields() -> None:
    request = tenant_profile.TenantAIRedactionPolicyUpdate.model_validate(
        {
            "scope": "*",
            "level": "basic",
            "rules": {"guardOnViolation": "reject"},
            "approvedBy": "负责人",
        }
    )
    with pytest.raises(BusinessError, match="只允许覆盖"):
        tenant_profile._compose_ai_redaction_rules(request)
