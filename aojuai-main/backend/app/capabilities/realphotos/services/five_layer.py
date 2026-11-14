"""S2 five-layer pipeline.

Order follows architecture §8.2: L1 → L2 → L3 → L4 EXIF → L5 encode.
If L5 strips the snapshot, the final package restores it and reads it back.
The byte floor is measured only after that last encode and write.
"""

from __future__ import annotations

import io
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.exceptions import BusinessError

PIPELINE_VERSION = "s2-five-layer-3"
PIPELINE_VERSION_BASELINE = "s2-five-layer-2"
ENCODE_PROFILE = "s2-ecommerce-1"
_QUALITIES = (85, 88, 90, 93, 96, 98, 100)
# Q11 复裁：MAD 仅观测（日志/排序参考），不否决参数组、不 fail 端测。
FIDELITY_MAD_MAX = 3.5
FIDELITY_MAD_HARD_MAX = 6.0
FIDELITY_MAD_OBSERVE_ONLY = True
# L2 2D toward legacy effect (Q4/Q8 reopen → allow stronger packs).
_L2_SIGMA = 0.036
_L2_RADIUS = 0.35
_L2_1D_PHASE = 0.0045
_L2_1D_LOW_CUT = 0.05
_L2_1D_HIGH_CUT = 0.45
_L3_SPARSE_MAX = 2500
_L3_SPECTRAL_SIGMA = 0.012
# L1 vignette (Q3) + CA (Q4 reopen) + Layer0 (Q8 reopen).
_VIGNETTE_LEGACY_SCALE = 0.85
_SHARPEN_RADIUS = 0.6
_SHARPEN_PERCENT = 48
_MID_JPEG_QUALITY = 85
_MAD_PREFER_TARGET = 3.0
_ISO_PROCESS_FLOOR = 400.0
_NOISE_INTENSITY = 1.55
_FIXED_MODE_SCALE = 0.85
_LAYER0_OPTICAL_STRENGTH = 0.32
_LAYER0_IMG2IMG_STRENGTH = 0.12
_CA_INTENSITY = 1.15
_SMOOTH_LAP_VAR_THR = 12.0
_AUTO_TIERS_LIGHT: tuple[tuple[float, float, float, float], ...] = (
    (1.00, 0.90, 0.75, 0.85),
    (1.20, 1.10, 0.90, 1.00),
)
_AUTO_TIERS_STRONG: tuple[tuple[float, float, float, float], ...] = (
    (1.25, 1.15, 1.00, 1.10),
    (1.45, 1.35, 1.10, 1.25),
)
_AUTO_TIERS = _AUTO_TIERS_STRONG
_RERANK_PACKS: tuple[tuple[str, float, float, float, float], ...] = (
    ("2d", 0.90, 0.85, 0.55, 0.65),  # milder — avoid artifact regressions
    ("2d", 1.30, 1.25, 1.00, 1.10),
    ("2d", 1.10, 1.55, 0.70, 0.95),  # lighting-weighted vignette
)


@dataclass(frozen=True)
class FiveLayerOutput:
    jpeg: bytes
    fields: list[dict]
    width: int
    height: int
    detector_score: int | None = None
    # Full Gemini (or score_fn) report for the winning pack; C9 measurement.
    detector_report: dict | None = None


def _byte_floor(source: bytes) -> int:
    """S2 T-012 floor: output JPEG bytes >= source_bytes.

    For JPEG uploads, source_bytes is the file length. For non-JPEG sources
    (e.g. generation PNG), comparing to PNG length is not satisfiable by any
    JPEG encode of the same pixels; use quality-100 JPEG of the decoded RGB
    as the comparable floor. Never pad the file to fake compliance.
    """
    if source.startswith(b"\xff\xd8\xff"):
        return len(source)
    with Image.open(io.BytesIO(source)) as image:
        rgb = image.convert("RGB")
    return len(_encode(rgb, quality=100))


def _parse_iso(iso: object) -> float:
    raw = str(iso or "100").strip().split()[0]
    try:
        value = float(raw)
    except ValueError:
        value = 100.0
    return max(50.0, min(value, 6400.0))


def l1_noise_sigma(iso: object) -> float:
    """ISO-linked CMOS-like L1 sigma for s2-five-layer-3.

    Legacy ``isoToNoiseSigma = 0.5*sqrt(ISO/100)`` × ``_NOISE_INTENSITY``, with
    ``_ISO_PROCESS_FLOOR`` so clean ISO100 ecommerce shots still get grain.
    Capped to limit MAD / intentional-blur gaming (Q11).
    """
    value = max(_parse_iso(iso), float(_ISO_PROCESS_FLOOR))
    sigma = 0.5 * math.sqrt(value / 100.0) * float(_NOISE_INTENSITY)
    return float(min(2.20, max(0.85, sigma)))


def aperture_vignette_strength(aperture: object) -> float:
    """Legacy aperture→vignette table × scale (Q3)."""
    try:
        f_number = float(str(aperture or "2.8").strip().removeprefix("f/").removeprefix("F/"))
    except ValueError:
        f_number = 2.8
    if f_number <= 1.4:
        raw = 0.35
    elif f_number <= 2.0:
        raw = 0.28
    elif f_number <= 2.8:
        raw = 0.22
    elif f_number <= 4.0:
        raw = 0.16
    elif f_number <= 5.6:
        raw = 0.10
    elif f_number <= 8.0:
        raw = 0.06
    else:
        raw = 0.04
    return float(raw * float(_VIGNETTE_LEGACY_SCALE))


def focal_length_to_ca_strength(focal_length: object) -> float:
    """Legacy focalLengthToCAStrength (imagePhysicalizer)."""
    try:
        text = str(focal_length or "50").strip().lower().removesuffix("mm")
        value = float(text)
    except ValueError:
        value = 50.0
    if value <= 14:
        return 2.0
    if value <= 24:
        return 1.5
    if value <= 35:
        return 1.0
    if value <= 50:
        return 0.7
    if value <= 85:
        return 0.5
    if value <= 135:
        return 0.4
    return 0.3


def _layer0_optical(arr: np.ndarray, rng: np.random.Generator, *, strength: float) -> np.ndarray:
    """Local Layer0 stand-in (Q8): micro-contrast + fine texture. Not Node img2img."""
    if strength <= 1e-9:
        return arr
    out = np.array(arr, copy=True, dtype=np.float32)
    # 5x5 box blur residual for local contrast (camera-like micro detail).
    pad = np.pad(out, ((2, 2), (2, 2), (0, 0)), mode="edge")
    blur = np.zeros_like(out)
    for dy in range(5):
        for dx in range(5):
            blur += pad[dy : dy + out.shape[0], dx : dx + out.shape[1], :]
    blur /= 25.0
    detail = out - blur
    out = out + float(strength) * detail
    grain = rng.normal(0.0, 0.55 * float(strength), size=out.shape).astype(np.float32)
    out = out + grain
    return np.clip(out, 0, 255)


def _apply_chromatic_aberration(
    arr: np.ndarray, *, focal_length: object, intensity: float = 1.0
) -> np.ndarray:
    """Legacy-inspired R/B channel shift (Q4). Keeps width/height unchanged.

    Does **not** apply the old physicalizer saturation×1.02 fallback (C4 / Q7):
    that path discarded real channel composites and only nudged color.
    """
    ca = float(focal_length_to_ca_strength(focal_length)) * float(intensity) * float(_CA_INTENSITY)
    # Python banker's round(0.5)==0 would skip mid-focal CA; use ceil for measurable shift.
    shift = int(math.ceil(ca * 0.55)) if ca >= 0.35 else 0
    if shift < 1:
        return arr
    image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
    width, height = image.size
    r_ch, g_ch, b_ch = image.split()
    r_big = r_ch.resize((width + 2 * shift, height + 2 * shift), Image.Resampling.BICUBIC)
    r_ch = r_big.crop((shift, shift, shift + width, shift + height))
    inner_w = max(1, width - 2 * shift)
    inner_h = max(1, height - 2 * shift)
    b_small = b_ch.resize((inner_w, inner_h), Image.Resampling.BICUBIC)
    # Fill with mid-gray (128) instead of 0 to avoid black rim MAD spikes (audit C5 note).
    b_canvas = Image.new("L", (width, height), color=128)
    b_canvas.paste(b_small, (shift, shift))
    merged = Image.merge("RGB", (r_ch, g_ch, b_canvas))
    return np.asarray(merged, dtype=np.float32)


# Legacy Layer0 prompts from clone aiImageProcessor.ts DEFAULT_PROMPTS (C1).
# Geometry (barrel distortion) stripped; saturation clauses rewritten per gate 裁决 A.
# action category intentionally omitted (Q7 geometry).
_LAYER0_LEGACY_PROMPTS: dict[str, dict[str, str]] = {
    "phone": {
        "positive": (
            "保留原始画面构图与商品主体完全不变，添加真实智能手机计算摄影直出质感；"
            "仅增加：暗部区域轻微彩色噪点（模拟手机CMOS高感光度噪点）、边缘轻微过锐化白边、"
            "纯色背景轻微色阶断层与降噪涂抹痕迹，色彩统计贴近手机计算摄影直出特征且不进行"
            "可见的全局调色，整体带有计算摄影的轻微过锐与快拍随意感，不改变商品外形、"
            "商标文字与版型。"
        ),
        "negative": (
            "AI生成痕迹，过度平滑，蜡像感，卡通感，单反景深虚化，胶片颗粒，过度降噪，"
            "人工合成感，完美无瑕表面，过度饱和，明显的后期修图痕迹。"
        ),
    },
    "dslr": {
        "positive": (
            "保留原始画面构图与商品主体完全不变，添加真实单反相机拍摄质感，大光圈f/2.8光学景深效果；"
            "仅增加：暗部轻微亮度噪点颗粒（模拟高ISO真实噪点）、高光边缘细微紫边与轴向色差、"
            "画面四角自然暗角、微弱柔和的自然阴影变化与局部高光溢出（增强光线真实感），"
            "色彩统计贴近数码相机原生直出特征且不进行可见的全局调色，呈现RAW底片未调色质感，"
            "保证面料纹理锐利清晰、表面保留自然细节，不改变商品外形、商标文字与版型。"
        ),
        "negative": (
            "AI生成痕迹，过度平滑，蜡像感，卡通感，过度锐化，过度降噪，人工合成感，"
            "完美无瑕表面，过度饱和，HDR过度处理，明显的后期修图痕迹。"
        ),
    },
    "mirrorless": {
        "positive": (
            "保留原始画面构图与商品主体完全不变，添加真实无反相机拍摄质感，大光圈f/1.8光学景深效果；"
            "仅增加：暗部轻微亮度噪点颗粒（模拟高ISO真实噪点）、高光边缘细微紫边与轴向色差、"
            "画面四角自然暗角、微弱柔和的自然阴影变化与局部高光溢出（增强光线真实感），"
            "色彩统计贴近数码相机原生直出特征且不进行可见的全局调色，呈现RAW底片未调色质感，"
            "保证面料纹理锐利清晰、表面保留自然细节，不改变商品外形、商标文字与版型。"
        ),
        "negative": (
            "AI生成痕迹，过度平滑，蜡像感，卡通感，过度锐化，过度降噪，人工合成感，"
            "完美无瑕表面，过度饱和，HDR过度处理，明显的后期修图痕迹。"
        ),
    },
}


def _layer0_category_from_preset(preset: dict) -> str:
    """Map preset to phone/dslr/mirrorless. Never returns action (Q7)."""
    for key in ("deviceType", "device_type", "category", "legacyCategory", "legacy_category"):
        raw = str(preset.get(key) or "").strip().lower()
        if raw in {"phone", "dslr", "mirrorless"}:
            return raw
        if raw == "action":
            return "phone"  # refuse action prompts; fall back to phone
        if raw in {"camera"}:
            return "dslr"
    blob = " ".join(
        str(preset.get(k) or "")
        for k in ("brand", "model", "code", "name")
    ).lower()
    if any(tok in blob for tok in ("iphone", "pixel", "xiaomi", "huawei", "oppo", "vivo", "samsung galaxy")):
        return "phone"
    if any(tok in blob for tok in ("sony a", "nikon z", "canon eos r", "mirrorless")):
        return "mirrorless"
    if any(tok in blob for tok in ("canon", "nikon", "dslr")):
        return "dslr"
    return "phone"


def _layer0_prompt_for_preset(preset: dict) -> tuple[str, str, str]:
    """Return (category, prompt_sent_to_api, note). Negative folded into prompt (no API field)."""
    category = _layer0_category_from_preset(preset)
    pack = _LAYER0_LEGACY_PROMPTS[category]
    # aoju /images/edits has no negative_prompt field (supplier_clients.py) — fold in explicitly.
    prompt = (
        f"{pack['positive']}\n\n"
        f"【禁止出现 / avoid】：{pack['negative']}\n"
        "（注：供应商 edits 无独立 negative_prompt 字段，负向语义已并入本正向正文。）"
    )
    note = f"layer0_category={category}; negative_folded_into_positive=true; model=gpt-image-2"
    return category, prompt, note


def _maybe_layer0_img2img(source: bytes, *, preset: dict) -> bytes | None:
    """Supplier img2img Layer0 (Q8). Uses legacy Chinese category prompts (C1).

    Default on when generation key exists; set ALIGN_LAYER0_IMG2IMG=0 to disable.
    Legacy strength does not enter the API (C-STRENGTH-DEAD); optional pixel blend via
    ALIGN_LAYER0_BLEND_ALPHA (default 0.12; ALIGN e2e uses 1.0 to match old full replace).
    """
    from app.core.config import settings

    flag = str(settings.ALIGN_LAYER0_IMG2IMG or "auto").strip().lower()
    if flag in {"0", "false", "off", "no"}:
        return None
    try:
        import asyncio
        import base64

        from app.capabilities.realphotos.services.supplier_clients import (
            generate_images,
            prepare_reference_jpeg,
        )
        from app.capabilities.realphotos.services.supplier_secrets import read_duty_secret
    except Exception:  # noqa: BLE001
        return None
    if not str(read_duty_secret("generation") or "").strip():
        return None
    category, prompt, prompt_note = _layer0_prompt_for_preset(preset)
    with Image.open(io.BytesIO(source)) as image:
        width, height = image.size
    ref = prepare_reference_jpeg(source, max_edge=1280, quality=85)
    try:
        outcome = asyncio.run(
            generate_images(
                model_id="gpt-image-2",
                prompt=prompt,
                width=int(width),
                height=int(height),
                quantity=1,
                reference=ref,
            )
        )
    except Exception:  # noqa: BLE001
        return None
    images = list(outcome.get("images") or [])
    if not images or not images[0].get("raw"):
        return None
    raw = images[0]["raw"]
    if isinstance(raw, str):
        raw = base64.b64decode(raw)
    if not isinstance(raw, (bytes, bytearray)):
        return None
    with Image.open(io.BytesIO(bytes(raw))) as out_img, Image.open(io.BytesIO(source)) as src_img:
        rgb = out_img.convert("RGB")
        if rgb.size != (width, height):
            rgb = rgb.resize((width, height), Image.Resampling.LANCZOS)
        override = str(settings.ALIGN_LAYER0_BLEND_ALPHA or "").strip()
        if override:
            try:
                alpha = float(override)
            except ValueError:
                alpha = float(_LAYER0_IMG2IMG_STRENGTH)
        else:
            alpha = float(_LAYER0_IMG2IMG_STRENGTH)
        alpha = float(max(0.0, min(1.0, alpha)))
        base = src_img.convert("RGB")
        if base.size != (width, height):
            base = base.resize((width, height), Image.Resampling.LANCZOS)
        blended = Image.blend(base, rgb, alpha) if alpha < 1.0 - 1e-9 else rgb
        buf = io.BytesIO()
        blended.save(buf, format="JPEG", quality=95, subsampling=0)
        # C2 observability: stash last success note for callers that care.
        _maybe_layer0_img2img.last_note = (  # type: ignore[attr-defined]
            f"{prompt_note}; blend_alpha={alpha:.3f}; category={category}; ok=1"
        )
        return buf.getvalue()


def mean_abs_delta(before: np.ndarray, after: np.ndarray) -> float:
    """Mean absolute per-channel delta; used by fidelity regression tests."""
    a = np.asarray(before, dtype=np.float32)
    b = np.asarray(after, dtype=np.float32)
    if a.shape != b.shape:
        raise ValueError("shape mismatch")
    return float(np.mean(np.abs(a - b)))


def _l1_noise_sigma_v2(iso: object) -> float:
    """Frozen s2-five-layer-2 curve for baseline comparison."""
    raw = str(iso or "100").strip().split()[0]
    try:
        value = float(raw)
    except ValueError:
        value = 100.0
    value = max(50.0, min(value, 6400.0))
    sigma = 0.40 * math.sqrt(value / 100.0) + 0.70
    return float(min(1.85, max(1.05, sigma)))


def _l1_l3_v2(baseline: np.ndarray, *, seed: int, iso: object = "100") -> np.ndarray:
    """Frozen pixel/FFT path matching s2-five-layer-2 (no vignette/1d/sharpen)."""
    rng = np.random.default_rng(int(seed))
    arr = np.array(baseline, copy=True)
    sigma = _l1_noise_sigma_v2(iso)
    arr += rng.normal(0.0, sigma, size=arr.shape)
    for channel in range(3):
        freq = np.fft.rfft2(arr[:, :, channel])
        height, width = freq.shape
        yy, xx = np.ogrid[:height, :width]
        radius = np.sqrt((yy / max(height, 1)) ** 2 + (xx / max(width, 1)) ** 2)
        mask = radius > 0.35
        delta = rng.normal(0.0, 0.028, size=freq.shape)
        freq = freq * (1.0 + mask * delta)
        arr[:, :, channel] = np.fft.irfft2(freq, s=arr.shape[:2])
    count = min(512, arr.shape[0] * arr.shape[1])
    ys = rng.integers(0, arr.shape[0], size=count)
    xs = rng.integers(0, arr.shape[1], size=count)
    arr[ys, xs, :] += rng.choice(np.array([-1.0, 1.0]), size=(count, 1))
    return np.clip(arr, 0, 255)


def _laplacian_var(arr: np.ndarray) -> float:
    """Rough detail meter; low values → smoother / more AI-flat plates."""
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    # 3x3 Laplacian kernel
    pad = np.pad(gray, 1, mode="edge")
    lap = (
        -pad[:-2, 1:-1]
        - pad[1:-1, :-2]
        - pad[1:-1, 2:]
        - pad[2:, 1:-1]
        + 4.0 * pad[1:-1, 1:-1]
    )
    return float(np.var(lap))


def _pick_v3_pixels(
    baseline: np.ndarray,
    *,
    seed: int,
    iso: object,
    aperture: object,
    focal_length: object,
    requested: str,
) -> tuple[str, np.ndarray]:
    """Q6 dual-path + intensity tiers; ``auto`` prefers stronger packs (MAD observe-only)."""
    mode = str(requested or "auto").strip().lower()
    if mode not in {"2d", "1d", "hybrid", "auto"}:
        mode = "auto"
    if mode != "auto":
        return mode, _l1_l3(
            baseline,
            seed=seed,
            iso=iso,
            aperture=aperture,
            focal_length=focal_length,
            freq_mode=mode,
        )
    smooth = _laplacian_var(baseline) < float(_SMOOTH_LAP_VAR_THR)
    tiers = _AUTO_TIERS_STRONG if smooth else _AUTO_TIERS_LIGHT
    best_mode = "2d"
    best_pixels: np.ndarray | None = None
    best_rank = float("inf")
    for candidate in ("2d", "1d"):
        for noise_m, vig_m, l2_m, sparse_m in tiers:
            pixels = _l1_l3(
                baseline,
                seed=seed,
                iso=iso,
                aperture=aperture,
                focal_length=focal_length,
                freq_mode=candidate,
                noise_mult=noise_m,
                vignette_mult=vig_m,
                l2_mult=l2_m,
                sparse_mult=sparse_m,
            )
            mad = mean_abs_delta(baseline, pixels)
            # Q11 observe-only: MAD is a soft ranking hint, never a veto.
            rank = (
                -float(noise_m) * 0.15
                - float(vig_m) * 0.10
                + abs(mad - _MAD_PREFER_TARGET) * 0.02
                + (0.0 if candidate == "2d" else 0.03)
            )
            if rank < best_rank:
                best_rank = rank
                best_mode = candidate
                best_pixels = pixels
    if best_pixels is None:
        best_mode = "2d"
        best_pixels = _l1_l3(
            baseline,
            seed=seed,
            iso=iso,
            aperture=aperture,
            focal_length=focal_length,
            freq_mode="2d",
        )
    return best_mode, best_pixels


def _finalize_jpeg(
    image: Image.Image,
    *,
    source: bytes,
    preset: dict,
    seed: int,
    width: int,
    height: int,
    qualities: tuple[int, ...],
    mid_q: int | None,
    baseline: np.ndarray,
) -> FiveLayerOutput:
    floor = _byte_floor(source)
    # Intermediate EXIF probe only — do not re-decode into ``work``. A mid-q
    # re-encode irreversibly drops entropy so later q=100 cannot meet a PNG
    # floor measured as q=100 of the original RGB (CI: generation PNG path).
    if mid_q is not None:
        intermediate = _encode(image, quality=int(mid_q))
        _write_and_read(intermediate, preset, seed=int(seed))
    # Prefer encodes with MAD ≤ hard; still return byte-floor-OK if all over (noise fixtures).
    ranked: list[tuple[float, bytes, list[dict]]] = []
    for quality in qualities:
        encoded = _encode(image, quality=int(quality))
        final, fields = _write_and_read(encoded, preset, seed=int(seed))
        if len(final) >= floor and _same_size(final, width=width, height=height):
            with Image.open(io.BytesIO(final)) as after:
                mad = mean_abs_delta(baseline, np.asarray(after.convert("RGB"), dtype=np.float32))
            ranked.append((float(mad), final, fields))
    if not ranked:
        raise BusinessError(
            message="无法同时满足 JPEG 与字节下限",
            code="OUTPUT_CONSTRAINT_UNSATISFIED",
        )
    ranked.sort(key=lambda row: (0 if row[0] <= FIDELITY_MAD_HARD_MAX else 1, row[0]))
    _mad, final, fields = ranked[0]
    return FiveLayerOutput(jpeg=final, fields=fields, width=width, height=height, detector_score=None)


def _pixels_to_output(
    pixels: np.ndarray,
    *,
    source: bytes,
    preset: dict,
    seed: int,
    baseline: np.ndarray,
    width: int,
    height: int,
    mid_q: int | None = None,
    qualities: tuple[int, ...] | None = None,
    sharpen: bool = True,
) -> FiveLayerOutput:
    if pixels.shape[0] != height or pixels.shape[1] != width:
        raise BusinessError(message="五层改变了宽高", code="OUTPUT_CONSTRAINT_UNSATISFIED")
    image = Image.fromarray(pixels.astype(np.uint8), mode="RGB")
    if sharpen:
        image = _weak_sharpen(image)
    return _finalize_jpeg(
        image,
        source=source,
        preset=preset,
        seed=int(seed),
        width=width,
        height=height,
        qualities=qualities or _QUALITIES,
        mid_q=int(_MID_JPEG_QUALITY) if mid_q is None else mid_q,
        baseline=baseline,
    )


def _output_mad(baseline: np.ndarray, jpeg: bytes) -> float:
    with Image.open(io.BytesIO(jpeg)) as after:
        return mean_abs_delta(baseline, np.asarray(after.convert("RGB"), dtype=np.float32))


def run_five_layer(
    *,
    source: bytes,
    preset: dict,
    seed: int,
    freq_mode: str = "auto",
    algorithm: str = "v3",
    score_fn: object | None = None,
) -> FiveLayerOutput:
    """Run L1–L5 and return the final JPEG plus the EXIF field ledger.

    freq_mode: ``auto`` (default; pick 2d vs 1d × intensity by MAD prefer) | ``2d`` |
    ``1d`` | ``hybrid`` (2D then 1D for dual-path evidence; not claimed Node-equivalent).

    algorithm: ``v3`` (default) or ``v2`` frozen baseline pixel path for score deltas.

    score_fn: optional ``callable(jpeg_bytes) -> dict`` with ``total_score``; when set on
    v3/auto, builds a few packs and keeps the highest Gemini score (Q1).
    """
    work_source = source
    algo = str(algorithm or "v3").strip().lower()
    requested = str(freq_mode or "auto").strip().lower()
    # Layer0 img2img once on production/auto path; skip for dual-path 2d/1d/hybrid evidence.
    if algo != "v2" and requested in {"", "auto"}:
        img2 = _maybe_layer0_img2img(source, preset=preset)
        if img2 is not None:
            work_source = img2
    baseline = _decode_baseline(work_source)
    # Byte floor / size constraints still keyed to the original upload bytes.
    height, width = int(baseline.shape[0]), int(baseline.shape[1])
    with Image.open(io.BytesIO(source)) as src_img:
        src_w, src_h = src_img.size
    if (width, height) != (src_w, src_h):
        # Keep contract: never change output geometry vs original source.
        baseline = np.asarray(
            Image.fromarray(baseline.astype(np.uint8), mode="RGB").resize(
                (src_w, src_h), Image.Resampling.LANCZOS
            ),
            dtype=np.float32,
        )
        height, width = src_h, src_w
    if algo == "v2":
        pixels = _l1_l3_v2(baseline, seed=int(seed), iso=preset.get("iso"))
        return _pixels_to_output(
            pixels,
            source=source,
            preset=preset,
            seed=int(seed),
            baseline=baseline,
            width=width,
            height=height,
            mid_q=90,
            qualities=(90, 93, 96, 98, 100),
            sharpen=False,
        )

    focal = preset.get("focalLength") or preset.get("focal_length") or "50mm"
    if requested != "auto":
        mode = requested if requested in {"2d", "1d", "hybrid"} else "2d"
        pixels = _l1_l3(
            baseline,
            seed=int(seed),
            iso=preset.get("iso"),
            aperture=preset.get("aperture"),
            focal_length=focal,
            freq_mode=mode,
        )
        return _pixels_to_output(
            pixels,
            source=source,
            preset=preset,
            seed=int(seed),
            baseline=baseline,
            width=width,
            height=height,
        )

    _chosen, auto_pixels = _pick_v3_pixels(
        baseline,
        seed=int(seed),
        iso=preset.get("iso"),
        aperture=preset.get("aperture"),
        focal_length=focal,
        requested="auto",
    )
    auto_out = _pixels_to_output(
        auto_pixels,
        source=source,
        preset=preset,
        seed=int(seed),
        baseline=baseline,
        width=width,
        height=height,
    )
    if score_fn is None or not callable(score_fn):
        return auto_out

    candidates: list[FiveLayerOutput] = [auto_out]
    for mode, n_m, v_m, l_m, s_m in _RERANK_PACKS:
        pixels = _l1_l3(
            baseline,
            seed=int(seed),
            iso=preset.get("iso"),
            aperture=preset.get("aperture"),
            focal_length=focal,
            freq_mode=mode,
            noise_mult=n_m,
            vignette_mult=v_m,
            l2_mult=l_m,
            sparse_mult=s_m,
        )
        candidates.append(
            _pixels_to_output(
                pixels,
                source=source,
                preset=preset,
                seed=int(seed),
                baseline=baseline,
                width=width,
                height=height,
            )
        )

    best = auto_out
    best_score = -1
    best_report: dict | None = None
    for cand in candidates:
        try:
            report = score_fn(cand.jpeg)
            if not isinstance(report, dict):
                continue
            score = int(report.get("total_score", 0))
        except Exception:  # noqa: BLE001 — fall back to auto candidate
            continue
        if score > best_score:
            best_score = score
            best = cand
            best_report = report
    if best_score < 0:
        return best
    return FiveLayerOutput(
        jpeg=best.jpeg,
        fields=best.fields,
        width=best.width,
        height=best.height,
        detector_score=int(best_score),
        detector_report=best_report,
    )


def shutter_seconds(value: str) -> float:
    text = str(value).strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return float(numerator) / float(denominator)
    return float(text)


def apex_shutter_value(seconds: float) -> float:
    """APEX TimeValue = -log2(exposure seconds)."""
    return -math.log2(float(seconds))


def apex_aperture_value(f_number: float) -> float:
    """APEX ApertureValue = 2 * log2(FNumber)."""
    return 2.0 * math.log2(float(f_number))


def _decode_baseline(source: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(source)) as image:
        rgb = image.convert("RGB")
        return np.asarray(rgb, dtype=np.float32)


def _apply_vignette(arr: np.ndarray, *, strength: float) -> np.ndarray:
    """Legacy cos^4 vignette (imagePhysicalizer); strength already Q3-scaled."""
    if strength <= 1e-9:
        return arr
    height, width = arr.shape[:2]
    yy, xx = np.ogrid[:height, :width]
    cy = (height - 1) / 2.0
    cx = (width - 1) / 2.0
    denom = math.sqrt(cy * cy + cx * cx) or 1.0
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2) / denom
    cos4 = np.cos(np.arctan(radius * 1.5)) ** 4
    factor = 1.0 - float(strength) * (1.0 - cos4)
    return arr * factor[..., None]


def _l2_freq_2d(
    arr: np.ndarray, rng: np.random.Generator, *, sigma_mult: float = 1.0
) -> np.ndarray:
    out = np.array(arr, copy=True)
    sigma = float(_L2_SIGMA) * float(sigma_mult)
    for channel in range(3):
        freq = np.fft.rfft2(out[:, :, channel])
        height, width = freq.shape
        yy, xx = np.ogrid[:height, :width]
        radius = np.sqrt((yy / max(height, 1)) ** 2 + (xx / max(width, 1)) ** 2)
        mask = radius > _L2_RADIUS
        delta = rng.normal(0.0, sigma, size=freq.shape)
        freq = freq * (1.0 + mask * delta)
        out[:, :, channel] = np.fft.irfft2(freq, s=out.shape[:2])
    return out


def _l2_freq_1d_luminance(
    arr: np.ndarray, rng: np.random.Generator, *, phase_mult: float = 1.0
) -> np.ndarray:
    """Legacy-inspired row-wise 1D phase perturbation on luminance (every other row)."""
    out = np.array(arr, copy=True, dtype=np.float32)
    # Rec.601 luminance
    luma = 0.299 * out[:, :, 0] + 0.587 * out[:, :, 1] + 0.114 * out[:, :, 2]
    height, width = luma.shape
    low = max(1, int(width * _L2_1D_LOW_CUT))
    high = max(low + 1, int(width * _L2_1D_HIGH_CUT))
    phase_amp = float(_L2_1D_PHASE) * float(phase_mult)
    for y in range(0, height, 2):
        row = luma[y]
        spectrum = np.fft.rfft(row)
        for k in range(low, min(high, spectrum.shape[0])):
            phase_noise = (float(rng.random()) - 0.5) * phase_amp * 2.0 * math.pi
            mag = np.abs(spectrum[k])
            phase = np.angle(spectrum[k]) + phase_noise
            spectrum[k] = mag * np.exp(1j * phase)
        restored = np.fft.irfft(spectrum, n=width)
        delta = restored - row
        # Apply luminance delta proportionally to RGB (no global hue shift).
        out[y, :, 0] += delta
        out[y, :, 1] += delta
        out[y, :, 2] += delta
    return out


def _l3_sparse_and_spectral(
    arr: np.ndarray, rng: np.random.Generator, *, sparse_mult: float = 1.0
) -> np.ndarray:
    out = np.array(arr, copy=True)
    count = min(int(_L3_SPARSE_MAX * float(sparse_mult)), out.shape[0] * out.shape[1])
    ys = rng.integers(0, out.shape[0], size=count)
    xs = rng.integers(0, out.shape[1], size=count)
    out[ys, xs, :] += rng.choice(np.array([-1.0, 1.0]), size=(count, 1))
    # Very weak non-geometric spectral ripple (Q7); no rotation/crop/visible recolor.
    for channel in range(3):
        freq = np.fft.rfft2(out[:, :, channel])
        height, width = freq.shape
        yy, xx = np.ogrid[:height, :width]
        radius = np.sqrt((yy / max(height, 1)) ** 2 + (xx / max(width, 1)) ** 2)
        mask = radius > 0.60
        delta = rng.normal(0.0, _L3_SPECTRAL_SIGMA, size=freq.shape)
        freq = freq * (1.0 + mask * delta)
        out[:, :, channel] = np.fft.irfft2(freq, s=out.shape[:2])
    return out


def _l1_l3(
    baseline: np.ndarray,
    *,
    seed: int,
    iso: object = "100",
    aperture: object = "f/2.8",
    focal_length: object = "50mm",
    freq_mode: str = "hybrid",
    noise_mult: float = 1.0,
    vignette_mult: float = 1.0,
    l2_mult: float = 1.0,
    sparse_mult: float = 1.0,
    layer0: bool = True,
) -> np.ndarray:
    rng = np.random.default_rng(int(seed))
    arr = np.array(baseline, copy=True, dtype=np.float32)
    mode = str(freq_mode or "hybrid").strip().lower()
    if mode not in {"2d", "1d", "hybrid"}:
        mode = "hybrid"
    n_m = float(noise_mult)
    v_m = float(vignette_mult)
    l_m = float(l2_mult)
    s_m = float(sparse_mult)
    if (
        abs(n_m - 1.0) < 1e-9
        and abs(v_m - 1.0) < 1e-9
        and abs(l_m - 1.0) < 1e-9
        and abs(s_m - 1.0) < 1e-9
    ):
        scale = float(_FIXED_MODE_SCALE)
        n_m = v_m = l_m = s_m = scale
    # Layer0 optical prepass (Q8); optional supplier img2img applied earlier on bytes.
    if layer0:
        arr = _layer0_optical(arr, rng, strength=float(_LAYER0_OPTICAL_STRENGTH))
    # L1 noise + vignette (Q3) + chromatic aberration (Q4). No rotate/crop/resize.
    sigma = l1_noise_sigma(iso) * n_m
    fine = rng.normal(0.0, sigma, size=arr.shape).astype(np.float32)
    coarse = rng.normal(0.0, sigma * 0.85, size=arr.shape).astype(np.float32)
    kernel = np.ones((3, 3), dtype=np.float32) / 9.0
    for ch in range(3):
        pad = np.pad(coarse[:, :, ch], 1, mode="edge")
        acc = np.zeros_like(coarse[:, :, ch])
        for dy in range(3):
            for dx in range(3):
                acc += pad[dy : dy + arr.shape[0], dx : dx + arr.shape[1]] * kernel[dy, dx]
        coarse[:, :, ch] = acc
    noise = 0.65 * fine + 0.35 * coarse
    dark = arr < 64.0
    noise = np.where(dark, noise * 1.5, noise)
    arr = arr + noise
    vig = aperture_vignette_strength(aperture) * v_m
    arr = _apply_vignette(arr, strength=vig)
    arr = _apply_chromatic_aberration(arr, focal_length=focal_length, intensity=1.0)
    if mode in {"2d", "hybrid"}:
        arr = _l2_freq_2d(arr, rng, sigma_mult=l_m)
    if mode in {"1d", "hybrid"}:
        arr = _l2_freq_1d_luminance(arr, rng, phase_mult=l_m)
    arr = _l3_sparse_and_spectral(arr, rng, sparse_mult=s_m)
    return np.clip(arr, 0, 255)


def _weak_sharpen(image: Image.Image) -> Image.Image:
    """Weak unsharp (Q5). Pre-blur omitted — it blew MAD past hard cap on smooth plates."""
    from PIL import ImageFilter

    return image.filter(
        ImageFilter.UnsharpMask(
            radius=float(_SHARPEN_RADIUS),
            percent=int(_SHARPEN_PERCENT),
            threshold=2,
        )
    )


def _encode(image: Image.Image, *, quality: int) -> bytes:
    buf = io.BytesIO()
    image.save(
        buf,
        format="JPEG",
        quality=int(quality),
        subsampling=0,
        optimize=False,
    )
    return buf.getvalue()


def _same_size(jpeg: bytes, *, width: int, height: int) -> bool:
    with Image.open(io.BytesIO(jpeg)) as image:
        return image.size == (int(width), int(height)) and image.mode == "RGB"


def _f_number(aperture: str) -> float:
    return float(str(aperture).strip().removeprefix("f/").removeprefix("F/"))


_EXIF_REQUIRED: tuple[tuple[str, str], ...] = (
    ("brand", "品牌"),
    ("model", "型号"),
    ("iso", "ISO"),
    ("shutter", "快门"),
    ("aperture", "光圈"),
    ("focalLength", "焦距"),
)

# Empty / placeholder values must not become exiftool `-Tag=` writes.
_EMPTY_MARKERS = frozenset({"", "-", "—", "n/a", "na", "null", "none", "undefined"})
# Coded EXIF enums: write with Tag#=N so PrintConv does not reject raw numbers.
_NUMERIC_EXIF_TAGS = frozenset(
    {
        "WhiteBalance",
        "Flash",
        "LightSource",
        "MeteringMode",
        "ExposureMode",
        "ExposureProgram",
        "SceneCaptureType",
        "FocalPlaneResolutionUnit",
        "FocalLengthIn35mmFormat",
        "MaxApertureValue",
        "FocalPlaneXResolution",
        "FocalPlaneYResolution",
    }
)


def _is_empty_param(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    return text.lower() in _EMPTY_MARKERS


def _legacy_parameters(preset: dict) -> dict:
    raw = preset.get("legacyParameters")
    return dict(raw) if isinstance(raw, dict) else {}


def _param(preset: dict, *keys: str) -> object | None:
    """First non-empty value from top-level preset or legacyParameters."""
    legacy = _legacy_parameters(preset)
    for key in keys:
        if key in preset and not _is_empty_param(preset.get(key)):
            return preset.get(key)
        if key in legacy and not _is_empty_param(legacy.get(key)):
            return legacy.get(key)
    return None


def _metering_mode_code(mode: str) -> int | None:
    mapping = {
        "evaluative": 5,
        "center": 2,
        "spot": 3,
        "matrix": 5,
        "average": 1,
        "partial": 6,
        "multi": 5,
        "multi-segment": 5,
        "pattern": 5,
    }
    return mapping.get(mode.strip().lower())


def _exposure_mode_code(mode: str) -> int | None:
    mapping = {"auto": 0, "M": 1, "manual": 1, "bracket": 2}
    if mode in mapping:
        return mapping[mode]
    return mapping.get(mode.strip().lower())


def _flash_code(flash: str) -> int | None:
    lowered = flash.strip().lower()
    if lowered in {"off", "无", "关闭"}:
        return 0
    if lowered in {"on", "fired", "开启"}:
        return 1
    return None


def _exposure_program_code(mode: str) -> int | None:
    mapping = {
        "auto": 2,
        "m": 1,
        "manual": 1,
        "a": 3,
        "s": 4,
        "p": 2,
        "aperture priority": 3,
        "shutter priority": 4,
        "normal program": 2,
    }
    return mapping.get(mode.strip().lower())


def _scene_capture_type(scene: str) -> int | None:
    """Only known EXIF scene codes; unknown non-empty labels are skipped (not forced to 0)."""
    lowered = scene.strip().lower()
    if lowered == "portrait":
        return 2
    if lowered == "landscape":
        return 1
    if lowered == "night":
        return 3
    return None


def _light_source_code(white_balance: str) -> int | None:
    mapping = {
        "auto": 0,
        "daylight": 1,
        "fluorescent": 2,
        "tungsten": 3,
        "flash": 4,
        "shade": 11,
        "cloudy": 10,
    }
    return mapping.get(white_balance.strip().lower())


def optional_exif_assignments(preset: dict) -> list[tuple[str, str]]:
    """Map optional preset params → EXIF tags; skip blanks (do not write empty strings).

    Aligns with legacy exifToolWriter ``if (preset.field)`` guards: absent/empty/placeholder
    values are omitted entirely rather than written as ``-Tag=``.
    """
    out: list[tuple[str, str]] = []

    def add(tag: str, value: object) -> None:
        if _is_empty_param(value):
            return
        out.append((tag, str(value).strip()))

    add("Software", _param(preset, "software"))
    add("Artist", _param(preset, "author"))
    add("Copyright", _param(preset, "copyright"))
    add("LensModel", _param(preset, "lens_model"))
    add("LensMake", _param(preset, "lens_make"))
    add("ImageDescription", _param(preset, "image_description"))

    lens_max = _param(preset, "lens_max_aperture")
    if lens_max is not None:
        try:
            add("MaxApertureValue", float(str(lens_max).strip().removeprefix("f/").removeprefix("F/")))
        except ValueError:
            pass

    focal_equiv = _param(preset, "focal_length_equiv")
    if focal_equiv is not None:
        try:
            equiv_text = str(focal_equiv).strip()
            if equiv_text.lower().endswith("mm"):
                equiv_text = equiv_text[:-2].strip()
            add("FocalLengthIn35mmFormat", int(round(float(equiv_text))))
        except ValueError:
            pass

    fp_x = _param(preset, "focal_plane_x_res")
    fp_y = _param(preset, "focal_plane_y_res")
    if fp_x is None or fp_y is None:
        from app.capabilities.realphotos.services.camera_specs import lookup_camera_spec

        brand = str(preset.get("brand") or _param(preset, "camera_make") or "")
        model = str(preset.get("model") or _param(preset, "camera_model") or "")
        spec = lookup_camera_spec(brand, model)
        if spec is not None:
            fp_x = spec["focal_plane_x_res"]
            fp_y = spec["focal_plane_y_res"]
    if fp_x is not None and fp_y is not None:
        try:
            add("FocalPlaneXResolution", float(fp_x))
            add("FocalPlaneYResolution", float(fp_y))
            unit = _param(preset, "focal_plane_res_unit")
            if unit is not None:
                add("FocalPlaneResolutionUnit", int(float(unit)))
            else:
                add("FocalPlaneResolutionUnit", 2)
        except ValueError:
            pass

    metering = _param(preset, "metering_mode")
    if metering is not None:
        code = _metering_mode_code(str(metering))
        if code is not None:
            add("MeteringMode", code)

    white_balance = _param(preset, "white_balance")
    if white_balance is not None:
        wb = str(white_balance)
        add("WhiteBalance", 0 if wb.strip().lower() == "auto" else 1)
        light = _light_source_code(wb)
        if light is not None:
            add("LightSource", light)

    exposure_mode = _param(preset, "exposure_mode")
    if exposure_mode is not None:
        exp = str(exposure_mode)
        code = _exposure_mode_code(exp)
        if code is not None:
            add("ExposureMode", code)
        program = _exposure_program_code(exp)
        if program is not None:
            add("ExposureProgram", program)

    flash_mode = _param(preset, "flash_mode")
    if flash_mode is not None:
        code = _flash_code(str(flash_mode))
        if code is not None:
            add("Flash", code)

    scene_mode = _param(preset, "scene_mode", "scene_type")
    if scene_mode is not None:
        code = _scene_capture_type(str(scene_mode))
        if code is not None:
            add("SceneCaptureType", code)

    color_space = _param(preset, "color_space")
    if color_space is not None:
        # Core path still writes ColorSpace=sRGB as encode default; optional override only
        # when the preset explicitly carries a value (adobeRGB → Uncalibrated/65535).
        if str(color_space).strip().lower() in {"adobergb", "adobe rgb"}:
            add("ColorSpace", "Uncalibrated")

    return out


def missing_exif_fields(preset: dict) -> list[str]:
    """Return Chinese labels of missing brand/model/exposure fields (R2)."""
    missing: list[str] = []
    for key, label in _EXIF_REQUIRED:
        if not str(preset.get(key) or "").strip():
            missing.append(label)
    return missing


def assert_preset_exif_ready(preset: dict) -> None:
    """Reject submit/save-enable when EXIF required fields are incomplete (R2).

    Does not invent default exposure values.
    """
    missing = missing_exif_fields(preset)
    if missing:
        raise BusinessError(
            message=f"预设缺少必填字段：{'、'.join(missing)}",
            code="PRESET_EXIF_INCOMPLETE",
        )


def _write_and_read(jpeg: bytes, preset: dict, *, seed: int = 0) -> tuple[bytes, list[dict]]:
    from app.capabilities.realphotos.services.gps_write import resolve_gps

    brand = str(preset.get("brand") or "")
    model = str(preset.get("model") or "")
    if not brand or not model:
        raise BusinessError(message="预设缺少品牌或型号", code="EXIF_WRITE_FAILED")
    gps_plan = resolve_gps(preset=preset, seed=int(seed))
    if gps_plan.get("action") == "fail":
        raise BusinessError(message=str(gps_plan.get("reason") or "GPS 写入失败"), code="EXIF_WRITE_FAILED")
    iso = str(preset.get("iso") or "")
    shutter = str(preset.get("shutter") or "")
    aperture = str(preset.get("aperture") or "")
    focal = str(preset.get("focalLength") or "")
    if not iso or not shutter or not aperture or not focal:
        raise BusinessError(message="预设缺少曝光字段", code="EXIF_WRITE_FAILED")
    tv = apex_shutter_value(shutter_seconds(shutter))
    f_number = _f_number(aperture)
    av = apex_aperture_value(f_number)
    requested = {
        "Make": brand,
        "Model": model,
        "ISO": iso,
        "ExposureTime": shutter,
        "FNumber": f"{f_number:.1f}",
        "FocalLength": focal,
        "ColorSpace": "sRGB",
        "ShutterSpeedValue": f"{tv:.6f}",
        "ApertureValue": f"{av:.6f}",
    }
    optional = optional_exif_assignments(preset)
    maker_note = str(preset.get("makerNote") or "").strip()
    # exiftool 13.x rejects ExifIFD:ApertureValue when APEX < 1 (e.g. f/1.4 → ~0.97)
    # with "Must be a positive number"; FNumber remains the writable source of truth.
    write_aperture_value = av >= 1.0 - 1e-9
    with tempfile.TemporaryDirectory(prefix="rp-s2-") as folder:
        path = Path(folder) / "result.jpg"
        path.write_bytes(jpeg)
        command = [
            "exiftool",
            "-overwrite_original",
            f"-Make={requested['Make']}",
            f"-Model={requested['Model']}",
            f"-ISO={requested['ISO']}",
            f"-ExposureTime={requested['ExposureTime']}",
            f"-FNumber={f_number}",
            f"-FocalLength={requested['FocalLength']}",
            "-ColorSpace=sRGB",
            f"-ShutterSpeedValue={tv:.6f}",
            "-GPS:all=",
            "-MakerNote=",
        ]
        if write_aperture_value:
            command.append(f"-ApertureValue={av:.6f}")
        for tag, value in optional:
            # Only non-empty optional params reach here; never emit `-Tag=` blanks.
            if tag in _NUMERIC_EXIF_TAGS:
                command.append(f"-{tag}#={value}")
            else:
                command.append(f"-{tag}={value}")
        if maker_note:
            # PRODUCT-GAP A7：管理员 2026-11-07 授权写入；必须可回读，失败不静默。
            command.append(f"-MakerNote={maker_note}")
        if gps_plan.get("action") == "write":
            lat = float(gps_plan["latitude"])
            lon = float(gps_plan["longitude"])
            alt = float(gps_plan["altitude"])
            lat_ref = "N" if lat >= 0 else "S"
            lon_ref = "E" if lon >= 0 else "W"
            command.extend(
                [
                    f"-GPSLatitude={abs(lat)}",
                    f"-GPSLatitudeRef={lat_ref}",
                    f"-GPSLongitude={abs(lon)}",
                    f"-GPSLongitudeRef={lon_ref}",
                    f"-GPSAltitude={abs(alt)}",
                    f"-GPSAltitudeRef={'0' if alt >= 0 else '1'}",
                ]
            )
        command.append(str(path))
        try:
            written = subprocess.run(command, check=False, capture_output=True)
        except FileNotFoundError as exc:
            raise BusinessError(message="exiftool 不可用", code="EXIF_WRITE_FAILED") from exc
        if written.returncode != 0:
            detail = (written.stderr or written.stdout or b"").decode(errors="replace").strip()
            raise BusinessError(
                message=("EXIF 写入失败" + (f"：{detail[:200]}" if detail else "")),
                code="EXIF_WRITE_FAILED",
            )
        read_tags = [
            "exiftool",
            "-json",
            "-Make",
            "-Model",
            "-ISO",
            "-ExposureTime",
            "-FNumber",
            "-FocalLength",
            "-ColorSpace",
            "-ShutterSpeedValue#",
            "-ApertureValue#",
            "-GPSLatitude#",
            "-GPSLongitude#",
            "-GPSAltitude#",
            "-MakerNote",
        ]
        for tag, _value in optional:
            # Numeric enums were written with Tag#=N; read Tag# so PrintConv
            # labels (e.g. MeteringMode "Spot") do not break equality checks.
            flag = f"-{tag}#" if tag in _NUMERIC_EXIF_TAGS else f"-{tag}"
            if flag not in read_tags:
                read_tags.append(flag)
        read_tags.append(str(path))
        read = subprocess.run(
            read_tags,
            check=False,
            capture_output=True,
        )
        if read.returncode != 0:
            raise BusinessError(message="EXIF 回读失败", code="EXIF_WRITE_FAILED")
        payload = json.loads(read.stdout.decode() or "[]")
        row = payload[0] if payload else {}
        final = path.read_bytes()
    fields = []
    for tag in requested:
        if tag == "ApertureValue":
            fields.append(
                _verified_aperture_value(
                    requested_av=requested["ApertureValue"],
                    requested_fnumber=requested["FNumber"],
                    row=row,
                    wrote_tag=write_aperture_value,
                )
            )
        else:
            fields.append(_verified(tag, requested[tag], row.get(tag)))
    for tag, value in optional:
        fields.append(_verified_optional(tag, value, row.get(tag)))
    fields.append(_gps_field(gps_plan, row))
    maker_read = str(row.get("MakerNote") or "")
    if maker_note:
        maker_ok = maker_note in maker_read or maker_read.strip() == maker_note
        fields.append(
            {
                "tag": "MakerNote",
                "requested": maker_note,
                "written": maker_note,
                "read_back": maker_read,
                "verification_status": "verified" if maker_ok else "failed",
                "reason": "" if maker_ok else "MakerNote 回读与请求不一致",
            }
        )
    else:
        fields.append(
            {
                "tag": "MakerNote",
                "requested": "",
                "written": "",
                "read_back": maker_read,
                "verification_status": "skipped" if not maker_read else "failed",
                "reason": "" if not maker_read else "未授权预设却出现 MakerNote",
            }
        )
    for field in fields:
        if field["tag"] == "GPSLatitude" and field.get("verification_status") == "failed":
            raise BusinessError(message="GPS 回读与请求不一致", code="EXIF_WRITE_FAILED")
        if field["tag"] == "GPSLatitude" and gps_plan.get("action") == "skip" and field["read_back"]:
            raise BusinessError(message="gpsMode 不应写入 GPS", code="EXIF_WRITE_FAILED")
        if field["tag"] == "MakerNote" and field.get("verification_status") == "failed":
            raise BusinessError(
                message=str(field.get("reason") or "MakerNote 写入或回读失败"),
                code="MAKERNOTE_WRITE_FAILED",
            )
        if field["verification_status"] == "failed" and field["tag"] not in {"GPSLatitude", "MakerNote"}:
            raise BusinessError(message=f"{field['tag']} 回读与预设不一致", code="EXIF_WRITE_FAILED")
    if not final.startswith(b"\xff\xd8\xff"):
        raise BusinessError(message="最终文件不是 JPEG", code="OUTPUT_CONSTRAINT_UNSATISFIED")
    return final, fields


def _verified_optional(tag: str, requested: str, read_back: object) -> dict:
    """Verify an optional tag that was intentionally written (non-empty source only)."""
    actual = "" if read_back is None else str(read_back)
    head = actual.split()[0] if actual.split() else actual
    if tag in {"MaxApertureValue", "FocalPlaneXResolution", "FocalPlaneYResolution", "FocalLengthIn35mmFormat"}:
        ok = _close(head, requested) if head else False
    elif tag == "WhiteBalance":
        lowered = actual.strip().lower()
        ok = (
            head == requested
            or actual == requested
            or (requested == "0" and lowered in {"0", "auto"})
            or (requested == "1" and lowered in {"1", "manual"})
        )
    elif tag == "Flash":
        lowered = actual.strip().lower()
        ok = (
            head == requested
            or actual == requested
            or (requested == "0" and ("no" in lowered or "off" in lowered or lowered == "0"))
            or (requested == "1" and ("fired" in lowered or "on" in lowered or lowered == "1"))
        )
    elif tag == "LightSource":
        lowered = actual.strip().lower()
        ok = (
            head == requested
            or actual == requested
            or (requested == "0" and lowered in {"0", "unknown"})
            or (requested == "1" and "daylight" in lowered)
            or (requested == "2" and "fluorescent" in lowered)
            or (requested == "3" and "tungsten" in lowered)
            or (requested == "4" and "flash" in lowered)
            or (requested == "10" and "cloud" in lowered)
            or (requested == "11" and "shade" in lowered)
        )
    elif tag == "FocalPlaneResolutionUnit":
        lowered = actual.strip().lower()
        ok = (
            head == requested
            or actual == requested
            or (requested == "2" and ("inch" in lowered or lowered == "2"))
            or (requested == "3" and ("cm" in lowered or "centimeter" in lowered or lowered == "3"))
        )
    elif tag in {"MeteringMode", "ExposureMode", "ExposureProgram", "SceneCaptureType"}:
        # Prefer numeric equality (Tag# readback). Keep PrintConv aliases for
        # defense if a caller still supplies human-readable read_back.
        lowered = actual.strip().lower()
        aliases: dict[str, dict[str, tuple[str, ...]]] = {
            "MeteringMode": {
                "1": ("average",),
                "2": ("center-weighted average", "center"),
                "3": ("spot",),
                "4": ("multi-spot",),
                "5": ("multi-segment", "pattern", "matrix", "evaluative"),
                "6": ("partial",),
            },
            "ExposureMode": {
                "0": ("auto",),
                "1": ("manual",),
                "2": ("auto bracket", "bracket"),
            },
            "ExposureProgram": {
                "1": ("manual",),
                "2": ("program ae", "program", "normal program"),
                "3": ("aperture-priority ae", "aperture priority", "aperture-priority"),
                "4": ("shutter speed priority ae", "shutter priority", "shutter-priority"),
            },
            "SceneCaptureType": {
                "0": ("standard",),
                "1": ("landscape",),
                "2": ("portrait",),
                "3": ("night",),
            },
        }
        name_ok = any(alias in lowered for alias in aliases.get(tag, {}).get(requested, ()))
        ok = head == requested or actual == requested or name_ok
    elif tag == "ColorSpace":
        ok = requested.lower() in actual.lower() or actual.lower() in {"uncalibrated", "65535"}
    else:
        ok = bool(actual) and (actual == requested or requested in actual)
    return {
        "tag": tag,
        "requested": requested,
        "written": requested,
        "read_back": actual,
        "verification_status": "verified" if ok else "failed",
        "reason": "" if ok else "回读与请求不一致",
    }


def _gps_field(plan: dict, row: dict) -> dict:
    read_lat = row.get("GPSLatitude")
    read_lon = row.get("GPSLongitude")
    read_alt = row.get("GPSAltitude")
    read_back = ""
    if read_lat not in (None, "") or read_lon not in (None, ""):
        read_back = f"{read_lat},{read_lon},{read_alt}"
    if plan.get("action") == "skip":
        return {
            "tag": "GPSLatitude",
            "requested": "",
            "written": "",
            "read_back": read_back,
            "verification_status": "skipped",
            "reason": str(plan.get("reason") or "未写入 GPS"),
            "gpsMode": plan.get("mode"),
        }
    requested = f"{float(plan['latitude']):.6f},{float(plan['longitude']):.6f},{float(plan['altitude']):.2f}"
    ok = False
    try:
        ok = (
            abs(float(read_lat) - float(plan["latitude"])) < 0.0005
            and abs(float(read_lon) - float(plan["longitude"])) < 0.0005
        )
    except (TypeError, ValueError):
        ok = False
    return {
        "tag": "GPSLatitude",
        "requested": requested,
        "written": requested,
        "read_back": read_back,
        "verification_status": "verified" if ok else "failed",
        "reason": "" if ok else "GPS 回读与请求不一致",
        "gpsMode": plan.get("mode"),
        "actualGps": {
            "latitude": float(plan["latitude"]),
            "longitude": float(plan["longitude"]),
            "altitude": float(plan["altitude"]),
        },
    }


def _verified(tag: str, requested: str, read_back: object) -> dict:
    actual = "" if read_back is None else str(read_back)
    if tag in {"ShutterSpeedValue", "ApertureValue", "FNumber"}:
        ok = _close(actual, requested)
    elif tag == "FocalLength":
        ok = _focal_matches(actual, requested)
    elif tag == "ISO":
        ok = actual.split(".", 1)[0] == requested
    else:
        ok = actual == requested
    return {
        "tag": tag,
        "requested": requested,
        "written": requested,
        "read_back": actual,
        "verification_status": "verified" if ok else "failed",
        "reason": "" if ok else "回读与请求不一致",
    }


def _verified_aperture_value(
    *,
    requested_av: str,
    requested_fnumber: str,
    row: dict,
    wrote_tag: bool,
) -> dict:
    """Verify ApertureValue; fall back to FNumber-derived APEX when tag cannot be stored.

    Some exiftool builds refuse APEX ApertureValue < 1 (large apertures like f/1.4).
    FNumber is always written; deriving AV from a verified FNumber keeps honesty without
    inventing exposure values.
    """
    actual = row.get("ApertureValue")
    if actual is not None and str(actual).strip() != "":
        ok = _close(str(actual), requested_av)
        return {
            "tag": "ApertureValue",
            "requested": requested_av,
            "written": requested_av if wrote_tag else "",
            "read_back": str(actual),
            "verification_status": "verified" if ok else "failed",
            "reason": "" if ok else "回读与请求不一致",
        }
    fn_raw = row.get("FNumber")
    if fn_raw is None or not _close(str(fn_raw), requested_fnumber):
        return {
            "tag": "ApertureValue",
            "requested": requested_av,
            "written": requested_av if wrote_tag else "",
            "read_back": "",
            "verification_status": "failed",
            "reason": "ApertureValue 缺失且 FNumber 回读不可用",
        }
    derived = apex_aperture_value(float(fn_raw))
    ok = _close(f"{derived:.6f}", requested_av)
    return {
        "tag": "ApertureValue",
        "requested": requested_av,
        "written": "derived_from_FNumber",
        "read_back": f"derived:{derived:.6f}",
        "verification_status": "verified" if ok else "failed",
        "reason": (
            ""
            if ok
            else "ApertureValue 无法写入时由 FNumber 推导仍不一致"
        ),
    }


def _close(actual: str, requested: str) -> bool:
    try:
        return abs(float(actual) - float(requested)) < 0.02
    except ValueError:
        return False


def _focal_matches(actual: str, requested: str) -> bool:
    digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in actual).split()
    wanted = "".join(ch if ch.isdigit() or ch == "." else " " for ch in requested).split()
    if not digits or not wanted:
        return False
    return _close(digits[0], wanted[0])
