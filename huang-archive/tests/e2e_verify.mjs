#!/usr/bin/env node
/**
 * 8-item live E2E verification against production.
 * Usage: node tests/e2e_verify.mjs [baseUrl]
 */
import { createRequire } from 'module'
import { writeFileSync, mkdirSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const DOMAIN = process.env.E2E_DOMAIN || 'https://huangzhisong.com'
const IP = process.env.E2E_IP || 'http://47.239.73.214'
const BASE = process.env.E2E_BASE || DOMAIN

const results = []

function pass(id, msg) {
  results.push({ id, ok: true, msg })
  console.log(`PASS  ${id}: ${msg}`)
}

function fail(id, msg) {
  results.push({ id, ok: false, msg })
  console.error(`FAIL  ${id}: ${msg}`)
}

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, opts)
  const text = await res.text()
  let body
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = text
  }
  return { res, body, text }
}

async function authWith(base, identity, password) {
  const { res, body } = await fetchJson(`${base}/api/collections/users/auth-with-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identity, password }),
  })
  if (!res.ok) throw new Error(`auth ${identity}: ${res.status} ${JSON.stringify(body)}`)
  return body
}

function authHeaders(token) {
  return { Authorization: token, 'Content-Type': 'application/json' }
}

// Minimal 1x1 PNG
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)

async function test1() {
  const id = 1
  try {
    const a = await fetch(DOMAIN, { redirect: 'follow' })
    const b = await fetch(IP, { redirect: 'follow' })
    const h1 = await fetch(`${DOMAIN}/api/health`)
    const h2 = await fetch(`${IP}/api/health`)
    const hj1 = await h1.json().catch(() => ({}))
    const hj2 = await h2.json().catch(() => ({}))
    if (a.status !== 200) throw new Error(`domain status ${a.status}`)
    if (b.status !== 200) throw new Error(`ip status ${b.status}`)
    if (h1.status !== 200 || hj1.status !== 'ok') throw new Error(`domain health ${h1.status} ${JSON.stringify(hj1)}`)
    if (h2.status !== 200 || hj2.status !== 'ok') throw new Error(`ip health ${h2.status} ${JSON.stringify(hj2)}`)
    pass(id, `domain+ip 200, /api/health ok`)
  } catch (e) {
    fail(id, e.message)
  }
}

async function test2() {
  const id = 2
  try {
    const admin = await authWith(BASE, 'huangxiangcai@huangzhisong.com', '3599263')
    if (admin.record?.role !== 'admin') throw new Error('黄祥财 role != admin')
    if (admin.record?.display_name !== '黄祥财') throw new Error('display_name mismatch')

    for (const [name, email] of [
      ['黄纲生', 'user1@huangzhisong.com'],
      ['黄成生', 'user2@huangzhisong.com'],
      ['黄嘉颖', 'user24@huangzhisong.com'],
    ]) {
      const u = await authWith(BASE, email, 'hzs1933')
      if (u.record?.role !== 'member') throw new Error(`${name} role != member`)
      if (u.record?.display_name !== name) throw new Error(`${name} display_name`)
    }

    const list = await fetchJson(`${BASE}/api/collections/users/records?perPage=100`, {
      headers: authHeaders(admin.token),
    })
    if (!list.res.ok) throw new Error(`list users ${list.res.status}`)
    const total = list.body.totalItems ?? list.body.items?.length ?? 0
    if (total < 25) throw new Error(`users count ${total} < 25`)
    pass(id, `admin+members auth OK, users=${total}`)
  } catch (e) {
    fail(id, e.message)
  }
}

async function test3() {
  const id = 3
  try {
    const u = await authWith(BASE, 'user1@huangzhisong.com', 'hzs1933')
    const form = new FormData()
    form.append('title', `E2E测试图-${Date.now()}`)
    form.append('category', 'image')
    form.append('occurred_time', '1985-10-01')
    form.append('related_persons', '黄志松、黄纲生')
    form.append('description', '端测上传')
    form.append('uploader', u.record.id)
    form.append('uploader_name', '黄纲生')
    form.append('likes_count', '0')
    form.append('media_files', new Blob([PNG_1X1], { type: 'image/png' }), 'e2e.png')

    const { res, body } = await fetchJson(`${BASE}/api/collections/archives/records`, {
      method: 'POST',
      headers: { Authorization: u.token },
      body: form,
    })
    if (!res.ok) throw new Error(`upload ${res.status} ${JSON.stringify(body)}`)
    if (body.category !== 'image') throw new Error('category')
    if (body.occurred_time !== '1985-10-01') throw new Error('occurred_time')
    if (body.related_persons !== '黄志松、黄纲生') throw new Error('related_persons')

    const list = await fetchJson(
      `${BASE}/api/collections/archives/records?filter=${encodeURIComponent(`id="${body.id}"`)}`,
      { headers: authHeaders(u.token) },
    )
    if (!list.body.items?.length) throw new Error('not visible in list')
    globalThis.__e2eArchiveId = body.id
    globalThis.__e2eMemberToken = u.token
    globalThis.__e2eMember = u.record
    pass(id, `uploaded archive ${body.id}`)
  } catch (e) {
    fail(id, e.message)
  }
}

async function test4() {
  const id = 4
  try {
    const token = globalThis.__e2eMemberToken
    const archiveId = globalThis.__e2eArchiveId
    const member = globalThis.__e2eMember
    if (!token || !archiveId) throw new Error('missing archive from test3')

    const before = await fetchJson(`${BASE}/api/collections/archives/records/${archiveId}`, {
      headers: authHeaders(token),
    })
    const prev = before.body.likes_count || 0

    const like = await fetchJson(`${BASE}/api/collections/archive_likes/records`, {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ archive_id: archiveId, user_id: member.id }),
    })
    if (!like.res.ok) throw new Error(`like ${like.res.status} ${JSON.stringify(like.body)}`)

    const upd = await fetchJson(`${BASE}/api/collections/archives/records/${archiveId}`, {
      method: 'PATCH',
      headers: authHeaders(token),
      body: JSON.stringify({ likes_count: prev + 1 }),
    })
    if (!upd.res.ok) throw new Error(`likes_count update ${upd.res.status}`)
    if ((upd.body.likes_count || 0) !== prev + 1) throw new Error('likes_count not incremented')

    const mem = await fetchJson(`${BASE}/api/collections/memories/records`, {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({
        archive_id: archiveId,
        author: member.id,
        author_name: '黄纲生',
        content_type: 'text',
        text_content: '端测文字追忆',
      }),
    })
    if (!mem.res.ok) throw new Error(`memory ${mem.res.status} ${JSON.stringify(mem.body)}`)
    if (mem.body.author_name !== '黄纲生') throw new Error('author_name')
    globalThis.__e2eMemoryId = mem.body.id
    pass(id, `like ${prev}->${prev + 1}, text memory ok`)
  } catch (e) {
    fail(id, e.message)
  }
}

async function test5() {
  const id = 5
  try {
    const token = globalThis.__e2eMemberToken
    const archiveId = globalThis.__e2eArchiveId
    const member = globalThis.__e2eMember
    if (!token || !archiveId) throw new Error('missing archive from test3')

    // Minimal fake webm-ish bytes; PocketBase may still accept as application/octet or we use wav
    const voiceBuf = Buffer.from(
      'UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=',
      'base64',
    )
    const form = new FormData()
    form.append('archive_id', archiveId)
    form.append('author', member.id)
    form.append('author_name', '黄纲生')
    form.append('content_type', 'voice')
    form.append('voice_duration', '1')
    form.append('voice_file', new Blob([voiceBuf], { type: 'audio/wav' }), 'voice.wav')

    const { res, body } = await fetchJson(`${BASE}/api/collections/memories/records`, {
      method: 'POST',
      headers: { Authorization: token },
      body: form,
    })
    if (!res.ok) throw new Error(`voice ${res.status} ${JSON.stringify(body)}`)
    if (body.content_type !== 'voice') throw new Error('content_type')
    const file = body.voice_file
    if (!file) throw new Error('no voice_file')
    const url = `${BASE}/api/files/${body.collectionId || 'memories'}/${body.id}/${file}`
    // Prefer PocketBase file URL pattern with collection id from record
    const fileUrl = body.collectionId
      ? `${BASE}/api/files/${body.collectionId}/${body.id}/${encodeURIComponent(file)}`
      : `${BASE}/api/files/memories00001/${body.id}/${encodeURIComponent(file)}`
    const fr = await fetch(fileUrl, { headers: { Authorization: token } })
    if (fr.status !== 200) {
      // try alternate collection name path
      const alt = `${BASE}/api/files/memories/${body.id}/${encodeURIComponent(file)}`
      const fr2 = await fetch(alt, { headers: { Authorization: token } })
      if (fr2.status !== 200) throw new Error(`voice file url ${fr.status}/${fr2.status} ${fileUrl}`)
    }
    globalThis.__e2eVoiceMemoryId = body.id
    pass(id, `voice memory uploaded, file 200`)
  } catch (e) {
    fail(id, e.message)
  }
}

async function test6() {
  const id = 6
  try {
    const email = 'user24@huangzhisong.com'
    const original = 'hzs1933'
    const temp = 'TempPass9'

    const u = await authWith(BASE, email, original)
    const upd = await fetchJson(`${BASE}/api/collections/users/records/${u.record.id}`, {
      method: 'PATCH',
      headers: authHeaders(u.token),
      body: JSON.stringify({
        oldPassword: original,
        password: temp,
        passwordConfirm: temp,
      }),
    })
    if (!upd.res.ok) throw new Error(`change pwd ${upd.res.status} ${JSON.stringify(upd.body)}`)

    const again = await authWith(BASE, email, temp)
    if (again.record.display_name !== '黄嘉颖') throw new Error('re-login failed')

    const restore = await fetchJson(`${BASE}/api/collections/users/records/${again.record.id}`, {
      method: 'PATCH',
      headers: authHeaders(again.token),
      body: JSON.stringify({
        oldPassword: temp,
        password: original,
        passwordConfirm: original,
      }),
    })
    if (!restore.res.ok) throw new Error(`restore pwd ${restore.res.status} ${JSON.stringify(restore.body)}`)
    await authWith(BASE, email, original)
    pass(id, '黄嘉颖 change password + restore OK')
  } catch (e) {
    fail(id, e.message)
  }
}

async function test7() {
  const id = 7
  try {
    const member = await authWith(BASE, 'user1@huangzhisong.com', 'hzs1933')
    const admin = await authWith(BASE, 'huangxiangcai@huangzhisong.com', '3599263')
    const archiveId = globalThis.__e2eArchiveId
    const memoryId = globalThis.__e2eMemoryId || globalThis.__e2eVoiceMemoryId
    if (!archiveId) throw new Error('missing archive')

    // Create disposable archive for admin delete if needed
    const form = new FormData()
    form.append('title', `DeleteTarget-${Date.now()}`)
    form.append('category', 'other')
    form.append('occurred_time', '测试')
    form.append('related_persons', '黄志松')
    form.append('uploader', admin.record.id)
    form.append('uploader_name', '黄祥财')
    form.append('likes_count', '0')
    form.append('media_files', new Blob([PNG_1X1], { type: 'image/png' }), 'del.png')
    const created = await fetchJson(`${BASE}/api/collections/archives/records`, {
      method: 'POST',
      headers: { Authorization: admin.token },
      body: form,
    })
    if (!created.res.ok) throw new Error(`create delete target ${created.res.status}`)
    const targetId = created.body.id

    const memCreate = await fetchJson(`${BASE}/api/collections/memories/records`, {
      method: 'POST',
      headers: authHeaders(member.token),
      body: JSON.stringify({
        archive_id: targetId,
        author: member.record.id,
        author_name: '黄纲生',
        content_type: 'text',
        text_content: '待删留言',
      }),
    })
    const memId = memCreate.body?.id

    const denyA = await fetch(`${BASE}/api/collections/archives/records/${targetId}`, {
      method: 'DELETE',
      headers: authHeaders(member.token),
    })
    if (![403, 404].includes(denyA.status)) throw new Error(`member delete archive expected 403/404 got ${denyA.status}`)

    if (memId) {
      const denyM = await fetch(`${BASE}/api/collections/memories/records/${memId}`, {
        method: 'DELETE',
        headers: authHeaders(member.token),
      })
      if (![403, 404].includes(denyM.status)) throw new Error(`member delete memory expected 403/404 got ${denyM.status}`)
    }

    if (memId) {
      const okM = await fetch(`${BASE}/api/collections/memories/records/${memId}`, {
        method: 'DELETE',
        headers: authHeaders(admin.token),
      })
      if (okM.status !== 204) throw new Error(`admin delete memory ${okM.status}`)
    }

    const okA = await fetch(`${BASE}/api/collections/archives/records/${targetId}`, {
      method: 'DELETE',
      headers: authHeaders(admin.token),
    })
    if (okA.status !== 204) throw new Error(`admin delete archive ${okA.status}`)

    pass(id, 'member denied 403/404; admin delete 204')
  } catch (e) {
    fail(id, e.message)
  }
}

async function test8() {
  const id = 8
  try {
    let playwright
    const require = createRequire(import.meta.url)
    try {
      playwright = await import('playwright')
    } catch {
      try {
        playwright = require(join(__dirname, '../frontend/node_modules/playwright'))
      } catch {
        playwright = require('playwright')
      }
    }
    const { chromium } = playwright
    const browser = await chromium.launch({ headless: true })
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 60000 })
    await page.fill('input[type="text"]', '黄祥财')
    await page.fill('input[type="password"]', '3599263')
    await page.click('button[type="submit"]')
    await page.waitForURL(/\/$/, { timeout: 30000 })

    const overflow = await page.evaluate(() => {
      const doc = document.documentElement
      return doc.scrollWidth > doc.clientWidth + 1
    })
    if (overflow) throw new Error('horizontal overflow detected')

    const tab = page.locator('[data-testid="category-tabs"] button').nth(1)
    await tab.click()
    await page.waitForTimeout(300)

    // Ensure at least one archive exists for delete UI; admin may upload none — create via API then reload
    const admin = await authWith(BASE, 'huangxiangcai@huangzhisong.com', '3599263')
    const form = new FormData()
    form.append('title', `UI删除确认-${Date.now()}`)
    form.append('category', 'image')
    form.append('occurred_time', '测试')
    form.append('related_persons', '黄志松')
    form.append('uploader', admin.record.id)
    form.append('uploader_name', '黄祥财')
    form.append('likes_count', '0')
    form.append('media_files', new Blob([PNG_1X1], { type: 'image/png' }), 'ui.png')
    await fetchJson(`${BASE}/api/collections/archives/records`, {
      method: 'POST',
      headers: { Authorization: admin.token },
      body: form,
    })
    await page.reload({ waitUntil: 'networkidle' })
    await page.locator('[data-testid="category-tabs"] button').first().click()

    const delBtn = page.locator('[data-testid="delete-archive"]').first()
    await delBtn.waitFor({ timeout: 15000 })
    await delBtn.click()
    const dialog = page.locator('[data-testid="delete-confirm-dialog"]')
    await dialog.waitFor({ timeout: 5000 })
    const text = await dialog.innerText()
    if (!text.includes('确认要永久删除这条珍贵的家族记忆吗？此操作不可恢复。')) {
      throw new Error('confirm copy mismatch')
    }
    // cancel to avoid wiping
    await page.getByRole('button', { name: '取消' }).click()

    await browser.close()
    pass(id, 'Playwright 390x844: login, no overflow, tabs, delete confirm')
  } catch (e) {
    fail(id, e.message)
  }
}

async function main() {
  console.log(`E2E against DOMAIN=${DOMAIN} IP=${IP} BASE=${BASE}`)
  await test1()
  await test2()
  await test3()
  await test4()
  await test5()
  await test6()
  await test7()
  await test8()

  const passed = results.filter((r) => r.ok).length
  const failed = results.filter((r) => !r.ok)
  console.log(`\n=== Summary: ${passed}/8 PASS ===`)
  for (const r of results) {
    console.log(`${r.ok ? 'PASS' : 'FAIL'} #${r.id} ${r.msg}`)
  }

  const report = {
    at: new Date().toISOString(),
    domain: DOMAIN,
    ip: IP,
    passed,
    total: 8,
    results,
  }

  const outDir = join(__dirname, '..', 'artifacts')
  try {
    mkdirSync(outDir, { recursive: true })
    writeFileSync(join(outDir, 'e2e-results.json'), JSON.stringify(report, null, 2))
  } catch (_) {}

  if (failed.length) process.exit(1)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
