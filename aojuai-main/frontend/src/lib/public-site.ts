/** Deployment-level public-site route ownership.  Default is deliberately off. */
export type PublicSiteRoutingMode = 'off' | 'domain' | 'path'

export function isPublicSiteModuleInstalled(value: string | undefined) {
  const raw = String(value || '').trim().toLowerCase().replace(/-/g, '_')
  if (!raw || raw === 'all' || raw === '*') return true
  const modules = new Set(
    raw.replace(/;/g, ',').split(',').map((item) => item.trim()).filter(Boolean),
  )
  return modules.has('cms') || modules.has('public_site') || modules.has('site_cms')
}

const configuredMode = String(process.env.NEXT_PUBLIC_PUBLIC_SITE_ROUTING_MODE || 'off')
  .trim()
  .toLowerCase()

const configuredRoutingMode: PublicSiteRoutingMode =
  configuredMode === 'domain' || configuredMode === 'path' ? configuredMode : 'off'

export const PUBLIC_SITE_INSTALLED = isPublicSiteModuleInstalled(
  process.env.NEXT_PUBLIC_AOJ_ENABLED_MODULES,
)

export const PUBLIC_SITE_ROUTING_MODE: PublicSiteRoutingMode =
  PUBLIC_SITE_INSTALLED ? configuredRoutingMode : 'off'

/** Exact public hosts used only by domain mode; application hosts are excluded. */
export const PUBLIC_SITE_DOMAINS = String(process.env.NEXT_PUBLIC_PUBLIC_SITE_DOMAINS || '')
  .split(',')
  .map((host) => host.trim().toLowerCase())
  .filter(Boolean)

export const PUBLIC_SITE_ENABLED = PUBLIC_SITE_ROUTING_MODE !== 'off'
