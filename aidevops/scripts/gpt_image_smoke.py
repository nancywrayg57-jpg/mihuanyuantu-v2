#!/usr/bin/env python3
"""Smoke-test OpenAI image generation and Responses relay behavior.

Reads .env-style files supporting both KEY=value and KEY: value. Never prints
secret values. Writes a PNG or JSON response plus one JSON report.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


KEY_ALIASES = ("OPENAI_API_KEY", "apikey", "API_KEY")
BASE_URL_ALIASES = ("OPENAI_BASE_URL", "baseurl", "BASE_URL")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*([=:])\s*(.*)$", line)
        if not match:
            continue
        key, _, value = match.groups()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def pick(values: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        if os.environ.get(alias):
            return os.environ[alias]
        if values.get(alias):
            return values[alias]
    return None


def normalize_base_url(base_url: str | None) -> str:
    if not base_url:
        return "https://api.openai.com/v1"
    url = base_url.rstrip("/")
    if url.endswith("/images/generations"):
        return url[: -len("/images/generations")]
    if not url.endswith("/v1"):
        url = url + "/v1"
    return url


def response_input(text: str, image_paths: list[Path] | None = None) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
    for path in image_paths or []:
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        content.append({"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}"})
    return [{"role": "user", "content": content}]


def request_image(
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    size: str,
    quality: str | None,
    timeout: int,
    user_agent: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if quality:
        payload["quality"] = quality

    req = urllib.request.Request(
        f"{base_url}/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def request_models(
    *,
    api_key: str,
    base_url: str,
    timeout: int,
    user_agent: str,
) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{base_url}/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def parse_sse_response(raw: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if not data or data == "[DONE]":
            continue
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    completed = next((e for e in reversed(events) if e.get("type") == "response.completed"), None)
    if completed and isinstance(completed.get("response"), dict):
        return {"events": events, **completed["response"]}
    return {"events": events}


def decode_response_body(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return parse_sse_response(raw)
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def request_responses(
    *,
    api_key: str,
    base_url: str,
    payload: dict[str, Any],
    timeout: int,
    user_agent: str,
    originator: str | None = None,
) -> tuple[dict[str, Any], str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": user_agent,
    }
    if originator:
        headers["originator"] = originator
    req = urllib.request.Request(
        f"{base_url}/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return decode_response_body(body), body


def iter_response_images(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        result = value.get("result")
        if isinstance(result, str) and len(result) > 100:
            found.append(result)
        b64_json = value.get("b64_json")
        if isinstance(b64_json, str) and len(b64_json) > 100:
            found.append(b64_json)
        for child in value.values():
            found.extend(iter_response_images(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(iter_response_images(child))
    return found


def write_image(response: dict[str, Any], output: Path) -> str:
    data = response.get("data") or []
    if not data:
        raise RuntimeError("Image API response contained no data entries")
    first = data[0]
    if "b64_json" in first:
        raw = base64.b64decode(first["b64_json"])
        output.write_bytes(raw)
        return "b64_json"
    if "url" in first:
        with urllib.request.urlopen(first["url"], timeout=120) as image_response:
            output.write_bytes(image_response.read())
        return "url"
    raise RuntimeError("Image API response had neither b64_json nor url")


def png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:32]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def collect_image_metadata(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        item_type = value.get("type")
        if item_type in {"image_generation_call", "image_generation.completed"} or "b64_json" in value:
            meta: dict[str, Any] = {}
            for key in ("type", "model", "quality", "size", "output_format", "id"):
                if key in value:
                    meta[key] = value[key]
            if meta:
                found.append(meta)
        for child in value.values():
            found.extend(collect_image_metadata(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(collect_image_metadata(child))
    return found


def extract_tool_usage(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("tool_usage",):
            if key in value:
                return value[key]
        for child in value.values():
            nested = extract_tool_usage(child)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = extract_tool_usage(child)
            if nested is not None:
                return nested
    return None


def image_tool_usage_present(tool_usage: Any) -> bool:
    if not isinstance(tool_usage, dict):
        return False
    return tool_usage.get("image_gen") is not None


def has_positive_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, dict):
        return any(has_positive_number(child) for child in value.values())
    if isinstance(value, list):
        return any(has_positive_number(child) for child in value)
    return False


def image_tool_usage_detected(tool_usage: Any) -> bool:
    if not isinstance(tool_usage, dict):
        return False
    return has_positive_number(tool_usage.get("image_gen"))


def prompt_with_render_targets(prompt: str, size: str, quality: str | None) -> str:
    quality_text = quality or "auto"
    requirement = (
        f"Target canvas: {size} pixels. Requested image quality: {quality_text}. "
        "Render the mockup at this canvas size and quality as part of the visual brief."
    )
    lowered = prompt.lower()
    if size.lower() in lowered and "quality" in lowered:
        return prompt
    return f"{prompt}\n\n{requirement}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test OpenAI-compatible model, Responses, and image routes.")
    parser.add_argument("--env", default=".env", help="Path to env file")
    parser.add_argument("--outdir", default="tmp/aidevops-image-smoke", help="Output directory")
    parser.add_argument("--model", default="gpt-image-2", help="Image model")
    parser.add_argument("--size", default="1536x1024", help="Image size")
    parser.add_argument("--quality", default="high", help="Optional quality parameter")
    parser.add_argument(
        "--image-action",
        choices=("auto", "generate", "edit"),
        default="generate",
        help="Optional Responses image_generation tool action.",
    )
    parser.add_argument(
        "--partial-images",
        type=int,
        default=None,
        help="Optional partial_images count for Responses image_generation streaming-compatible routes.",
    )
    parser.add_argument("--timeout", type=int, default=180, help="HTTP timeout seconds")
    parser.add_argument(
        "--mode",
        choices=("models", "images", "responses-text", "responses-image-tool", "responses-codex-auto"),
        default="images",
        help="API shape to test",
    )
    parser.add_argument("--text-model", default="gpt-5.4", help="Responses-capable text model")
    parser.add_argument("--user-agent", default="aidevops-image-smoke/0.1", help="HTTP User-Agent")
    parser.add_argument("--originator", default=None, help="Optional originator header")
    parser.add_argument(
        "--reference-image",
        action="append",
        default=[],
        help="Optional local image path to include as an input_image reference in Responses modes.",
    )
    parser.add_argument("--strict-size", action="store_true", help="Fail when returned PNG size differs from --size")
    parser.add_argument(
        "--prompt",
        default=(
            "High-fidelity desktop product UI mockup for an AI-assisted MVP delivery hub. "
            "Show a calm operational SaaS workspace with a left navigation rail, phase "
            "progress timeline, PRD/MVP summary panel, risk and quality gate indicators, "
            "and a focused next-action panel. Use realistic product labels, compact "
            "professional spacing, restrained color accents, legible text, and no lorem "
            "ipsum. Avoid generic monochrome wireframe style, marketing hero layout, "
            "brand logos, and decorative background art."
        ),
        help="Prompt to send to the image API",
    )
    args = parser.parse_args()
    prompt = prompt_with_render_targets(args.prompt, args.size, args.quality)

    env_values = load_env(Path(args.env))
    api_key = pick(env_values, KEY_ALIASES)
    base_url = normalize_base_url(pick(env_values, BASE_URL_ALIASES))

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / ("response.json" if args.mode in {"models", "responses-text"} else "smoke.png")
    report = outdir / "report.json"

    started = time.time()
    safe_report: dict[str, Any] = {
        "model": args.model,
        "mode": args.mode,
        "text_model": args.text_model,
        "size": args.size,
        "quality": args.quality,
        "image_action": args.image_action,
        "partial_images": args.partial_images,
        "user_agent": args.user_agent,
        "originator_detected": bool(args.originator),
        "env_file": str(Path(args.env)),
        "api_key_detected": bool(api_key),
        "base_url_host_detected": bool(base_url),
        "output": str(output),
        "reference_images": [str(Path(path)) for path in args.reference_image],
        "prompt_includes_size": args.size.lower() in prompt.lower(),
        "prompt_includes_quality": "quality" in prompt.lower(),
    }

    if not api_key:
        safe_report["status"] = "missing_api_key"
        report.write_text(json.dumps(safe_report, indent=2), encoding="utf-8")
        print(f"missing_api_key report={report}")
        return 2

    reference_images = [Path(path) for path in args.reference_image]
    for path in reference_images:
        if not path.exists():
            safe_report["status"] = "missing_reference_image"
            safe_report["missing_reference_image"] = str(path)
            report.write_text(json.dumps(safe_report, indent=2), encoding="utf-8")
            print(f"missing_reference_image path={path} report={report}")
            return 2

    try:
        if args.mode == "models":
            response = request_models(
                api_key=api_key,
                base_url=base_url,
                timeout=args.timeout,
                user_agent=args.user_agent,
            )
            output.write_text(json.dumps(response, indent=2), encoding="utf-8")
            response_mode = "models_json"
        elif args.mode == "images":
            safe_report["requested_images_payload"] = {
                "model": args.model,
                "size": args.size,
                "quality": args.quality,
                "n": 1,
            }
            response = request_image(
                api_key=api_key,
                base_url=base_url,
                model=args.model,
                prompt=prompt,
                size=args.size,
                quality=args.quality,
                timeout=args.timeout,
                user_agent=args.user_agent,
            )
            response_mode = write_image(response, output)
        elif args.mode == "responses-text":
            response, raw = request_responses(
                api_key=api_key,
                base_url=base_url,
                payload={
                    "model": args.text_model,
                    "input": response_input("Reply with the exact text: aidevops-ok", reference_images),
                    "stream": False,
                },
                timeout=args.timeout,
                user_agent=args.user_agent,
                originator=args.originator,
            )
            (outdir / "responses-text.raw").write_text(raw, encoding="utf-8")
            output.write_text(json.dumps(response, indent=2), encoding="utf-8")
            response_mode = "responses_json"
        elif args.mode == "responses-image-tool":
            image_tool: dict[str, Any] = {
                "type": "image_generation",
                "model": args.model,
                "size": args.size,
                "output_format": "png",
            }
            if args.quality:
                image_tool["quality"] = args.quality
            if args.image_action:
                image_tool["action"] = args.image_action
            if args.partial_images is not None:
                image_tool["partial_images"] = args.partial_images
            safe_report["requested_image_tool"] = image_tool.copy()
            response, raw = request_responses(
                api_key=api_key,
                base_url=base_url,
                payload={
                    "model": args.text_model,
                    "input": response_input(prompt, reference_images),
                    "stream": False,
                    "tools": [image_tool],
                    "tool_choice": {"type": "image_generation"},
                },
                timeout=args.timeout,
                user_agent=args.user_agent,
                originator=args.originator,
            )
            (outdir / "responses-image-tool.raw").write_text(raw, encoding="utf-8")
            images = iter_response_images(response)
            if not images:
                raise RuntimeError("Responses API returned no image result/b64_json values")
            output.write_bytes(base64.b64decode(images[0]))
            response_mode = "responses_image_tool"
        else:
            response, raw = request_responses(
                api_key=api_key,
                base_url=base_url,
                payload={
                    "model": args.text_model,
                    "input": response_input(prompt, reference_images),
                    "stream": False,
                },
                timeout=args.timeout,
                user_agent=args.user_agent,
                originator=args.originator,
            )
            (outdir / "responses-codex-auto.raw").write_text(raw, encoding="utf-8")
            images = iter_response_images(response)
            if images:
                output.write_bytes(base64.b64decode(images[0]))
                response_mode = "responses_codex_auto_image"
            else:
                output = outdir / "response.json"
                output.write_text(json.dumps(response, indent=2), encoding="utf-8")
                response_mode = "responses_codex_auto_no_image"
        dimensions = png_dimensions(output)
        metadata = collect_image_metadata(response) if "response" in locals() else []
        tool_usage = extract_tool_usage(response) if "response" in locals() else None
        safe_tool_usage = tool_usage if isinstance(tool_usage, (dict, list, str, int, float, bool, type(None))) else str(tool_usage)
        safe_report.update(
            {
                "status": "ok",
                "response_mode": response_mode,
                "elapsed_seconds": round(time.time() - started, 2),
                "bytes": output.stat().st_size,
                "png_dimensions": list(dimensions) if dimensions else None,
                "image_metadata": metadata[:20],
                "tool_usage_detected": tool_usage is not None,
                "image_tool_usage_present": image_tool_usage_present(tool_usage),
                "image_tool_usage_detected": image_tool_usage_detected(tool_usage),
                "tool_usage": safe_tool_usage,
            }
        )
        if args.strict_size and dimensions:
            requested = tuple(int(part) for part in args.size.lower().split("x", 1))
            if dimensions != requested:
                safe_report["status"] = "size_mismatch"
                safe_report["requested_dimensions"] = list(requested)
                report.write_text(json.dumps(safe_report, indent=2), encoding="utf-8")
                print(f"size_mismatch output={output} report={report} actual={dimensions} requested={requested}")
                return 3
        report.write_text(json.dumps(safe_report, indent=2), encoding="utf-8")
        print(f"ok output={output} report={report} bytes={output.stat().st_size}")
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        safe_report.update(
            {
                "status": "http_error",
                "http_status": exc.code,
                "error_body": body[:2000],
                "elapsed_seconds": round(time.time() - started, 2),
            }
        )
        report.write_text(json.dumps(safe_report, indent=2), encoding="utf-8")
        print(f"http_error status={exc.code} report={report}")
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI must report any smoke-test failure.
        safe_report.update(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
                "elapsed_seconds": round(time.time() - started, 2),
            }
        )
        report.write_text(json.dumps(safe_report, indent=2), encoding="utf-8")
        print(f"error type={type(exc).__name__} report={report}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
