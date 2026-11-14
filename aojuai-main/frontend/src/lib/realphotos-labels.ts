/**
 * UX-CN-PRESET: Chinese display labels for realphotos enums.
 * API / DB codes stay English; unknown codes keep the raw value with a Chinese prefix.
 */

function unknown(kind: string, raw: string): string {
  return `未知${kind}（${raw}）`
}

export function originKindLabel(kind: string | null | undefined): string {
  const value = String(kind || '').trim()
  if (!value) return '—'
  const map: Record<string, string> = {
    local_upload: '本地上传',
    text_to_image: '文生图',
    image_to_image: '图生图',
  }
  return map[value] || unknown('来源', value)
}

export function generationModeLabel(mode: string | null | undefined): string {
  return originKindLabel(mode)
}

export function taskStatusLabel(status: string | null | undefined): string {
  const value = String(status || '').trim()
  if (!value) return '—'
  const map: Record<string, string> = {
    SUBMITTED: '已提交',
    PRE_REVIEW: '预审中',
    PRE_REVIEW_PASSED: '预审通过',
    PRE_REVIEW_FAILED: '预审失败',
    FULL_PROCESSING: '处理中',
    DETECTION: '检测中',
    DELIVERED: '已交付',
    FAILED: '失败',
    AUTO_REPROCESS_PENDING: '自动重做待处理',
    stored: '已入库',
    failed: '失败',
    pending: '待处理',
    succeeded: '成功',
    open: '待处理',
    resolved: '已办结',
    closed: '已关闭',
    confirmed: '已确认',
    rejected: '已拒绝',
  }
  return map[value] || unknown('状态', value)
}

export function creditDispositionLabel(value: string | null | undefined): string {
  const raw = String(value || '').trim()
  if (!raw) return '—'
  const map: Record<string, string> = {
    consumed_detection_pass: '检测通过已扣减',
    held_until_tech_support: '技术失败冻结待客服',
    released_tech_audit: '技术客服已释放',
    released_pre_review_reject: '预审拒绝已释放',
    released_precheck: '前置校验失败已释放',
    released_detection_not_passed: '检测未通过已释放',
    held_unresolved_prd_4_5_vs_fr016: '争议冻结（PRD 待裁决）',
    copy_no_reserve_technical: '复制路径技术失败（未预冻）',
    processing: '处理中',
  }
  return map[raw] || unknown('积分处置', raw)
}

export function failureClassLabel(value: string | null | undefined): string {
  const raw = String(value || '').trim()
  if (!raw) return '—'
  const map: Record<string, string> = {
    pre_review: '预审未通过',
    pre_review_failed: '预审请求失败（技术）',
    precheck: '前置校验失败',
    // C1: historical fixture technical — retired for merchant UX; keep distinct from real EXIF/Gemini holds
    technical: '历史联调替身（已停用）',
    fixture_technical: '历史联调替身（已停用）',
    detection_not_passed: '检测未通过',
    detection_failed: '检测失败',
    EXIF_WRITE_FAILED: 'EXIF 写入失败',
    MAKERNOTE_WRITE_FAILED: 'MakerNote 写入失败',
    PRESET_EXIF_INCOMPLETE: '预设 EXIF 字段不完整',
    PRESET_GPS_UNUSABLE: '预设 GPS 不可用',
    OUTPUT_CONSTRAINT_UNSATISFIED: '输出约束未满足',
    GEMINI_FAILED: 'Gemini 检测失败',
    GEMINI_TIMEOUT: 'Gemini 检测超时',
    GEMINI_REJECTED: 'Gemini 未通过',
    GEMINI_TECHNICAL: 'Gemini 检测技术异常',
    GEMINI_NOT_CONFIGURED: '最终检测未配置',
  }
  if (map[raw]) return map[raw]
  if (raw.startsWith('GEMINI_')) return `Gemini 相关（${raw}）`
  return unknown('失败原因', raw)
}

/** F5: prefer detectionMode=technical wording even if failureClass is generic. */
export function failureClassLabelForTask(
  failureClass: string | null | undefined,
  detectionMode?: string | null,
): string {
  const mode = String(detectionMode || '').trim()
  if (mode === 'technical') return failureClassLabel('technical')
  return failureClassLabel(failureClass)
}

export const DETECTION_PASS_SCORE = 75

export function detectionNotPassedExplanation(detection: {
  total_score?: number | null
  passed?: boolean | null
  accepted?: boolean | null
} | null | undefined): string | null {
  if (!detection) return null
  const score = detection.total_score
  if (score == null || Number.isNaN(Number(score))) return null
  const modelHint =
    detection.passed === true
      ? '模型判定为通过，但未达到平台接受分'
      : detection.passed === false
        ? '模型判定为未通过'
        : ''
  return `检测未通过：总分 ${Number(score)}/100，需达到 ${DETECTION_PASS_SCORE} 分才可交付${
    modelHint ? `（${modelHint}）` : ''
  }`
}

/** Prefer snapshot display name over internal preset code. */
export function presetDisplayName(input: {
  presetCode?: string | null
  presetSnapshot?: Record<string, unknown> | null
} | null | undefined): string {
  const snap = input?.presetSnapshot
  if (snap && typeof snap === 'object') {
    const topName = String(snap.name || '').trim()
    if (topName) return topName
    const legacy = snap.legacyParameters
    if (legacy && typeof legacy === 'object') {
      const legacyName = String((legacy as Record<string, unknown>).name || '').trim()
      if (legacyName) return legacyName
    }
    const brand = String(snap.brand || '').trim()
    const model = String(snap.model || '').trim()
    if (brand || model) return [brand, model].filter(Boolean).join(' ')
  }
  const code = String(input?.presetCode || '').trim()
  return code || '—'
}

export function formatByteSizeMb(bytes: number | null | undefined): string {
  const value = Number(bytes)
  if (!Number.isFinite(value) || value < 0) return '—'
  const mb = value / (1024 * 1024)
  if (mb === 0) return '0 Mb'
  if (mb < 0.01) return `${mb.toFixed(3)} Mb`
  if (mb < 10) return `${mb.toFixed(2)} Mb`
  return `${mb.toFixed(1)} Mb`
}

const _REASON_PHRASES: Array<[RegExp, string]> = [
  [/below\s*(the\s*)?pass(ing)?\s*(score|threshold|line)?/i, '未达到平台通过分'],
  [/pass\s*score/i, '通过分'],
  [/total[_\s-]?score/i, '总分'],
  [/not\s+pass(ed)?/i, '未通过'],
  [/failed?/i, '失败'],
  [/noise/i, '噪声'],
  [/depth\s*of\s*field|dof/i, '景深'],
  [/lighting|illumination/i, '光线'],
  [/color\s*realism/i, '色彩真实感'],
  [/overall\s*realism/i, '整体真实感'],
  [/artificial|synthetic|ai[- ]?generated/i, '偏合成/生成感'],
  [/unnatural/i, '不自然'],
]

/** Soft-map common English detector phrases; leave already-Chinese text intact. */
export function detectionReasonChinese(reason: string | null | undefined): string {
  const raw = String(reason || '').trim()
  if (!raw) return ''
  if (/[\u4e00-\u9fff]/.test(raw) && !/[A-Za-z]{4,}/.test(raw)) return raw
  let text = raw
  for (const [pattern, zh] of _REASON_PHRASES) {
    text = text.replace(pattern, zh)
  }
  if (text !== raw) return text
  if (/[\u4e00-\u9fff]/.test(raw)) return raw
  return `检测说明：${raw}`
}

type DetectionScores = {
  noise?: number | null
  depthOfField?: number | null
  lighting?: number | null
  colorRealism?: number | null
  overallRealism?: number | null
  total_score?: number | null
  accepted?: boolean | null
  passed?: boolean | null
  reason?: string | null
}

const _OPT_TIPS: Record<string, string> = {
  noise: '降低过高锐化/颗粒；避免过强 JPEG 压缩，保留更自然的传感器噪声层次',
  depthOfField: '加强景深层次（主体清晰、背景适度虚化），避免整图一样平',
  lighting: '改善光照方向与阴影过渡，减少死黑/死白与不自然打光',
  colorRealism: '收敛过饱和与偏色，让肤色/材质更接近实拍',
  overallRealism: '整体降低「生成感」：减少塑料质感、边缘伪影与构图违和',
}

/** Concrete optimization directions from the weakest detection dimensions. */
export function detectionOptimizationTips(detection: DetectionScores | null | undefined): string[] {
  if (!detection) return []
  const dims: Array<[string, number | null | undefined]> = [
    ['noise', detection.noise],
    ['depthOfField', detection.depthOfField],
    ['lighting', detection.lighting],
    ['colorRealism', detection.colorRealism],
    ['overallRealism', detection.overallRealism],
  ]
  const scored = dims
    .map(([key, value]) => ({ key, value: value == null ? null : Number(value) }))
    .filter((row): row is { key: string; value: number } => row.value != null && !Number.isNaN(row.value))
    .sort((a, b) => a.value - b.value)
  const tips: string[] = []
  for (const row of scored.slice(0, 3)) {
    if (row.value >= DETECTION_PASS_SCORE) continue
    const tip = _OPT_TIPS[row.key]
    if (tip) {
      tips.push(
        `${detectionDimensionLabel(row.key === 'depthOfField' ? 'depth' : row.key === 'colorRealism' ? 'color_realism' : row.key === 'overallRealism' ? 'overall_realism' : row.key)}（${row.value}分）：${tip}`,
      )
    }
  }
  if (tips.length === 0 && detection.accepted === false) {
    tips.push('可换一张更接近实拍的原图，或更换设备预设后重处理后再检')
  }
  return tips
}

/** Combined Chinese reason + optimization block for task detail. */
export function detectionFailureGuidance(detection: DetectionScores | null | undefined): {
  reason: string
  tips: string[]
} {
  const score = detection?.total_score
  const base =
    detectionReasonChinese(detection?.reason) ||
    (score != null
      ? `总分 ${Number(score)}/100，未达到交付所需的 ${DETECTION_PASS_SCORE} 分`
      : '检测未给出具体说明')
  return { reason: base, tips: detectionOptimizationTips(detection) }
}

export function ticketTypeLabel(value: string | null | undefined): string {
  const raw = String(value || '').trim()
  if (!raw) return '—'
  const map: Record<string, string> = {
    account_freeze: '账号冻结',
    image_appeal: '图片申诉',
    order: '订单',
  }
  return map[raw] || unknown('工单类型', raw)
}

export function ticketStatusLabel(value: string | null | undefined): string {
  return taskStatusLabel(value)
}

export function deviceTypeLabel(value: string | null | undefined): string {
  const raw = String(value || '').trim()
  if (!raw) return '—'
  const map: Record<string, string> = {
    phone: '手机',
    dslr: '单反',
    mirrorless: '无反',
    action: '运动相机',
  }
  return map[raw] || unknown('设备类型', raw)
}

export function gpsModeLabel(value: string | null | undefined): string {
  const raw = String(value || '').trim()
  if (!raw) return '—'
  const map: Record<string, string> = {
    none: '不写入',
    fixed: '固定坐标',
    random_by_scene: '按场景随机',
  }
  return map[raw] || unknown('GPS 模式', raw)
}

export function boolPassLabel(value: boolean | null | undefined): string {
  if (value === true) return '通过'
  if (value === false) return '未通过'
  return '—'
}

export function detectionDimensionLabel(key: string): string {
  const map: Record<string, string> = {
    noise: '噪声',
    depth: '景深',
    lighting: '光线',
    color_realism: '色彩真实感',
    overall_realism: '整体真实感',
    total_score: '总分',
    totalScore: '总分',
    passed: '是否通过',
    accepted: '是否接受',
    detector: '检测器',
    reason: '原因',
  }
  return map[key] || key
}
