"""Gemini Vision final detector. Invalid responses are technical failures, not forged reports."""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request

from app.capabilities.realphotos.services.redo_policy import PASS_SCORE
from app.core.config import settings
from app.core.exceptions import BusinessError

_KEYS = ("noise", "depthOfField", "lighting", "colorRealism", "overallRealism")
_LOG = logging.getLogger(__name__)


def _line(pass_score: int | None) -> int:
    return int(PASS_SCORE if pass_score is None else pass_score)


def prompt_pass_line(pass_score: int | None = None) -> str:
    return f"平台通过线为 total_score ≥ {_line(pass_score)}"


def detection_prompt(pass_score: int | None = None) -> str:
    """Ask the model to align passed with the live pass line. Default line is PASS_SCORE."""
    line = _line(pass_score)
    return (
        "你是图片最终检测器。只返回一个 JSON 对象，不要 Markdown。"
        "键必须是 noise、depthOfField、lighting、colorRealism、overallRealism、total_score、passed、reason。"
        "五个维度和 total_score 都是 0 到 100 的整数。total_score 由你单独给出，不要写成五维平均。"
        "passed 是布尔值。reason 是字符串。"
        f"{prompt_pass_line(line)}："
        f"仅当 total_score ≥ {line} 时 passed 才可为 true；"
        f"若 total_score < {line}，passed 必须为 false，并在 reason 中说明未达 {line}。"
    )


# Default prompt stays aligned with PASS_SCORE (75) when no admin override is passed in.
_PROMPT = detection_prompt()


def parse_gemini_report(payload: str, *, pass_score: int | None = None) -> dict:
    text = str(payload or "").strip()
    if text.lower().startswith("<!doctype") or text.lower().startswith("<html"):
        raise BusinessError(message="检测响应不是 JSON", code="GEMINI_TECHNICAL")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise BusinessError(message="检测响应无法解析", code="GEMINI_TECHNICAL")
    try:
        row = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise BusinessError(message="检测响应无法解析", code="GEMINI_TECHNICAL") from exc
    if not isinstance(row, dict):
        raise BusinessError(message="检测响应无法解析", code="GEMINI_TECHNICAL")
    parsed: dict = {}
    for key in _KEYS:
        parsed[key] = _score(row.get(key), key)
    if "total_score" not in row or isinstance(row.get("total_score"), bool):
        raise BusinessError(message="检测响应缺少总分", code="GEMINI_TECHNICAL")
    parsed["total_score"] = _score(row.get("total_score"), "total_score")
    passed = row.get("passed")
    if not isinstance(passed, bool):
        raise BusinessError(message="检测响应缺少 passed", code="GEMINI_TECHNICAL")
    parsed["passed"] = passed
    parsed["reason"] = "" if row.get("reason") is None else str(row.get("reason"))
    # Soft check only: never rewrite model JSON to fake acceptance (R1).
    line = _line(pass_score)
    if parsed["passed"] is True and int(parsed["total_score"]) < line:
        _LOG.warning(
            "gemini_passed_score_misaligned passed=true total_score=%s pass_score=%s",
            parsed["total_score"],
            line,
        )
    return parsed


def detect_jpeg(
    jpeg: bytes,
    *,
    model_id: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    pass_score: int | None = None,
) -> dict:
    """Call Gemini. Prefer explicit contract args; settings are seed fallback only."""
    key = str(api_key or settings.GEMINI_API_KEY or "").strip()
    model = str(model_id or settings.GEMINI_MODEL or "gemini-3.1-pro-preview").strip()
    if not key or not model:
        raise BusinessError(message="最终检测未配置", code="GEMINI_NOT_CONFIGURED")
    root = str(base_url or settings.GEMINI_API_BASE or "").rstrip("/")
    url = root if root.endswith(":generateContent") else f"{root}/models/{model}:generateContent"
    body = {
        "contents": [
            {
                "parts": [
                    {"text": detection_prompt(pass_score)},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg).decode()}},
                ]
            }
        ],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode()
    except (TimeoutError, urllib.error.URLError) as exc:
        raise BusinessError(message="检测请求失败", code="GEMINI_TECHNICAL") from exc
    if raw.lstrip().startswith("<"):
        raise BusinessError(message="检测响应不是 JSON", code="GEMINI_TECHNICAL")
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BusinessError(message="检测响应无法解析", code="GEMINI_TECHNICAL") from exc
    text = _response_text(envelope)
    report = parse_gemini_report(text, pass_score=pass_score)
    report["detector"] = model
    report["passScoreThreshold"] = _line(pass_score)
    return report


def _score(value: object, name: str) -> int:
    if type(value) is not int:
        raise BusinessError(message=f"检测字段 {name} 不是整数", code="GEMINI_TECHNICAL")
    if value < 0 or value > 100:
        raise BusinessError(message=f"检测字段 {name} 超出 0 到 100", code="GEMINI_TECHNICAL")
    return int(value)


def _response_text(envelope: dict) -> str:
    candidates = envelope.get("candidates") if isinstance(envelope, dict) else None
    if not isinstance(candidates, list) or not candidates:
        raise BusinessError(message="检测响应缺少候选", code="GEMINI_TECHNICAL")
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise BusinessError(message="检测响应缺少正文", code="GEMINI_TECHNICAL")
    texts = [str(part.get("text") or "") for part in parts if isinstance(part, dict)]
    if not any(texts):
        raise BusinessError(message="检测响应缺少正文", code="GEMINI_TECHNICAL")
    return "\n".join(texts)
