import assert from 'node:assert/strict'
import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  INTERNAL_SITE_PREFIX,
  publicSiteSubPath,
  resolvePublicSiteRoute,
} from '../src/lib/public-site-routing.ts'
import { isPublicSiteModuleInstalled } from '../src/lib/public-site.ts'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const defaults = {
  publicDomains: ['www.example.com'],
  locales: ['zh-CN', 'en-US'],
  defaultLocale: 'zh-CN',
}

function decide(mode, pathname, hostname = 'app.example.com') {
  return resolvePublicSiteRoute({ ...defaults, mode, pathname, hostname })
}

test('route ownership matrix covers off, domain, and path modes', () => {
  const matrix = [
    ['off app route', decide('off', '/catalog'), 'next', 'app'],
    ['off public-looking slug', decide('off', '/pricing', 'www.example.com'), 'next', 'app'],
    ['off internal namespace', decide('off', `${INTERNAL_SITE_PREFIX}/zh-CN/pricing`), 'not-found', 'internal'],
    ['off static asset', decide('off', '/assets/app.js'), 'next', 'static'],

    ['domain app host route', decide('domain', '/pricing'), 'next', 'app'],
    ['domain public host slug', decide('domain', '/pricing', 'www.example.com'), 'rewrite', 'public'],
    ['domain internal namespace', decide('domain', `${INTERNAL_SITE_PREFIX}/zh-CN/pricing`, 'www.example.com'), 'not-found', 'internal'],
    ['domain static asset', decide('domain', '/assets/generated-file', 'www.example.com'), 'next', 'static'],

    ['path app route', decide('path', '/pricing'), 'next', 'app'],
    ['path public slug', decide('path', '/site/pricing'), 'rewrite', 'public'],
    ['path internal namespace', decide('path', `${INTERNAL_SITE_PREFIX}/zh-CN/pricing`), 'not-found', 'internal'],
    ['path static asset', decide('path', '/site/logo.png'), 'next', 'static'],
  ]

  for (const [label, result, action, owner] of matrix) {
    assert.equal(result.action, action, label)
    assert.equal(result.owner, owner, label)
  }

  assert.equal(decide('domain', '/pricing', 'www.example.com').pathname, `${INTERNAL_SITE_PREFIX}/zh-CN/pricing`)
  assert.equal(decide('path', '/site/pricing').pathname, `${INTERNAL_SITE_PREFIX}/zh-CN/pricing`)
})

test('locale canonicalization happens only after public ownership', () => {
  assert.deepEqual(decide('domain', '/zh-CN/pricing'), { action: 'next', owner: 'app' })
  assert.equal(decide('domain', '/zh-CN/pricing', 'www.example.com').pathname, '/pricing')
  assert.equal(decide('domain', '/en-us/pricing', 'www.example.com').pathname, '/en-US/pricing')
  assert.equal(
    decide('path', '/site/en-US/pricing').pathname,
    `${INTERNAL_SITE_PREFIX}/en-US/pricing`,
  )
  assert.equal(decide('path', '/site/zh-CN/pricing').pathname, '/site/pricing')
  assert.deepEqual(decide('path', '/site'), { action: 'redirect', owner: 'public', pathname: '/' })
  assert.equal(publicSiteSubPath('/site/pricing', 'zh-CN', 'zh-CN', 'path'), '/pricing')
  assert.equal(publicSiteSubPath('/site/en-US/pricing', 'en-US', 'zh-CN', 'path'), '/pricing')
  assert.equal(publicSiteSubPath('/en-US/pricing', 'en-US', 'zh-CN', 'domain'), '/pricing')
})

async function appPages() {
  const root = path.join(frontendRoot, 'src/app/(app)')
  const found = []

  async function walk(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name)
      if (entry.isDirectory()) await walk(absolute)
      if (entry.isFile() && entry.name === 'page.tsx') found.push(absolute)
    }
  }

  await walk(root)
  return found.map((pageFile) => {
    const directory = path.relative(root, path.dirname(pageFile))
    const segments = directory === '' ? [] : directory.split(path.sep)
    const urlSegments = segments
      .filter((segment) => !(segment.startsWith('(') && segment.endsWith(')')))
      .filter((segment) => !segment.startsWith('@'))
      .map((segment) => segment.replace(/^\[\[?\.\.\.(.+)\]\]?$/, '$1-sample'))
      .map((segment) => segment.replace(/^\[(.+)\]$/, '$1-sample'))
    return { pageFile, pathname: urlSegments.length ? `/${urlSegments.join('/')}` : '/' }
  })
}

test('every discovered app page stays with the app in each backstage request context', async () => {
  const pages = await appPages()
  assert.ok(pages.length > 0)

  for (const { pageFile, pathname } of pages) {
    const label = path.relative(frontendRoot, pageFile)
    assert.deepEqual(decide('off', pathname, 'www.example.com'), { action: 'next', owner: 'app' }, `${label} in off mode`)
    assert.deepEqual(decide('domain', pathname, 'app.example.com'), { action: 'next', owner: 'app' }, `${label} on app domain`)
    if (pathname !== '/') {
      assert.deepEqual(decide('path', pathname), { action: 'next', owner: 'app' }, `${label} in path mode`)
    }
  }

  // Path mode deliberately owns only the root exception plus /site/*.
  assert.equal(decide('path', '/').action, 'rewrite')
})

test('middleware preserves query strings and public misses use real notFound pages', async () => {
  const middleware = await readFile(path.join(frontendRoot, 'src/middleware.ts'), 'utf8')
  assert.match(middleware, /request\.nextUrl\.clone\(\)/)
  assert.doesNotMatch(middleware, /url\.search\s*=/)

  const cmsPage = await readFile(
    path.join(frontendRoot, 'src/app/(site)/__cms-site/[locale]/[slug]/page.tsx'),
    'utf8',
  )
  assert.match(cmsPage, /if \(!page\) notFound\(\)/)
})

test('CMS-off robots omits the CMS sitemap without resolving an origin', async () => {
  const robots = await readFile(path.join(frontendRoot, 'src/app/robots.ts'), 'utf8')
  assert.match(robots, /PUBLIC_SITE_ENABLED \? \(await siteOrigin\(\)\)/)
  assert.match(robots, /PUBLIC_SITE_ENABLED && origin/)
  assert.deepEqual(decide('off', '/'), { action: 'next', owner: 'app' })
  assert.equal(isPublicSiteModuleInstalled('none'), false)
  assert.equal(isPublicSiteModuleInstalled('base'), false)
  assert.equal(isPublicSiteModuleInstalled('cms'), true)
})
