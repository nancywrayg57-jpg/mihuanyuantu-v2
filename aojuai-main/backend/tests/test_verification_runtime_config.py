from app.core.verification import VerificationRuntimeConfig


def test_from_tenant_config_handles_non_object_root() -> None:
    cfg = VerificationRuntimeConfig.from_tenant_config([])  # type: ignore[arg-type]

    assert cfg.length == 6
    assert cfg.sms_enabled is True
    assert cfg.email_enabled is True


def test_from_tenant_config_reads_verification_namespace() -> None:
    cfg = VerificationRuntimeConfig.from_tenant_config(
        {
            "verification": {
                "code": {"length": 4, "ttlSeconds": 120},
                "sms": {"provider": "webhook", "enabled": False},
                "email": {"subject": "Test Code"},
            }
        }
    )

    assert cfg.length == 4
    assert cfg.ttl_seconds == 120
    assert cfg.sms_provider == "webhook"
    assert cfg.sms_enabled is False
    assert cfg.email_subject == "Test Code"
