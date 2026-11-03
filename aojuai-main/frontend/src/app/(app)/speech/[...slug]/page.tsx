import { redirect } from 'next/navigation'

import type { RouteSearchParams } from '@/lib/system-settings-routes'
import { buildTenantSpeechSettingsHref, resolveSpeechSettingsPanelFromSlug } from '@/lib/system-settings-routes'

export default async function SpeechCatchAllPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug?: string[] }>
  searchParams: Promise<RouteSearchParams>
}) {
  const resolvedParams = await params
  const resolvedSearchParams = await searchParams
  const panel = resolvedParams.slug?.length ? resolveSpeechSettingsPanelFromSlug(resolvedParams.slug) : resolvedSearchParams.panel
  redirect(buildTenantSpeechSettingsHref(panel, resolvedSearchParams))
}
