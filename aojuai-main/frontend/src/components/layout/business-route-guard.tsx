'use client'

import { useEffect, type ReactNode } from 'react'
import { usePathname, useRouter } from 'next/navigation'

import { useAuth } from '@/hooks/useAuth'

/**
 * 2026-11-18 UX audit U3：演示页不再保留。
 * 业务角色直接敲 URL 也不能进入平台演示页面（菜单隐藏不是授权边界）。
 */
const BLOCKED_PREFIXES = ['/schedule', '/permission', '/system/dict', '/tenant/package']

function isBlockedPath(pathname: string): boolean {
  return BLOCKED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}

export function BusinessRouteGuard({ children }: { children: ReactNode }) {
  const { session, ready } = useAuth()
  const pathname = usePathname()
  const router = useRouter()
  const blocked = Boolean(ready && session && isBlockedPath(pathname || ''))

  useEffect(() => {
    if (blocked) router.replace('/realphotos/workspace')
  }, [blocked, router])

  if (blocked) return null
  return <>{children}</>
}
