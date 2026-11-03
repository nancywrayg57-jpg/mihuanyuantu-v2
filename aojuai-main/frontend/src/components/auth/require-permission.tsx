'use client'

import type { ReactNode } from 'react'

import { hasAnyPermission } from '@/lib/auth'
import { useAuth } from '@/hooks/useAuth'

export function RequirePermission({
  anyOf,
  fallback = null,
  children,
}: {
  anyOf: string[]
  fallback?: ReactNode
  children: ReactNode
}) {
  const { session } = useAuth()

  if (!hasAnyPermission(session, anyOf)) return fallback
  return children
}

