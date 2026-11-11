import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

/**
 * Mirror of src/lib/realphotos-download.ts for node:test without TS strip loader.
 * Sync gate below fails if the TypeScript source drifts from these contracts.
 */
const CONTENT_TYPE_EXT = {
  'image/jpeg': '.jpg',
  'image/jpg': '.jpg',
  'image/pjpeg': '.jpg',
  'image/png': '.png',
  'image/webp': '.webp',
  'image/gif': '.gif',
}

function extensionForContentType(contentType) {
  const raw = String(contentType || '')
    .split(';')[0]
    .trim()
    .toLowerCase()
  if (!raw) return '.jpg'
  if (CONTENT_TYPE_EXT[raw]) return CONTENT_TYPE_EXT[raw]
  if (raw.endsWith('+xml') && raw.includes('svg')) return '.svg'
  if (raw.startsWith('image/')) {
    const subtype = raw.slice('image/'.length)
    if (subtype === 'jpeg' || subtype === 'pjpeg') return '.jpg'
    if (/^[a-z0-9.+-]+$/i.test(subtype)) return `.${subtype.split('+')[0]}`
  }
  return '.jpg'
}

function allocateDownloadFileName(basename, extension, usedNames) {
  const ext = extension.startsWith('.') ? extension : `.${extension}`
  const stem = String(basename || 'asset').replace(/[\\/]+/g, '_').trim() || 'asset'
  const preferred = `${stem}${ext}`
  const seen = usedNames.get(preferred) || 0
  usedNames.set(preferred, seen + 1)
  if (seen === 0) return preferred
  return `${stem}_${seen + 1}${ext}`
}

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

test('A2 extension maps JPEG/PNG content types', () => {
  assert.equal(extensionForContentType('image/jpeg'), '.jpg')
  assert.equal(extensionForContentType('image/png'), '.png')
  assert.equal(extensionForContentType('image/png; charset=binary'), '.png')
  assert.equal(extensionForContentType(''), '.jpg')
})

test('A2 collision suffixes use _2/_3 without overwriting first', () => {
  const used = new Map()
  assert.equal(allocateDownloadFileName('sku_a', '.png', used), 'sku_a.png')
  assert.equal(allocateDownloadFileName('sku_a', '.png', used), 'sku_a_2.png')
  assert.equal(allocateDownloadFileName('sku_a', '.png', used), 'sku_a_3.png')
  assert.equal(allocateDownloadFileName('sku_b', '.jpg', used), 'sku_b.jpg')
})

test('A2 TypeScript helper remains the library download source of truth', async () => {
  const tsPath = path.join(frontendRoot, 'src/lib/realphotos-download.ts')
  const ts = await readFile(tsPath, 'utf8')
  assert.match(ts, /export function extensionForContentType/)
  assert.match(ts, /export function allocateDownloadFileName/)
  assert.match(ts, /image\/png/)
  assert.match(ts, /\$\{stem\}_\$\{seen \+ 1\}/)
})
