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
JOB_KIND_PROCESS_IMAGE = "process_image"

LEDGER_TYPE_ADMIN_ADJUST = "admin_adjust"
LEDGER_TYPE_FREEZE = "freeze"
LEDGER_TYPE_CONSUME = "consume"
LEDGER_TYPE_RELEASE = "release"
LEDGER_TYPE_RECHARGE_CONFIRM = "recharge_confirm"

# FR-003 / NFR-004 / 架构 §8.1：20 MiB = 20,971,520 字节；40MP。
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
# FR-016 / anchor B03：处理单价。S1 单张路径只接受 1 张。
# S4 批次按请求张数冻结，每张仍是 10，上限 10 张。
PROCESS_UNIT_CREDITS = 10
S1_MAX_IMAGES = 1
S4_MIN_IMAGES = 1
S4_MAX_IMAGES = 10
# FR-016：生图成功入库每张 10，不预冻。提示词优化成功 1。数量与文生图宽高见 FR-010。
GENERATION_UNIT_CREDITS = 10
PROMPT_OPT_CREDITS = 1
GENERATION_MIN_QUANTITY = 1
GENERATION_MAX_QUANTITY = 10
GENERATION_MIN_EDGE = 256
GENERATION_MAX_EDGE = 2048
# 管理员 2026-11-06：URL/JSON 导入单次上限按 AC-002 取 100。本地上传仍是 20。
URL_IMPORT_MAX = 100
# FR-028 / AC-002：本地上传单次硬上限；第 21 张起整批拒绝。
UPLOAD_BATCH_MAX = 20
# FR-023：站内消息投递最多自动重试 3 次（含首次共 3 次 attempt）。
NOTIFY_MAX_ATTEMPTS = 3
NOTIFY_RETRY_SECONDS = (2, 5, 15)
IMAGE_PROCESSING_SCOPE = "image_processing"
# FR-019：处理结果 7×24 小时；站内消息 30 天。
OUTPUT_TTL_HOURS = 7 * 24
INBOX_TTL_DAYS = 30
# FR-007 首期设备类型（英文 identifier）；与 PRD「手机/单反/无反/运动相机」对应。
DEVICE_TYPES = ("phone", "dslr", "mirrorless", "action")
DEVICE_TYPE_ALIASES = {"camera": "dslr"}  # 历史错误值诚实映射，禁止静默冒充未说明的第三套名
JOB_KIND_INBOX_CLEANUP = "inbox_cleanup"
JOB_KIND_OUTPUT_CLEANUP = "output_cleanup"

# SM-001 名称。S1 不进入自动重做 / 主动重处理 / 技术重试链。
TASK_SUBMITTED = "SUBMITTED"
TASK_PRE_REVIEW = "PRE_REVIEW"
TASK_PRE_REVIEW_PASSED = "PRE_REVIEW_PASSED"
TASK_PRE_REVIEW_FAILED = "PRE_REVIEW_FAILED"
TASK_FULL_PROCESSING = "FULL_PROCESSING"
TASK_DETECTION = "DETECTION"
TASK_DELIVERED = "DELIVERED"
TASK_FAILED = "FAILED"
TASK_AUTO_REPROCESS_PENDING = "AUTO_REPROCESS_PENDING"

# 运行中占用资源，禁止删除（anchor E04 / FR-003 段）。
RUNNING_TASK_STATUSES = frozenset(
    {
        TASK_SUBMITTED,
        TASK_PRE_REVIEW,
        TASK_PRE_REVIEW_PASSED,
        TASK_FULL_PROCESSING,
        TASK_DETECTION,
        TASK_AUTO_REPROCESS_PENDING,
    }
)

# 规则替身结果。技术异常不写五维报告、不写可下载文件（FR-018）。
DETECT_PASS = "pass"
DETECT_NOT_PASSED = "not_passed"
DETECT_TECHNICAL = "technical"
DETECT_GEMINI = "gemini"
PRE_REVIEW_PASS = "pass"
PRE_REVIEW_REJECT = "reject"

# 充值：现行 PRD §12.1 点名的人民币档位。到账积分按 FR-021「1 元 = 10 积分」。
# 赠送积分只出现在不得作为开发依据的待决策清单/归档，本阶段不采用。
RECHARGE_TIERS_YUAN = (100, 300, 500, 1000, 3000)
# 管理员 2026-11-06：按待决策清单已确认档位入账，额外积分并入同一余额。
RECHARGE_CREDITS_BY_YUAN = {
    100: 1000,
    300: 3150,
    500: 5500,
    1000: 11500,
    3000: 36000,
}
RECHARGE_PRICE_FORMULA = "decision_list_v1_confirmed_2026_10_23_tier_credits"

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
