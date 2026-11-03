from __future__ import annotations

import sys

from app.core.config import Settings


def _clear_pool_env(monkeypatch) -> None:  # noqa: ANN001
    for name in (
        "AOJU_PROCESS_ROLE",
        "AOJU_DB_POOL_PROFILE",
        "DB_POOL_SIZE",
        "DB_MAX_OVERFLOW",
        "DB_POOL_TIMEOUT",
        "DB_POOL_RECYCLE",
        "DB_POOL_SIZE_WEB",
        "DB_MAX_OVERFLOW_WEB",
        "DB_POOL_TIMEOUT_WEB",
        "DB_POOL_RECYCLE_WEB",
        "DB_POOL_SIZE_WORKER",
        "DB_MAX_OVERFLOW_WORKER",
        "DB_POOL_TIMEOUT_WORKER",
        "DB_POOL_RECYCLE_WORKER",
        "DB_IDLE_SESSION_TIMEOUT",
        "DB_IDLE_SESSION_TIMEOUT_WEB",
        "DB_IDLE_SESSION_TIMEOUT_WORKER",
    ):
        monkeypatch.delenv(name, raising=False)


def test_database_pool_defaults_to_web_profile(monkeypatch) -> None:  # noqa: ANN001
    _clear_pool_env(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["pytest"])

    settings = Settings(_env_file=None)

    assert settings.ACTIVE_DB_POOL_PROFILE == "web"
    assert settings.DB_POOL_SIZE_EFFECTIVE == 10
    assert settings.DB_MAX_OVERFLOW_EFFECTIVE == 20
    assert settings.DB_POOL_TIMEOUT_EFFECTIVE == 30
    assert settings.DB_POOL_RECYCLE_EFFECTIVE == 1800
    assert settings.DB_IDLE_SESSION_TIMEOUT_EFFECTIVE == 600


def test_database_pool_uses_worker_profile_defaults_for_worker_entrypoint(monkeypatch) -> None:  # noqa: ANN001
    _clear_pool_env(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["/home/aojuai/backend/app/tasks/ppt_master_worker.py"])

    settings = Settings(_env_file=None)

    assert settings.ACTIVE_DB_POOL_PROFILE == "worker"
    assert settings.DB_POOL_SIZE_EFFECTIVE == 4
    assert settings.DB_MAX_OVERFLOW_EFFECTIVE == 4
    assert settings.DB_POOL_TIMEOUT_EFFECTIVE == 15
    assert settings.DB_POOL_RECYCLE_EFFECTIVE == 1800
    assert settings.DB_IDLE_SESSION_TIMEOUT_EFFECTIVE == 300


def test_database_pool_profile_supports_explicit_web_and_worker_overrides(monkeypatch) -> None:  # noqa: ANN001
    _clear_pool_env(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["pytest"])
    monkeypatch.setenv("DB_POOL_SIZE", "10")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "20")
    monkeypatch.setenv("DB_POOL_SIZE_WEB", "16")
    monkeypatch.setenv("DB_MAX_OVERFLOW_WEB", "8")
    monkeypatch.setenv("DB_POOL_SIZE_WORKER", "3")
    monkeypatch.setenv("DB_MAX_OVERFLOW_WORKER", "2")
    monkeypatch.setenv("DB_IDLE_SESSION_TIMEOUT_WEB", "900")
    monkeypatch.setenv("DB_IDLE_SESSION_TIMEOUT_WORKER", "120")

    monkeypatch.setenv("AOJU_DB_POOL_PROFILE", "web")
    web_settings = Settings(_env_file=None)
    assert web_settings.ACTIVE_DB_POOL_PROFILE == "web"
    assert web_settings.DB_POOL_SIZE_EFFECTIVE == 16
    assert web_settings.DB_MAX_OVERFLOW_EFFECTIVE == 8
    assert web_settings.DB_IDLE_SESSION_TIMEOUT_EFFECTIVE == 900

    monkeypatch.setenv("AOJU_DB_POOL_PROFILE", "worker")
    worker_settings = Settings(_env_file=None)
    assert worker_settings.ACTIVE_DB_POOL_PROFILE == "worker"
    assert worker_settings.DB_POOL_SIZE_EFFECTIVE == 3
    assert worker_settings.DB_MAX_OVERFLOW_EFFECTIVE == 2
    assert worker_settings.DB_IDLE_SESSION_TIMEOUT_EFFECTIVE == 120


def test_database_application_name_uses_configured_process_role(monkeypatch) -> None:  # noqa: ANN001
    _clear_pool_env(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["pytest"])

    settings = Settings(_env_file=None, AOJU_PROCESS_ROLE="ppt-master worker")

    assert settings.DB_APPLICATION_NAME_EFFECTIVE == "aojuai:ppt-master-worker"
