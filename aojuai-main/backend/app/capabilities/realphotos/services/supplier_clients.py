"""Single-request supplier calls. No retries and no second provider."""

from __future__ import annotations

import base64
import io
import re
from typing import Any

import httpx
from PIL import Image

from app.capabilities.realphotos.services.supplier_secrets import read_duty_secret

GENERATION_BASE = "https://apis.aoju.ai/v1"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
CONFIG_VERSION = "2026-11-11.model-api"


class SupplierCallError(Exception):
    def __init__(self, *, kind: str, status: int | None, content_type: str, detail: str) -> None:
        self.kind = kind
        self.status = status
        self.content_type = content_type
        self.detail = detail
        super().__init__(kind)


def redact(text: str) -> str:
    cleaned = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "sk-redacted", text or "")
    cleaned = re.sub(r"Bearer\s+\S+", "Bearer redacted", cleaned)
    cleaned = re.sub(r"https?://\S+", "url-redacted", cleaned)
    return cleaned[:180]


def _timeout(total: float) -> httpx.Timeout:
    return httpx.Timeout(total, connect=15.0)


def _require_json(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        raise SupplierCallError(
            kind="http_error",
            status=response.status_code,
            content_type=content_type,
            detail=redact(response.text),
        )
    if "json" not in content_type.lower():
        raise SupplierCallError(
            kind="unexpected_content_type",
            status=response.status_code,
            content_type=content_type,
            detail=redact(response.text),
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise SupplierCallError(
            kind="unparseable",
            status=response.status_code,
            content_type=content_type,
            detail="json",
        ) from exc
    if not isinstance(payload, dict):
        raise SupplierCallError(
            kind="unparseable",
            status=response.status_code,
            content_type=content_type,
            detail="object",
        )
    return payload


def prepare_reference_jpeg(data: bytes, *, max_edge: int = 1280, quality: int = 85) -> bytes:
    """Downscale/re-encode reference for supplier transport. Hard-check remains on original bytes."""
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        scale = min(1.0, float(max_edge) / float(max(width, height, 1)))
        if scale < 1.0:
            rgb = rgb.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return buf.getvalue()


def _generation_roots(base_url: str | None) -> str:
    root = str(base_url or GENERATION_BASE).rstrip("/")
    # Allow admins to paste either .../v1 or .../v1/images/generations.
    for suffix in ("/images/generations", "/images/edits"):
        if root.endswith(suffix):
            return root[: -len(suffix)]
    return root


async def generate_images(
    *,
    model_id: str,
    prompt: str,
    width: int,
    height: int,
    quantity: int,
    reference: bytes | None,
    seed: str | int | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    secret = str(api_key or "").strip() or read_duty_secret("generation")
    if not secret:
        raise SupplierCallError(kind="missing_credential", status=None, content_type="", detail="generation")
    root = _generation_roots(base_url)
    size = f"{int(width)}x{int(height)}"
    headers = {"Authorization": f"Bearer {secret}"}
    # Contract gap: seed is not sent and must not be forged as accepted.
    _ = seed
    try:
        # trust_env=False: avoid broken corporate HTTP(S)_PROXY 403 on supplier hosts.
        async with httpx.AsyncClient(timeout=_timeout(180.0), trust_env=False) as client:
            if reference is None:
                response = await client.post(
                    f"{root}/images/generations",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"model": model_id, "prompt": prompt, "n": int(quantity), "size": size},
                )
            else:
                response = await client.post(
                    f"{root}/images/edits",
                    headers=headers,
                    data={"model": model_id, "prompt": prompt, "n": str(int(quantity)), "size": size},
                    files={"image": ("reference.jpg", reference, "image/jpeg")},
                )
    except httpx.TimeoutException as exc:
        raise SupplierCallError(kind="timeout", status=None, content_type="", detail="generation") from exc
    except httpx.HTTPError as exc:
        raise SupplierCallError(kind="transport", status=None, content_type="", detail=type(exc).__name__) from exc
    payload = _require_json(response)
    images = _images_from_payload(payload)
    if reference is None:
        await _inline_urls(images)
    else:
        await _inline_urls(images)
    return {
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "model_id": str(payload.get("model") or model_id),
        "requested_size": size,
        "seed_sent": False,
        "images": images,
    }


async def _inline_urls(images: list[dict[str, Any]]) -> None:
    pending = [item for item in images if item.get("kind") == "url" and item.get("url")]
    if not pending:
        return
    try:
        async with httpx.AsyncClient(timeout=_timeout(60.0), trust_env=False) as client:
            for item in pending:
                response = await client.get(str(item["url"]))
                content_type = response.headers.get("content-type", "")
                if response.status_code >= 400 or not content_type.startswith("image/"):
                    item["kind"] = "failed_url"
                    item["http_status"] = response.status_code
                    item["content_type"] = content_type
                    continue
                item["raw"] = response.content
                item["content_type"] = content_type
    except httpx.TimeoutException as exc:
        raise SupplierCallError(kind="timeout", status=None, content_type="", detail="image_url") from exc
    except httpx.HTTPError as exc:
        raise SupplierCallError(kind="transport", status=None, content_type="", detail=type(exc).__name__) from exc


def _images_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    images: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("b64_json"):
            try:
                raw = base64.b64decode(str(item["b64_json"]), validate=False)
            except (ValueError, TypeError):
                images.append({"kind": "bad_b64"})
                continue
            images.append({"kind": "b64_json", "raw": raw})
        elif item.get("url"):
            images.append({"kind": "url", "url": str(item["url"])})
    return images


def image_size(raw: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(raw)) as image:
        return int(image.size[0]), int(image.size[1])


def _chat_completions_url(base_url: str | None, default: str) -> str:
    text = str(base_url or default).rstrip("/")
    if text.endswith("/chat/completions"):
        return text
    return f"{text}/chat/completions"


async def optimize_text(
    *,
    model_id: str,
    original: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    secret = str(api_key or "").strip() or read_duty_secret("prompt_opt")
    if not secret:
        raise SupplierCallError(kind="missing_credential", status=None, content_type="", detail="prompt_opt")
    endpoint = _chat_completions_url(base_url, DEEPSEEK_URL)
    try:
        async with httpx.AsyncClient(timeout=_timeout(60.0)) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
                json={
                    "model": model_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": "只返回优化后的提示词正文，不要解释，不要写出供应商名称。\n" + original,
                        }
                    ],
                    "stream": False,
                },
            )
    except httpx.TimeoutException as exc:
        raise SupplierCallError(kind="timeout", status=None, content_type="", detail="prompt") from exc
    except httpx.HTTPError as exc:
        raise SupplierCallError(kind="transport", status=None, content_type="", detail=type(exc).__name__) from exc
    payload = _require_json(response)
    text = _message_text(payload)
    if not text:
        raise SupplierCallError(
            kind="empty",
            status=response.status_code,
            content_type=response.headers.get("content-type", ""),
            detail="prompt",
        )
    return {
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "model_id": str(payload.get("model") or model_id),
        "text": text,
    }


def _message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    return ""


async def review_image(
    *,
    model_id: str,
    data: bytes,
    mime: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    secret = str(api_key or "").strip() or read_duty_secret("pre_review")
    if not secret:
        raise SupplierCallError(kind="missing_credential", status=None, content_type="", detail="pre_review")
    endpoint = _chat_completions_url(base_url, DASHSCOPE_URL)
    encoded = base64.b64encode(data).decode("ascii")
    try:
        async with httpx.AsyncClient(timeout=_timeout(90.0)) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
                json={
                    "model": model_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                                {
                                    "type": "text",
                                    "text": "只返回 JSON：{\"verdict\":\"allow\"}、{\"verdict\":\"reject\"} 或 {\"verdict\":\"uncertain\"}。不确定就用 uncertain。",
                                },
                            ],
                        }
                    ],
                    "stream": False,
                },
            )
    except httpx.TimeoutException as exc:
        raise SupplierCallError(kind="timeout", status=None, content_type="", detail="pre_review") from exc
    except httpx.HTTPError as exc:
        raise SupplierCallError(kind="transport", status=None, content_type="", detail=type(exc).__name__) from exc
    payload = _require_json(response)
    verdict = _verdict(_message_text(payload))
    if verdict is None:
        raise SupplierCallError(
            kind="unparseable",
            status=response.status_code,
            content_type=response.headers.get("content-type", ""),
            detail="verdict",
        )
    return {
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "model_id": str(payload.get("model") or model_id),
        "verdict": verdict,
    }


def _verdict(text: str) -> str | None:
    match = re.search(r"allow|reject|uncertain", text or "", flags=re.I)
    if match is None:
        return None
    label = match.group(0).lower()
    if label == "allow":
        return "pass"
    return label
