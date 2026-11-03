"""AOJU Backend - Assistant Action Protocol Helpers"""

from __future__ import annotations

import json
import re
from typing import Any

AOJU_ACTION_BLOCK_RE = re.compile(r"```aoju_action\s*\r?\n([\s\S]*?)```", re.MULTILINE)
GENERIC_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\r?\n([\s\S]*?)```", re.MULTILINE)
XML_STYLE_ACTION_BLOCK_RE = re.compile(r"<assistant_action>\s*([\s\S]*?)\s*</assistant_action>", re.MULTILINE)
AOJU_ACTION_FENCE_RE = re.compile(r"```aoju_action\b", re.IGNORECASE)
PARTIAL_JSON_ACTION_TAIL_RE = re.compile(r"(?:^|\n\s*\n|\n)(\s*[\{\[][\s\S]*)$", re.MULTILINE)
JSON_ACTION_HINT_RE = re.compile(
    r'"(?:assistantAction|assistant_action|toolId|tool_id|actionType|action_type|targetRoutePath|targetModuleCode|params|parameters|args)"'
)
JSON_LIKE_TAIL_RE = re.compile(r"^[\s\{\}\[\]\":,._/\-\w]+$")
_ALLOWED_ACTION_MODES = {"collect", "confirm", "ready", "blocked", "result"}
_ACTION_RESULT_BLOCK_TAG = "aoju_action_result"
_ACTION_STATE_BLOCK_TAG = "aoju_action_state"
_INTERNAL_AOJU_BLOCK_RE = re.compile(r"\[(aoju_[a-z_]+)\][\s\S]*?\[/\1\]", re.MULTILINE)
_SENSITIVE_RESULT_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "share_token",
    "password",
    "password_hash",
    "secret",
    "api_key",
    "apikey",
}
_RESULT_SUMMARY_SKIP_KEYS = {
    "items",
    "tool",
    "querycontext",
    "pagination",
    "validationerrors",
}
_ENTITY_REFERENCE_PREFERRED_KEYS = (
    "id",
    "name",
    "title",
    "label",
    "code",
    "username",
    "nickname",
    "status",
    "type",
    "projectId",
    "courseId",
    "teacherId",
    "companyId",
    "shareId",
    "sessionId",
    "startDate",
    "endDate",
    "startTime",
    "endTime",
)


def _is_write_like_tool(tool_id: str) -> bool:
    normalized = str(tool_id or "").strip().lower()
    if not normalized:
        return False
    write_markers = (".create", ".update", ".delete", ".review", ".submit", ".confirm")
    return any(marker in normalized for marker in write_markers)


def _safe_positive_int(value: Any, fallback: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _normalize_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return None


def _read_explicit_bool(source: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        if key in source:
            return _normalize_optional_bool(source.get(key))
    return None


def _normalize_field_definition(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    key = str(value.get("key") or "").strip()
    if not key:
        return None

    label = str(value.get("label") or key).strip() or key
    description = str(value.get("description") or "").strip()
    examples = [str(item).strip() for item in (value.get("examples") or []) if str(item).strip()]
    return {
        "key": key,
        "label": label,
        "required": _read_explicit_bool(value, "required"),
        "description": description,
        "examples": examples[:6],
    }


def normalize_assistant_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    assistant_action = value.get("assistantAction") or value.get("assistant_action")
    if isinstance(assistant_action, dict):
        merged_value = dict(assistant_action)
        if "params" not in merged_value and isinstance(value.get("params"), dict):
            merged_value["params"] = value.get("params")
        if "args" not in merged_value and isinstance(value.get("args"), dict):
            merged_value["args"] = value.get("args")
        if "parameters" not in merged_value and isinstance(value.get("parameters"), dict):
            merged_value["parameters"] = value.get("parameters")
        if "summary" not in merged_value and value.get("summary"):
            merged_value["summary"] = value.get("summary")
        return normalize_assistant_action(merged_value)

    tool_id = str(
        value.get("toolId")
        or value.get("tool_id")
        or value.get("tool")
        or value.get("actionType")
        or value.get("action_type")
        or (assistant_action if isinstance(assistant_action, str) else "")
        or ""
    ).strip()
    if not tool_id:
        return None

    raw_mode = value.get("mode")
    mode = str(raw_mode or "").strip().lower() or None
    if mode and mode not in _ALLOWED_ACTION_MODES:
        mode = None
    if not mode:
        mode = "confirm" if _is_write_like_tool(tool_id) else "ready"

    collected_params = (
        value.get("collectedParams")
        or value.get("collected_params")
        or value.get("args")
        or value.get("params")
        or value.get("parameters")
        or {}
    )
    if not isinstance(collected_params, dict):
        collected_params = {}

    target_route_path = str(
        value.get("targetRoutePath")
        or value.get("target_route_path")
        or collected_params.get("targetRoutePath")
        or collected_params.get("target_route_path")
        or collected_params.get("routePath")
        or collected_params.get("route_path")
        or collected_params.get("path")
        or ""
    ).strip() or None
    target_module_code = str(
        value.get("targetModuleCode")
        or value.get("target_module_code")
        or collected_params.get("targetModuleCode")
        or collected_params.get("target_module_code")
        or collected_params.get("moduleCode")
        or collected_params.get("module_code")
        or ""
    ).strip() or None
    target_context_params = (
        value.get("targetContextParams")
        or value.get("target_context_params")
        or collected_params.get("targetContextParams")
        or collected_params.get("target_context_params")
        or {}
    )
    if not isinstance(target_context_params, dict):
        target_context_params = {}

    raw_missing_fields = value.get("missingFields") or value.get("missing_fields") or []
    missing_fields = [
        item
        for item in (
            _normalize_field_definition(field)
            for field in (raw_missing_fields if isinstance(raw_missing_fields, list) else [])
        )
        if item
    ]

    confirmation_required = _read_explicit_bool(value, "confirmationRequired", "confirmation_required")
    can_execute = _read_explicit_bool(value, "canExecute", "can_execute")
    auto_execute = _read_explicit_bool(value, "autoExecute", "auto_execute")
    if confirmation_required is None:
        confirmation_required = _is_write_like_tool(tool_id)
    if can_execute is None:
        can_execute = not missing_fields and mode in {"confirm", "ready"}
    if auto_execute is None:
        auto_execute = False

    confirm_text = str(value.get("confirmText") or value.get("confirm_text") or "").strip()
    if not confirm_text:
        confirm_text = "前往页面" if tool_id == "page.router.navigate" else "确认执行"

    tool_label = str(value.get("toolLabel") or value.get("tool_label") or "").strip() or None
    if not tool_label and tool_id == "page.router.navigate":
        tool_label = "前往目标页面"

    return {
        "version": _safe_positive_int(value.get("version"), 1),
        "toolId": tool_id,
        "toolLabel": tool_label,
        "skillId": str(value.get("skillId") or value.get("skill_id") or "").strip() or None,
        "skillLabel": str(value.get("skillLabel") or value.get("skill_label") or "").strip() or None,
        "mode": mode,
        "summary": str(value.get("summary") or value.get("description") or collected_params.get("summary") or "").strip(),
        "targetRoutePath": target_route_path,
        "targetModuleCode": target_module_code,
        "targetContextParams": dict(target_context_params),
        "confirmationRequired": confirmation_required,
        "canExecute": can_execute,
        "autoExecute": auto_execute,
        "confirmText": confirm_text,
        "reason": str(value.get("reason") or "").strip() or None,
        "nextQuestion": str(value.get("nextQuestion") or value.get("next_question") or "").strip() or None,
        "suggestedReplies": [
            str(item).strip()
            for item in (value.get("suggestedReplies") or value.get("suggested_replies") or [])
            if str(item).strip()
        ][:6],
        "collectedParams": dict(collected_params),
        "missingFields": missing_fields,
    }


def _normalize_action_candidate(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        for item in value:
            action = normalize_assistant_action(item)
            if action:
                return action
        return None
    return normalize_assistant_action(value)


def strip_internal_action_tags(text: str, *, trim: bool = True) -> str:
    cleaned = _INTERNAL_AOJU_BLOCK_RE.sub("", text)
    return cleaned.strip() if trim else cleaned


def sanitize_streaming_assistant_text(text: str) -> str:
    cleaned = strip_internal_action_tags(text, trim=False)
    last_internal_marker = cleaned.rfind("[aoju_")
    if last_internal_marker >= 0:
        cleaned = cleaned[:last_internal_marker]
    fenced_action_match = AOJU_ACTION_FENCE_RE.search(cleaned)
    if fenced_action_match:
        cleaned = cleaned[:fenced_action_match.start()]
    cleaned, action = _extract_xml_style_action(cleaned)
    if action:
        return cleaned
    cleaned, action = _extract_generic_json_block_action(cleaned)
    if action:
        return cleaned
    cleaned, action = _extract_inline_json_action(cleaned)
    if action:
        return cleaned
    matches = list(PARTIAL_JSON_ACTION_TAIL_RE.finditer(cleaned))
    for match in reversed(matches):
        suffix = str(match.group(1) or "")
        normalized_suffix = suffix.lstrip()
        if not normalized_suffix.startswith(("{", "[")):
            continue
        if "```" in suffix or "<assistant_action>" in suffix.lower():
            continue
        if normalized_suffix in {"{", "["}:
            return cleaned[: match.start(1)]
        if JSON_ACTION_HINT_RE.search(suffix):
            return cleaned[: match.start(1)]
        if JSON_LIKE_TAIL_RE.fullmatch(suffix) and (
            normalized_suffix.count("{") > normalized_suffix.count("}")
            or normalized_suffix.count("[") > normalized_suffix.count("]")
        ):
            return cleaned[: match.start(1)]
    return cleaned


def _extract_generic_json_block_action(text: str) -> tuple[str, dict[str, Any] | None]:
    matches = list(GENERIC_JSON_BLOCK_RE.finditer(text))
    for match in reversed(matches):
        block = str(match.group(1) or "").strip()
        if not block:
            continue
        try:
            payload = json.loads(block)
        except Exception:
            continue
        action = _normalize_action_candidate(payload)
        if not action:
            continue
        plain_text = text[:match.start()].rstrip()
        return plain_text, action
    return text, None


def _extract_xml_style_action(text: str) -> tuple[str, dict[str, Any] | None]:
    matches = list(XML_STYLE_ACTION_BLOCK_RE.finditer(text))
    for match in reversed(matches):
        block = str(match.group(1) or "").strip()
        if not block:
            continue
        try:
            payload = json.loads(block)
        except Exception:
            continue
        action = _normalize_action_candidate(payload)
        if not action:
            continue
        plain_text = XML_STYLE_ACTION_BLOCK_RE.sub("", text).strip()
        return plain_text, action
    return text, None


def _extract_inline_json_action(text: str) -> tuple[str, dict[str, Any] | None]:
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, int, dict[str, Any]]] = []

    for matched in re.finditer(r"[\{\[]", text):
        start = matched.start()
        try:
            payload, end = decoder.raw_decode(text[start:])
        except Exception:
            continue
        action = _normalize_action_candidate(payload)
        if not action:
            continue
        absolute_end = start + end
        suffix = text[absolute_end:].strip()
        if suffix:
            continue
        candidates.append((start, absolute_end, action))

    if not candidates:
        return text, None

    start, _, action = candidates[-1]
    plain_text = text[:start].rstrip()
    return plain_text, action


def extract_assistant_action(raw_text: str | None) -> tuple[str, dict[str, Any] | None]:
    text = str(raw_text or "").strip()
    if not text:
        return "", None
    text = strip_internal_action_tags(text)

    matches = list(AOJU_ACTION_BLOCK_RE.finditer(text))
    action: dict[str, Any] | None = None
    for match in reversed(matches):
        block = str(match.group(1) or "").strip()
        if not block:
            continue
        try:
            payload = json.loads(block)
        except Exception:
            continue
        action = _normalize_action_candidate(payload)
        if action:
            plain_text = text[:match.start()].rstrip()
            return plain_text, action

    text, action = _extract_xml_style_action(text)
    if action:
        return text, action

    text, action = _extract_generic_json_block_action(text)
    if action:
        return text, action

    return _extract_inline_json_action(text)


def _sanitize_result_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).strip().lower() in _SENSITIVE_RESULT_KEYS:
                continue
            sanitized[str(key)] = _sanitize_result_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_result_payload(item) for item in value]
    return value


def _compact_entity_reference(value: Any, *, max_scalar_fields: int = 6) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        scalar_items = [
            _sanitize_result_payload(item)
            for item in value
            if item is None or isinstance(item, str | int | float | bool)
        ]
        if scalar_items:
            return scalar_items[:max_scalar_fields]
        return {"count": len(value)}
    if not isinstance(value, dict):
        return None

    sanitized = _sanitize_result_payload(value)
    if not isinstance(sanitized, dict):
        return None

    compacted: dict[str, Any] = {}
    for key in _ENTITY_REFERENCE_PREFERRED_KEYS:
        if key not in sanitized:
            continue
        current_value = sanitized.get(key)
        if current_value is None or isinstance(current_value, str | int | float | bool):
            compacted[key] = current_value
        elif isinstance(current_value, list):
            compacted[key] = _compact_entity_reference(current_value, max_scalar_fields=max_scalar_fields)
        if len(compacted) >= max_scalar_fields:
            return compacted

    for key, current_value in sanitized.items():
        normalized_key = str(key).strip()
        if not normalized_key or normalized_key in compacted:
            continue
        if current_value is None or isinstance(current_value, str | int | float | bool):
            compacted[normalized_key] = current_value
        elif isinstance(current_value, list):
            compacted[normalized_key] = _compact_entity_reference(current_value, max_scalar_fields=max_scalar_fields)
        if len(compacted) >= max_scalar_fields:
            break

    return compacted or None


def _compact_validation_errors(value: Any, *, max_items: int = 3) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    compacted: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        payload: dict[str, Any] = {}
        loc = item.get("loc")
        if isinstance(loc, list | tuple):
            payload["loc"] = [str(part) for part in list(loc)[:6]]
        elif loc is not None:
            payload["loc"] = [str(loc)]
        msg = str(item.get("msg") or "").strip()
        if msg:
            payload["msg"] = msg
        error_type = str(item.get("type") or "").strip()
        if error_type:
            payload["type"] = error_type
        if payload:
            compacted.append(payload)
        if len(compacted) >= max_items:
            break
    return compacted or None


def summarize_action_execution(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None

    sanitized = _sanitize_result_payload(result)
    if not isinstance(sanitized, dict):
        return None

    payload: dict[str, Any] = {}
    for key in ("actionType", "success", "message"):
        if key in sanitized:
            payload[key] = sanitized.get(key)

    raw_result = sanitized.get("result")
    if not isinstance(raw_result, dict):
        return payload or None

    summarized_result: dict[str, Any] = {}
    if isinstance(raw_result.get("queryContext"), dict):
        summarized_result["queryContext"] = _sanitize_result_payload(raw_result.get("queryContext"))
    compact_validation_errors = _compact_validation_errors(raw_result.get("validationErrors"))
    if compact_validation_errors:
        summarized_result["validationErrors"] = compact_validation_errors
    if isinstance(raw_result.get("items"), list) and "queryContext" not in summarized_result:
        summarized_result["itemCount"] = len(raw_result.get("items") or [])

    for key, value in raw_result.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        lower_key = normalized_key.lower()
        if lower_key in _RESULT_SUMMARY_SKIP_KEYS:
            continue
        compacted_value = _compact_entity_reference(value)
        if compacted_value is None:
            continue
        summarized_result[normalized_key] = compacted_value

    if summarized_result:
        payload["result"] = summarized_result
    return payload or None


def _wrap_internal_block(tag: str, payload: dict[str, Any]) -> str:
    return f"[{tag}]{json.dumps(payload, ensure_ascii=False)}[/{tag}]"


def build_action_history_suffix(action: dict[str, Any] | None) -> str:
    normalized = normalize_assistant_action(action)
    if not normalized:
        return ""
    payload = {
        "assistantAction": normalized,
    }
    return "\n" + _wrap_internal_block(_ACTION_STATE_BLOCK_TAG, payload)


def build_action_execution_history_suffix(result: dict[str, Any] | None) -> str:
    payload = summarize_action_execution(result)
    if not isinstance(payload, dict):
        return ""
    return "\n" + _wrap_internal_block(_ACTION_RESULT_BLOCK_TAG, payload)
