/**
 * Processed-image size targeter.
 *
 * Goal: keep the final JPEG within 60-80% of the original upload size where
 * feasible, by iteratively re-encoding at decreasing quality. The pipeline
 * may emit a JPEG that is significantly smaller than the original (the
 * platform simulator and AI step both reduce information density), so we
 * also raise quality back up to nudge into the band when needed.
 *
 * EXIF/thumbnail awareness: callers that write EXIF (and a thumbnail) after
 * encoding can pass a `finalize` callback. The optimizer then measures the
 * post-finalize buffer on every iteration, so the returned `finalBytes`
 * matches the bytes the caller will actually ship. Without `finalize` the
 * optimizer measures the raw encoded buffer (legacy behaviour). The audit on
 * commit 598a05a flagged the legacy contract as unsafe for callers that
 * append EXIF after the fact, because the appended bytes can push the actual
 * file past the 80% ceiling even when the optimizer reported in-band.
 *
 * Behavior:
 *   - If original is below MIN_ORIGINAL_BYTES (tiny image), skip targeting
 *     and return the input (post-finalize when `finalize` is provided).
 *     Marked as `tiny-original-skipped` so the caller can surface the
 *     exception.
 *   - If processed is already in [targetLow, targetHigh] * originalBytes
 *     (measured after finalize when provided), accept immediately.
 *   - Otherwise binary-search quality between QUALITY_FLOOR..QUALITY_CEIL
 *     and return the best-effort buffer plus a status flag.
 */

import sharp from 'sharp';

export interface SizeTargetOptions {
  /** Lower band as fraction of original size. Default 0.6. */
  targetLow?: number;
  /** Upper band as fraction of original size. Default 0.8. */
  targetHigh?: number;
  /** Minimum original byte size for targeting to be attempted. Default 40KB. */
  minOriginalBytes?: number;
  /** Lowest JPEG quality we will accept. Default 60. */
  qualityFloor?: number;
  /** Highest JPEG quality we will try when nudging size up. Default 96. */
  qualityCeil?: number;
  /** Initial quality probe. Default 88 (matches platform default). */
  initialQuality?: number;
  /** Maximum search iterations. Default 6 (binary-search has log2 budget). */
  maxIterations?: number;
  /**
   * Optional post-encode step applied to each candidate buffer before
   * measurement (typically EXIF/thumbnail writing). When provided, the
   * optimizer measures the post-finalize buffer, and `buffer`/`finalBytes`
   * in the result describe that finalized buffer — so the caller can upload
   * it directly without a follow-up step that would invalidate the measured
   * size.
   */
  finalize?: (buffer: Buffer) => Promise<Buffer>;
}

export interface SizeTargetResult {
  /** Final JPEG buffer (may equal input if nothing helped). */
  buffer: Buffer;
  /** Final size in bytes. */
  finalBytes: number;
  /** Original size in bytes. */
  originalBytes: number;
  /** Final size as fraction of original. */
  ratio: number;
  /** True if the final buffer lands in [targetLow, targetHigh]. */
  inBand: boolean;
  /** Reason the targeter exited (for logs/tests/UI). */
  reason:
    | 'in-band'
    | 'best-effort'
    | 'tiny-original-skipped'
    | 'already-in-band'
    | 'fallback-input';
  /** JPEG quality used for the final encode (undefined when input was returned as-is). */
  finalQuality?: number;
}

const DEFAULTS = {
  targetLow: 0.6,
  targetHigh: 0.8,
  minOriginalBytes: 40 * 1024,
  qualityFloor: 60,
  qualityCeil: 96,
  initialQuality: 88,
  maxIterations: 6,
} as const;

async function encodeJpeg(buffer: Buffer, quality: number): Promise<Buffer> {
  return sharp(buffer)
    .withMetadata()
    .jpeg({
      quality,
      chromaSubsampling: '4:2:0',
      mozjpeg: false,
      trellisQuantisation: false,
      overshootDeringing: false,
      optimiseScans: false,
    })
    .toBuffer();
}

export async function optimizeImageSize(
  processedBuffer: Buffer,
  originalBytes: number,
  options: SizeTargetOptions = {}
): Promise<SizeTargetResult> {
  const opts = { ...DEFAULTS, ...options };
  const { targetLow, targetHigh, minOriginalBytes, qualityFloor, qualityCeil, initialQuality, maxIterations, finalize } = opts;

  // Sanity-check the band so misconfiguration cannot silently bypass targeting.
  if (!(targetLow > 0 && targetHigh > targetLow && targetHigh <= 1)) {
    throw new Error(`[sizeOptimizer] invalid band: low=${targetLow}, high=${targetHigh}`);
  }

  const applyFinalize = async (buf: Buffer): Promise<Buffer> =>
    finalize ? await finalize(buf) : buf;

  const fallback = (
    reason: SizeTargetResult['reason'],
    buf: Buffer,
    finalQuality?: number,
  ): SizeTargetResult => ({
    buffer: buf,
    finalBytes: buf.byteLength,
    originalBytes,
    ratio: originalBytes > 0 ? buf.byteLength / originalBytes : 0,
    inBand:
      originalBytes > 0 &&
      buf.byteLength / originalBytes >= targetLow &&
      buf.byteLength / originalBytes <= targetHigh,
    reason,
    finalQuality,
  });

  if (originalBytes < minOriginalBytes) {
    // Tiny-original exception still gets finalize applied so the caller can
    // upload the returned buffer directly without a separate finalize step.
    const out = await applyFinalize(processedBuffer);
    return fallback('tiny-original-skipped', out);
  }

  const lowBytes = originalBytes * targetLow;
  const highBytes = originalBytes * targetHigh;

  // Baseline measurement is post-finalize when finalize is provided, so the
  // already-in-band check reflects the bytes the caller will actually ship.
  const baselineBuf = await applyFinalize(processedBuffer);
  const baselineBytes = baselineBuf.byteLength;

  if (baselineBytes >= lowBytes && baselineBytes <= highBytes) {
    return fallback('already-in-band', baselineBuf);
  }

  // Binary search the JPEG quality that lands within the band. We re-encode
  // from the processed buffer each iteration (rather than chaining encodes)
  // to avoid compounding quality loss.
  let lo = qualityFloor;
  let hi = qualityCeil;
  let bestBuf = baselineBuf;
  let bestBytes = baselineBytes;
  let bestQuality: number | undefined;
  let bestDelta = Math.min(
    Math.abs(baselineBytes - lowBytes),
    Math.abs(baselineBytes - highBytes),
  );

  let q = Math.max(qualityFloor, Math.min(qualityCeil, initialQuality));

  for (let i = 0; i < maxIterations; i++) {
    let candidate: Buffer;
    try {
      const encoded = await encodeJpeg(processedBuffer, q);
      candidate = await applyFinalize(encoded);
    } catch {
      // sharp/finalize can refuse exotic inputs; give up gracefully with the
      // best buf so far.
      break;
    }
    const candBytes = candidate.byteLength;

    if (candBytes >= lowBytes && candBytes <= highBytes) {
      return {
        buffer: candidate,
        finalBytes: candBytes,
        originalBytes,
        ratio: candBytes / originalBytes,
        inBand: true,
        reason: 'in-band',
        finalQuality: q,
      };
    }

    // Track the best (closest-to-band) candidate so we can return a best-effort
    // result when the search exhausts.
    const delta =
      candBytes < lowBytes ? lowBytes - candBytes : candBytes - highBytes;
    if (delta < bestDelta) {
      bestDelta = delta;
      bestBuf = candidate;
      bestBytes = candBytes;
      bestQuality = q;
    }

    if (candBytes > highBytes) {
      // Too large -> need lower quality
      hi = q - 1;
    } else {
      // Too small -> need higher quality
      lo = q + 1;
    }
    if (lo > hi) break;
    q = Math.floor((lo + hi) / 2);
  }

  return {
    buffer: bestBuf,
    finalBytes: bestBytes,
    originalBytes,
    ratio: bestBytes / originalBytes,
    inBand: false,
    reason: 'best-effort',
    finalQuality: bestQuality,
  };
}
