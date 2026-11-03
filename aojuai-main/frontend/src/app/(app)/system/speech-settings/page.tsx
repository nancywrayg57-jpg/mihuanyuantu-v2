import { redirect } from 'next/navigation'

import type { RouteSearchParams } from '@/lib/system-settings-routes'
import { buildTenantSpeechSettingsHref } from '@/lib/system-settings-routes'

export default async function SpeechSettingsRedirectPage({
  searchParams,
}: {
  searchParams: Promise<RouteSearchParams>
}) {
  const resolvedSearchParams = await searchParams
  redirect(buildTenantSpeechSettingsHref(resolvedSearchParams.panel, resolvedSearchParams))
}
