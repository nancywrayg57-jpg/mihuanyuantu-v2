/**
 * 模块路由解析：纯函数，不依赖 React、不依赖 `@/` 别名、不 import 生成物。
 *
 * 单独成文件是为了**能被 node --test 直接跑**：`feature-switches.ts` 里
 * `import ... from '@/generated/module-catalog.json'` 这一行让整个模块在
 * 裸 node 下解析不了，而路由判定恰恰是最该有测试的地方——它决定用户手敲 URL
 * 能不能进一个没装的模块。
 */

export type ModuleRouteDeclaration = {
  code: string
  routePrefixes?: string[]
}

export type RouteBlockReason = 'uninstalled' | 'disabled'

export function normalizeRoutePath(pathname: string | null | undefined): string {
  let path = String(pathname || '').trim().toLowerCase()
  if (!path) return '/'

  if (path.includes('#/')) {
    path = `/${path.split('#/', 2)[1].trim()}`
  } else if (path.includes('#')) {
    path = path.split('#', 1)[0].trim()
  }
  if (path.includes('?')) {
    path = path.split('?', 1)[0].trim()
  }

  if (!path.startsWith('/')) path = `/${path.replace(/^\/+/, '')}`
  if (path.length > 1) path = path.replace(/\/+$/, '')
  return path || '/'
}

export function routePathMatchesPrefix(pathname: string, prefix: string): boolean {
  const path = normalizeRoutePath(pathname)
  const normalizedPrefix = normalizeRoutePath(prefix)
  if (normalizedPrefix === '/') return path === '/'
  return path === normalizedPrefix || path.startsWith(`${normalizedPrefix}/`)
}

/**
 * 路径 → 声明的模块 code。传入的必须是**完整声明目录**（构建期生成的那份），
 * 而不是接口返回的目录——后者只包含已安装的模块，未安装的模块连 routePrefixes
 * 都拿不到，`/cms/pages` 就会被当成内核路径放行。
 */
export function resolveDeclaredModuleForPath(
  pathname: string,
  declared: readonly ModuleRouteDeclaration[],
): string | null {
  for (const item of declared) {
    if (item.routePrefixes?.some((prefix) => routePathMatchesPrefix(pathname, prefix))) {
      return item.code
    }
  }
  return null
}

/**
 * 这个路径当前能不能进。三种结果：
 * - `null`：内核路径，或模块已装且已启用
 * - `uninstalled`：部署级没装（已安装目录里没有它）→ 当作页面不存在
 * - `disabled`：装了但该租户关了 → 提示"未启用"
 */
export function resolveRouteBlockReason(
  pathname: string,
  declared: readonly ModuleRouteDeclaration[],
  installedCodes: readonly string[],
  moduleSwitches: Record<string, boolean> | null | undefined,
): { code: string; reason: RouteBlockReason } | null {
  const code = resolveDeclaredModuleForPath(pathname, declared)
  if (!code) return null
  if (!installedCodes.includes(code)) return { code, reason: 'uninstalled' }
  const enabled = moduleSwitches?.[code]
  if (typeof enabled === 'boolean' && !enabled) return { code, reason: 'disabled' }
  return null
}
