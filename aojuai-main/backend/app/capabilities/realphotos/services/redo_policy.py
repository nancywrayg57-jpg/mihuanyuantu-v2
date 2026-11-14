"""FR-026 / FR-018 decision rules. The five scores are never averaged into total_score."""

from __future__ import annotations

# Code default. Live admin setting is DetectionPassScoreService; do not lower this constant.
PASS_SCORE = 75
DEFAULT_THRESHOLD = 70
DEFAULT_EXTRA_ROUNDS = 1
MIN_EXTRA_ROUNDS = 1
MAX_EXTRA_ROUNDS = 5
# FR-024：手动重试 2 次，含首次共 3 次执行。
MAX_EXECUTIONS = 3


def accepted(*, passed: bool, total_score: int, pass_score: int | None = None) -> bool:
    """Gate on the model flag and a pass line. Omitted pass_score uses the code default 75."""
    line = PASS_SCORE if pass_score is None else int(pass_score)
    return bool(passed) and int(total_score) >= line


def should_auto_redo(
    *,
    enabled: bool,
    total_score: int,
    threshold: int,
    redo_count: int,
    extra_rounds: int,
) -> bool:
    """True only when the chain is enabled, rounds remain, and the score is strictly below the snapshot threshold."""
    if not enabled:
        return False
    if int(redo_count) >= int(extra_rounds):
        return False
    return int(total_score) < int(threshold)


def validate_setting(*, threshold: int, extra_rounds: int) -> None:
    from app.core.exceptions import BusinessError

    if int(threshold) < 0 or int(threshold) > 100:
        raise BusinessError(message="自动重做阈值须在 0 到 100", code="REDO_SETTING_REJECTED")
    if int(extra_rounds) < MIN_EXTRA_ROUNDS or int(extra_rounds) > MAX_EXTRA_ROUNDS:
        raise BusinessError(message="自动重做追加次数须在 1 到 5", code="REDO_SETTING_REJECTED")
