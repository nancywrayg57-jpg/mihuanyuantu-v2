'use client'

import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { usePathname, useRouter } from 'next/navigation'

import { apiFetch } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'

const PROFILE_REQUIRED_PATH = '/personal/profile-required'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { ready, session, setSession } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [profileGateReady, setProfileGateReady] = useState(false)
  const sessionKey = session ? `${session.username}:${session.expires}:${session.authMode}` : null

  useEffect(() => {
    if (!ready || session) return
    const next = pathname || '/'
    router.replace(`/login?next=${encodeURIComponent(next)}`)
  }, [pathname, ready, router, session])

  useEffect(() => {
    if (!ready) return
    if (!session) {
      setProfileGateReady(true)
      return
    }
    if (typeof session.mustCompleteProfile === 'boolean') {
      setProfileGateReady(true)
      return
    }

    let ignore = false
    setProfileGateReady(false)

    const loadMine = async () => {
      try {
        const mine = await apiFetch<{ mustCompleteProfile?: boolean }>('/api/v1/auth/mine', { session })
        if (ignore) return

        const mustCompleteProfile = Boolean(mine.mustCompleteProfile)
        if (mustCompleteProfile !== Boolean(session.mustCompleteProfile)) {
          setSession({
            ...session,
            mustCompleteProfile,
          })
        }
      } finally {
        if (!ignore) setProfileGateReady(true)
      }
    }

    void loadMine()
    return () => {
      ignore = true
    }
  }, [ready, session, sessionKey, setSession])

  useEffect(() => {
    if (!ready || !session) return
    if (!session.mustCompleteProfile) return
    if (pathname === PROFILE_REQUIRED_PATH) return
    router.replace(PROFILE_REQUIRED_PATH)
  }, [pathname, ready, router, session])

  if (!ready || (session && !profileGateReady)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!session) return null
  return children
}
