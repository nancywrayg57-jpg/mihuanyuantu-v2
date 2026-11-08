/**
 * Shared GPS submit guard for batch / single-entry (library→batch) paths (R4).
 * Skip semantics stay honest: incomplete fixed/random may submit with a soft warning.
 */

export type GpsAwarePreset = {
  code: string
  gpsMode?: string
  gpsWritable?: boolean
  gpsWillSkip?: boolean
  gpsWritableReason?: string
}

export type GpsSubmitGuard = {
  blocked: boolean
  skipHint: string
  blockReason: string
}

export function gpsSubmitGuard(preset: GpsAwarePreset | null | undefined): GpsSubmitGuard {
  if (!preset) {
    return { blocked: false, skipHint: '', blockReason: '' }
  }
  const blocked = preset.gpsWritable === false
  const skipHint =
    !blocked &&
    Boolean(preset.gpsWillSkip) &&
    Boolean(preset.gpsMode) &&
    preset.gpsMode !== 'none'
      ? preset.gpsWritableReason ||
        '本预设 GPS 配置不完整，处理时将跳过 GPS 写入（不伪造坐标）'
      : ''
  const blockReason = blocked
    ? preset.gpsWritableReason || '请先在预设台账补全 GPS'
    : ''
  return { blocked, skipHint, blockReason }
}
