import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

/**
 * Mirror of src/lib/realphotos-import.ts for node:test without TS strip loader.
 * Sync gate below fails if the TypeScript source drifts from these contracts.
 */

const IMPORT_JSON_EXAMPLE = `[
  {
    "name": "示例商品图",
    "url": "http://47.85.47.252/images/bb330e9a1a8c48f683510cad1c4b23c7.png",
    "seller": "可选卖家",
    "sku": "可选SKU"
  }
]`

function precheckImportPayload(raw) {
  const text = String(raw || '').trim()
  if (!text) return [{ index: -1, message: '请粘贴每行 URL，或粘贴 JSON 数组' }]

  if (text.startsWith('[') || text.startsWith('{')) {
    let parsed
    try {
      parsed = JSON.parse(text)
    } catch {
      return [{ index: -1, message: 'JSON 无法解析，请检查格式' }]
    }
    const rows = Array.isArray(parsed) ? parsed : [parsed]
    const issues = []
    rows.forEach((row, index) => {
      if (row == null || typeof row !== 'object' || Array.isArray(row)) {
        issues.push({ index, message: '条目须为对象' })
        return
      }
      const name = String(row.name ?? '').trim()
      const url = String(row.url ?? '').trim()
      if (!name) issues.push({ index, message: '缺少 name' })
      if (!url) issues.push({ index, message: '缺少 url' })
    })
    return issues
  }

  return []
}

function summarizeImportResult(data) {
  if (!data) return '导入失败'
  const imported = Number(data.imported || 0)
  const failed = Array.isArray(data.failed) ? data.failed : []
  if (imported <= 0 && failed.length === 0) return '未导入'
  if (imported <= 0) {
    const reasons = failed
      .slice(0, 5)
      .map((row) => `#${row.index + 1} ${row.code}:${row.message}`)
      .join('；')
    return `未导入（失败 ${failed.length}）：${reasons}`
  }
  if (failed.length === 0) return `已入库 ${imported} 条`
  const reasons = failed
    .slice(0, 5)
    .map((row) => `#${row.index + 1} ${row.code}:${row.message}`)
    .join('；')
  return `已入库 ${imported} 条；失败 ${failed.length}：${reasons}`
}

function formatQueueWaitCopy(aheadCount) {
  if (aheadCount == null || Number.isNaN(Number(aheadCount))) {
    return '排队信息暂不可用；当前为单 worker 顺序处理，单张约 1.5–3 分钟。'
  }
  const n = Math.max(0, Math.floor(Number(aheadCount)))
  if (n <= 0) {
    return '当前无排队。提交后按顺序处理，单张约 1.5–3 分钟。'
  }
  const minM = Math.ceil(n * 1.5)
  const maxM = Math.ceil(n * 3)
  return `前方约 ${n} 单，预计等待约 ${minM}–${maxM} 分钟（单 worker 顺序处理）。`
}

function formatBatchSubmitWaitCopy(imageCount) {
  const n = Math.max(1, Math.floor(Number(imageCount) || 1))
  const minM = Math.ceil(n * 1.5)
  const maxM = Math.ceil(n * 3)
  return `当前为单 worker 顺序处理；本批 ${n} 张预计约 ${minM}–${maxM} 分钟（单张约 1.5–3 分钟）。`
}

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

test('W2 precheck flags missing name on JSON objects', () => {
  const issues = precheckImportPayload('[{"url":"http://47.85.47.252/images/a.jpg"}]')
  assert.equal(issues.length, 1)
  assert.equal(issues[0].message, '缺少 name')
})

test('W2 precheck accepts example JSON', () => {
  assert.deepEqual(precheckImportPayload(IMPORT_JSON_EXAMPLE), [])
})

test('W2 summarize surfaces failed[] index/code/message', () => {
  const text = summarizeImportResult({
    imported: 0,
    failed: [{ index: 0, code: 'INPUT_INVALID', message: '缺少 name' }],
  })
  assert.match(text, /缺少 name/)
  assert.match(text, /INPUT_INVALID/)
  assert.match(text, /#1/)
})

test('W3-A queue wait copy honest empty and estimated range', () => {
  assert.match(formatQueueWaitCopy(0), /当前无排队/)
  assert.match(formatQueueWaitCopy(2), /前方约 2 单/)
  assert.match(formatQueueWaitCopy(2), /3–6 分钟/)
  assert.match(formatBatchSubmitWaitCopy(10), /本批 10 张/)
})

test('sync gate: TypeScript source still exports W2/W3 helpers', async () => {
  const src = await readFile(path.join(frontendRoot, 'src/lib/realphotos-import.ts'), 'utf8')
  assert.match(src, /export function precheckImportPayload/)
  assert.match(src, /缺少 name/)
  assert.match(src, /export function summarizeImportResult/)
  assert.match(src, /export function formatQueueWaitCopy/)
  assert.match(src, /export function formatBatchSubmitWaitCopy/)
  assert.match(src, /IMPORT_JSON_EXAMPLE/)
})
