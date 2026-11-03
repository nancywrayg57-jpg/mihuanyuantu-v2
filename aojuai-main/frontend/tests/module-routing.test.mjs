import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  normalizeRoutePath,
  resolveDeclaredModuleForPath,
  resolveRouteBlockReason,
  routePathMatchesPrefix,
} from '../src/lib/module-routing.ts'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// 与后端 catalog 同形状的最小声明集
const DECLARED = [
  { code: 'assistant', routePrefixes: ['/assistant'] },
  { code: 'speech', routePrefixes: ['/speech', '/system/speech-settings'] },
  { code: 'public_site', routePrefixes: ['/cms'] },
]

test('内核路径不归任何模块，一律放行', () => {
  assert.equal(resolveDeclaredModuleForPath('/users', DECLARED), null)
  assert.equal(resolveRouteBlockReason('/users', DECLARED, [], null), null)
  assert.equal(resolveRouteBlockReason('/', DECLARED, [], null), null)
})

test('未安装的模块路径判为 uninstalled——这是手敲 URL 能进页面的那个洞', () => {
  // 已安装目录里只有 assistant：CMS 没装
  const blocked = resolveRouteBlockReason('/cms/pages', DECLARED, ['assistant'], { assistant: true })
  assert.deepEqual(blocked, { code: 'public_site', reason: 'uninstalled' })
})

test('装了但租户关掉，判为 disabled（与未安装区分开）', () => {
  const blocked = resolveRouteBlockReason('/cms/pages', DECLARED, ['assistant', 'public_site'], {
    assistant: true,
    public_site: false,
  })
  assert.deepEqual(blocked, { code: 'public_site', reason: 'disabled' })
})

test('装了且开着就放行；开关缺省视为开', () => {
  assert.equal(
    resolveRouteBlockReason('/cms/pages', DECLARED, ['public_site'], { public_site: true }),
    null,
  )
  assert.equal(resolveRouteBlockReason('/cms/pages', DECLARED, ['public_site'], {}), null)
})

test('前缀匹配按路径段边界，不做字符串包含', () => {
  assert.equal(routePathMatchesPrefix('/cms/pages', '/cms'), true)
  assert.equal(routePathMatchesPrefix('/cms', '/cms'), true)
  // /cmsx 不属于 /cms —— 否则会误伤同前缀的内核路由
  assert.equal(routePathMatchesPrefix('/cmsx', '/cms'), false)
  assert.equal(resolveDeclaredModuleForPath('/cmsx', DECLARED), null)
})

test('查询串、大小写与结尾斜杠不影响判定', () => {
  assert.equal(normalizeRoutePath('/CMS/Pages/'), '/cms/pages')
  assert.equal(resolveDeclaredModuleForPath('/CMS/pages?tab=1', DECLARED), 'public_site')
})

test('`#/` 后面的 hash 路由才是真路径（与后端 _normalize_prefix_path 同语义）', () => {
  // 老 hash 路由：/#/cms/pages 指向的是 /cms/pages
  assert.equal(normalizeRoutePath('/#/cms/pages'), '/cms/pages')
  assert.equal(resolveDeclaredModuleForPath('/#/cms/pages', DECLARED), 'public_site')
  // 反过来：真实路径带 hash 锚点时，以 hash 为准——所以这个**不**算 CMS 路径
  assert.equal(normalizeRoutePath('/cms/pages#/x'), '/x')
  assert.equal(resolveDeclaredModuleForPath('/cms/pages#/x', DECLARED), null)
})

test('守卫真的挂在 (app) 布局上——只写组件不挂载等于没做', async () => {
  const layout = await readFile(path.join(frontendRoot, 'src/app/(app)/layout.tsx'), 'utf8')
  // 必须断言**用上了**，不能只断言字符串出现过：
  // 第一版写的是 /ModuleRouteGuard/，把守卫从 JSX 里摘掉之后 import 行还在，
  // 测试照样绿——这就是"锁现象而不是锁不变量"的典型翻车。
  assert.match(
    layout,
    /<ModuleRouteGuard[\s>]/,
    '(app)/layout.tsx 必须把 ModuleRouteGuard 用作 JSX 包住 children，光 import 不算',
  )
  assert.match(layout, /<ModuleRouteGuard>\s*\{children\}\s*<\/ModuleRouteGuard>/)
})
