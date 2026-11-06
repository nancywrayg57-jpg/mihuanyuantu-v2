"""ORM models for realphotos S0 tables (physical prefix cap_realphotos_)."""

from .auth_guard import RealphotosAuthChallenge, RealphotosAuthGuard
from .credit import RealphotosCreditAccount, RealphotosCreditLedgerEntry
from .execution_job import RealphotosExecutionJob
from .merchant import RealphotosMerchantProfile
from .outbox import RealphotosOutbox
from .s1_loop import (
    RealphotosAsset,
    RealphotosBatch,
    RealphotosCreditReservation,
    RealphotosDetectionResult,
    RealphotosImageTask,
    RealphotosInboxMessage,
    RealphotosRechargeOrder,
    RealphotosStageResult,
    RealphotosTaskChain,
    RealphotosTaskSnapshot,
)
from .s3_detection import RealphotosChainPolicy, RealphotosRedoSetting
from .s5_growth import (
    RealphotosGenerationItem,
    RealphotosGenerationTask,
    RealphotosPromptOptimization,
    RealphotosPromptTemplate,
)

__all__ = [
    "RealphotosAsset",
    "RealphotosAuthChallenge",
    "RealphotosAuthGuard",
    "RealphotosBatch",
    "RealphotosChainPolicy",
    "RealphotosCreditAccount",
    "RealphotosCreditLedgerEntry",
    "RealphotosCreditReservation",
    "RealphotosDetectionResult",
    "RealphotosExecutionJob",
    "RealphotosGenerationItem",
    "RealphotosGenerationTask",
    "RealphotosImageTask",
    "RealphotosInboxMessage",
    "RealphotosMerchantProfile",
    "RealphotosOutbox",
    "RealphotosPromptOptimization",
    "RealphotosPromptTemplate",
    "RealphotosRechargeOrder",
    "RealphotosRedoSetting",
    "RealphotosStageResult",
    "RealphotosTaskChain",
    "RealphotosTaskSnapshot",
]
