"""S0 constants for realphotos."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings

# 会话：架构推荐绝对有效期 30 天（底座默认 refresh=7，本包登录路径单独钉死）
SESSION_ABSOLUTE_DAYS = 30
ACCESS_TOKEN_MINUTES = max(int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES or 180), 1)

# 验证码
CHALLENGE_TTL_SECONDS = 300
CHALLENGE_CODE_LENGTH = 6
MAX_FAILED_LOGINS = 5

# 队列状态（对齐 QueuePolicy 默认可覆盖）
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"

JOB_KIND_HEARTBEAT = "heartbeat"
JOB_KIND_NOOP = "noop"

LEDGER_TYPE_ADMIN_ADJUST = "admin_adjust"
LEDGER_TYPE_FREEZE = "freeze"
LEDGER_TYPE_CONSUME = "consume"
LEDGER_TYPE_RELEASE = "release"

SEED_OBJECT_KEY = "__seed__/s0-gateway.txt"
SEED_OBJECT_BYTES = b"realphotos-s0-seed-gateway-ok\n"


def allow_dev_captcha() -> bool:
    """开发验证码可：pytest / DEBUG / 显式 Settings 开关。"""
    raw = str(settings.REALPHOTOS_ALLOW_DEV_CAPTCHA or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(settings.DEBUG) or bool(settings.is_pytest_runtime)


def storage_root() -> Path:
    """LocalDisk 根目录；不暴露给 API 响应。"""
    override = str(settings.REALPHOTOS_STORAGE_ROOT or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path(settings.UPLOAD_DIR).resolve().parent / "realphotos").resolve()
