"""出云脱敏：把数据交给外部模型之前的去标识化。

设计与边界见 `docs/dev/reference/LLM_OUTBOUND_REDACTION.md`。
内核不含任何业务词汇，将来按 `flows/NEW_MODULE.md` §0.1 的晋升标准可整体上收到底座。

    redactor = Redactor(policy)
    result = redactor.redact_document(fields=..., known_values=[...])
    payload = enforce(result.fields, policy)      # 命中即抛 RedactionBlocked
    ...调用模型...
    human_visible = redactor.restore(model_output)
"""

from .candidates import Candidate, find_candidates
from .engine import Finding, KnownValue, Placeholder, RedactionResult, Redactor
from .guard import GuardViolation, RedactionBlocked, enforce, scan
from .policy import (
    ALWAYS_BLOCKED,
    ENTITY_LABELS,
    Action,
    EntityKind,
    FieldRule,
    RedactionLevel,
    RedactionPolicy,
    preset,
)

__all__ = [
    "ALWAYS_BLOCKED",
    "ENTITY_LABELS",
    "Action",
    "Candidate",
    "EntityKind",
    "FieldRule",
    "Finding",
    "GuardViolation",
    "KnownValue",
    "Placeholder",
    "RedactionBlocked",
    "RedactionLevel",
    "RedactionPolicy",
    "RedactionResult",
    "Redactor",
    "enforce",
    "find_candidates",
    "preset",
    "scan",
]
