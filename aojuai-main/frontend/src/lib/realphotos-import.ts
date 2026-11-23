/** URL/JSON 导入页：校验与结果摘要（与后端 s5_growth 缺 name / failed[] 口径对齐）。 */

export type ImportFailedRow = {
  index: number
  code: string
  message: string
}

export type ImportResult = {
  imported?: number
  failed?: ImportFailedRow[]
  formalSupplier?: boolean
  strategy?: string
  creditsCharged?: number
}

export const IMPORT_JSON_EXAMPLE = `[
  {
    "name": "示例商品图",
    "url": "http://47.85.47.252/images/bb330e9a1a8c48f683510cad1c4b23c7.png",
    "seller": "可选卖家",
    "sku": "可选SKU"
  }
]`

export type ImportPrecheckIssue = {
  index: number
  message: string
}

/** 提交前本地预检：仅对 JSON 对象条目检查 name/url；纯 URL 行跳过。 */
export function precheckImportPayload(raw: string): ImportPrecheckIssue[] {
  const text = String(raw || '').trim()
  if (!text) return [{ index: -1, message: '请粘贴每行 URL，或粘贴 JSON 数组' }]

  if (text.startsWith('[') || text.startsWith('{')) {
    let parsed: unknown
    try {
      parsed = JSON.parse(text)
    } catch {
      return [{ index: -1, message: 'JSON 无法解析，请检查格式' }]
    }
    const rows = Array.isArray(parsed) ? parsed : [parsed]
    const issues: ImportPrecheckIssue[] = []
    rows.forEach((row, index) => {
      if (row == null || typeof row !== 'object' || Array.isArray(row)) {
        issues.push({ index, message: '条目须为对象' })
        return
      }
      const record = row as Record<string, unknown>
      const name = String(record.name ?? '').trim()
      const url = String(record.url ?? '').trim()
      if (!name) issues.push({ index, message: '缺少 name' })
      if (!url) issues.push({ index, message: '缺少 url' })
    })
    return issues
  }

  return []
}

export function summarizeImportResult(data: ImportResult | null | undefined): string {
  if (!data) return '导入失败'
  const imported = Number(data.imported || 0)
  const failed = Array.isArray(data.failed) ? data.failed : []
  if (imported <= 0 && failed.length === 0) return '未导入'
  if (imported <= 0) {
    return `未导入（失败 ${failed.length}）：${formatFailedBrief(failed)}`
  }
  if (failed.length === 0) return `已入库 ${imported} 条`
  return `已入库 ${imported} 条；失败 ${failed.length}：${formatFailedBrief(failed)}`
}

export function formatFailedBrief(failed: ImportFailedRow[], limit = 5): string {
  return failed
    .slice(0, limit)
    .map((row) => `#${Number(row.index) + 1} ${row.message}`)
    .join('；')
}

/** 大批次等待：单张墙钟约 1.5–3 分钟。 */
export const BATCH_WAIT_MINUTES_PER_IMAGE = { min: 1.5, max: 3 } as const

function normalizeConcurrency(raw: number | null | undefined): number {
  const n = Math.floor(Number(raw))
  if (!Number.isFinite(n) || n < 1) return 1
  return Math.min(4, n)
}

export function formatQueueWaitCopy(
  aheadCount: number | null | undefined,
  processConcurrency: number | null | undefined = 1,
): string {
  const concurrency = normalizeConcurrency(processConcurrency)
  if (aheadCount == null || Number.isNaN(Number(aheadCount))) {
    return '排队信息暂不可用；单张约 1.5–3 分钟。'
  }
  const n = Math.max(0, Math.floor(Number(aheadCount)))
  if (n <= 0) {
    return '当前无排队，单张约 1.5–3 分钟。'
  }
  const waves = Math.ceil(n / concurrency)
  const minM = Math.ceil(waves * BATCH_WAIT_MINUTES_PER_IMAGE.min)
  const maxM = Math.ceil(waves * BATCH_WAIT_MINUTES_PER_IMAGE.max)
  return `前方约 ${n} 单，预计等待约 ${minM}–${maxM} 分钟。`
}

export function formatBatchSubmitWaitCopy(
  imageCount: number,
  processConcurrency: number | null | undefined = 1,
): string {
  const concurrency = normalizeConcurrency(processConcurrency)
  const n = Math.max(1, Math.floor(Number(imageCount) || 1))
  const waves = Math.ceil(n / concurrency)
  const minM = Math.ceil(waves * BATCH_WAIT_MINUTES_PER_IMAGE.min)
  const maxM = Math.ceil(waves * BATCH_WAIT_MINUTES_PER_IMAGE.max)
  return `本批 ${n} 张预计约 ${minM}–${maxM} 分钟（单张约 1.5–3 分钟）。`
}
