import { NextRequest } from 'next/server'

import { proxyToBackend } from '@/lib/server/backend-proxy'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'
export const maxDuration = 300

type RouteContext = {
  params: Promise<{ path: string[] }>
}

async function handle(request: NextRequest, context: RouteContext) {
  const { path } = await context.params
  const pathname = `/api/v1/${(path || []).map((item) => encodeURIComponent(item)).join('/')}`
  return proxyToBackend(request, pathname)
}

export const GET = handle
export const POST = handle
export const PUT = handle
export const PATCH = handle
export const DELETE = handle
export const OPTIONS = handle
export const HEAD = handle
