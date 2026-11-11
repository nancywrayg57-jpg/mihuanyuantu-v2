"""AD-001：realphotos 进程角色与可认领 job_kind 白名单。

三入口（工单 R5）：
- process → 图片处理
- notify  → outbox 投递（独立脚本，不走 execution_jobs claim）
- cleanup → inbox/output 清理

`realphotos_heartbeat` 保留为兼容入口，但默认仅认领 process 侧 kinds，
不再与 cleanup 抢同一队列（完整分进程见 scripts/run_realphotos_*）。
"""

from __future__ import annotations

from typing import Final

ROLE_PROCESS: Final = "process"
ROLE_NOTIFY: Final = "notify"
ROLE_CLEANUP: Final = "cleanup"

PROCESS_JOB_KINDS: Final[tuple[str, ...]] = (
    "heartbeat",
    "noop",
    "process_image",
)
CLEANUP_JOB_KINDS: Final[tuple[str, ...]] = (
    "inbox_cleanup",
    "output_cleanup",
)

ROLE_JOB_KINDS: Final[dict[str, tuple[str, ...]]] = {
    ROLE_PROCESS: PROCESS_JOB_KINDS,
    ROLE_CLEANUP: CLEANUP_JOB_KINDS,
}


def job_kinds_for_role(role: str) -> tuple[str, ...]:
    key = str(role or "").strip().lower()
    if key not in ROLE_JOB_KINDS:
        raise ValueError(f"unknown realphotos worker role {role!r}; expected process|cleanup")
    return ROLE_JOB_KINDS[key]
