"""W3-B：process worker 受控并发上限（运维开关）。"""

from __future__ import annotations

from app.core.config import settings

# 同机 4vCPU / ~7GiB：默认上限 4；生产灰度建议 2。
PROCESS_CONCURRENCY_MAX = 4
PROCESS_CONCURRENCY_MIN = 1


def clamp_process_concurrency(raw: object | None = None) -> int:
    """将配置/CLI 值钳到 [1, 4]；非法输入回退 1（可回滚安全默认）。"""
    if raw is None:
        raw = getattr(settings, "REALPHOTOS_PROCESS_CONCURRENCY", 1)
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return PROCESS_CONCURRENCY_MIN
    return max(PROCESS_CONCURRENCY_MIN, min(PROCESS_CONCURRENCY_MAX, value))
