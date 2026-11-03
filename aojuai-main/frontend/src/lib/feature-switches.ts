'use client'

import generatedModuleCatalog from '@/generated/module-catalog.json'
import type { MenuRoute } from '@/hooks/useMenuRoutes'
import {
  resolveDeclaredModuleForPath as resolveDeclaredModule,
  resolveRouteBlockReason,
  routePathMatchesPrefix,
  type RouteBlockReason,
} from './module-routing'

export type VerificationConfig = {
  sms?: { enabled?: boolean }
  email?: { enabled?: boolean }
}

export type FeatureSwitches = {
  modules: Record<string, boolean>
  capabilities: Record<string, boolean>
}

export type FeatureModuleItem = {
  code: string
  label: string
  description: string
  layer: 'kernel' | 'capability' | 'pack' | 'sample'
  /** i18n key；label/description 是服务端显示名（助手会拼进自然语言，那里不能出现 key） */
  labelKey?: string
  descriptionKey?: string
  defaultEnabled: boolean
  aliases?: string[]
  routePrefixes?: string[]
  apiPrefixes?: string[]
  permissionPrefixes?: string[]
}

export type FeatureCapabilityItem = {
  code: string
  label: string
  description: string
  labelKey?: string
  descriptionKey?: string
  defaultEnabled: boolean
}

export type FeatureCatalog = {
  catalogDigest: string
  modules: FeatureModuleItem[]
  capabilities: FeatureCapabilityItem[]
  /** 后端当前数据库方言：postgresql | sqlite（SQLite 轻量档部分功能不可用） */
  databaseDialect?: 'postgresql' | 'sqlite' | string
  /** 当前方言下不可用的功能码（见 backend app/core/dialect_features.py），前端据此隐藏入口 */
  unavailableFeatures?: string[]
  featureSwitches?: FeatureSwitches
  feature_switches?: FeatureSwitches
}

export const FALLBACK_FEATURE_CATALOG = generatedModuleCatalog as FeatureCatalog

export function normalizeSwitchKey(value: unknown): string {
  return String(value || '').trim().toLowerCase().replace(/-/g, '_')
}

// 路径规范化与前缀匹配统一在 module-routing.ts（纯函数、可被 node --test 直接跑）
// normalizePathname 的别名留了但没人用，lint 会直接判 Error 挡住 pnpm check——
// 只保留真正被引用的那个。
const pathMatchesPrefix = routePathMatchesPrefix

export function buildDefaultFeatureSwitches(catalog: FeatureCatalog): FeatureSwitches {
  const modules = catalog.modules.reduce((acc, item) => {
    acc[item.code] = Boolean(item.defaultEnabled)
    return acc
  }, {} as Record<string, boolean>)

  const capabilities = catalog.capabilities.reduce((acc, item) => {
    acc[item.code] = Boolean(item.defaultEnabled)
    return acc
  }, {} as Record<string, boolean>)

  return { modules, capabilities }
}

export function buildModuleAliasMap(catalog: FeatureCatalog): Record<string, string> {
  const map: Record<string, string> = {}
  catalog.modules.forEach((item) => {
    const code = normalizeSwitchKey(item.code)
    if (code) map[code] = item.code
    ;(item.aliases || []).forEach((alias) => {
      const aliasKey = normalizeSwitchKey(alias)
      if (aliasKey) map[aliasKey] = item.code
    })
  })
  return map
}

export function normalizeFeatureSwitches(
  catalog: FeatureCatalog,
  raw: unknown,
  verification?: VerificationConfig,
): FeatureSwitches {
  const defaults = buildDefaultFeatureSwitches(catalog)
  const aliasMap = buildModuleAliasMap(catalog)

  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const modulesRaw =
    source.modules && typeof source.modules === 'object' ? (source.modules as Record<string, unknown>) : {}
  const capabilitiesRaw =
    source.capabilities && typeof source.capabilities === 'object'
      ? (source.capabilities as Record<string, unknown>)
      : {}

  const modules: Record<string, boolean> = { ...defaults.modules }
  Object.entries(modulesRaw).forEach(([key, value]) => {
    const normalizedKey = normalizeSwitchKey(key)
    const canonicalKey = aliasMap[normalizedKey] || normalizedKey
    if (Object.prototype.hasOwnProperty.call(modules, canonicalKey)) {
      modules[canonicalKey] = Boolean(value)
    }
  })

  const capabilities: Record<string, boolean> = { ...defaults.capabilities }
  Object.keys(capabilities).forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(capabilitiesRaw, key)) {
      capabilities[key] = Boolean(capabilitiesRaw[key])
    }
  })

  if (!Object.prototype.hasOwnProperty.call(capabilitiesRaw, 'verification_sms')) {
    const smsEnabled = verification?.sms?.enabled
    if (typeof smsEnabled === 'boolean') capabilities.verification_sms = smsEnabled
  }

  if (!Object.prototype.hasOwnProperty.call(capabilitiesRaw, 'verification_email')) {
    const emailEnabled = verification?.email?.enabled
    if (typeof emailEnabled === 'boolean') capabilities.verification_email = emailEnabled
  }

  return { modules, capabilities }
}

export function isModuleEnabled(
  catalog: FeatureCatalog,
  featureSwitches: FeatureSwitches | null | undefined,
  moduleId: string,
) {
  const aliasMap = buildModuleAliasMap(catalog)
  const normalizedKey = normalizeSwitchKey(moduleId)
  const canonicalKey = aliasMap[normalizedKey] || normalizedKey
  const known = catalog.modules.some((item) => item.code === canonicalKey)
  if (!known) return false
  if (!featureSwitches) return true
  const enabled = featureSwitches.modules[canonicalKey]
  return typeof enabled === 'boolean' ? enabled : true
}

/** 路径 → 声明的模块 code（用构建期生成的完整声明目录，含未安装的模块） */
export function resolveDeclaredModuleForPath(pathname: string): string | null {
  return resolveDeclaredModule(pathname, FALLBACK_FEATURE_CATALOG.modules)
}

export type { RouteBlockReason }

/**
 * 这个路径当前能不能进：`null` 放行，否则给出模块 code 与原因。
 * 判定逻辑在 module-routing.ts，这里只负责把两份目录喂进去——
 * `catalog` 是接口返回的**已安装**目录，声明目录来自构建期生成物。
 */
export function resolveRouteBlock(
  pathname: string,
  catalog: FeatureCatalog,
  featureSwitches: FeatureSwitches | null | undefined,
): { code: string; reason: RouteBlockReason } | null {
  return resolveRouteBlockReason(
    pathname,
    FALLBACK_FEATURE_CATALOG.modules,
    catalog.modules.map((item) => item.code),
    featureSwitches?.modules,
  )
}

export function getDisabledModuleCodeForPath(
  pathname: string,
  catalog: FeatureCatalog,
  featureSwitches: FeatureSwitches | null | undefined,
) {
  for (const item of catalog.modules) {
    if (!item.routePrefixes?.some((prefix) => pathMatchesPrefix(pathname, prefix))) continue
    return isModuleEnabled(catalog, featureSwitches, item.code) ? null : item.code
  }
  return null
}

export function filterMenuRoutesByFeatureSwitches(
  routes: MenuRoute[],
  catalog: FeatureCatalog,
  featureSwitches: FeatureSwitches | null | undefined,
): MenuRoute[] {
  function filterRoute(route: MenuRoute): MenuRoute | null {
    if (getDisabledModuleCodeForPath(route.path, catalog, featureSwitches)) return null

    const originalChildren = route.children || []
    const nextChildren = originalChildren
      .map(filterRoute)
      .filter((item): item is MenuRoute => item !== null)

    if (nextChildren.length > 0) {
      return { ...route, children: nextChildren }
    }
    if (originalChildren.length > 0) {
      return null
    }
    return route
  }

  return routes.map(filterRoute).filter((item): item is MenuRoute => item !== null)
}

/** 功能在当前部署方言下是否可用（未下发字段时视为可用，保持旧后端兼容）。 */
export function isFeatureAvailable(catalog: FeatureCatalog | null | undefined, featureCode: string): boolean {
  const list = catalog?.unavailableFeatures
  if (!Array.isArray(list)) return true
  return !list.includes(featureCode)
}
