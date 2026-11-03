'use client'

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { fetchAuthSession, logoutCurrentSession } from '@/lib/auth-api'
import {
  clearSession,
  isCookieBackedSession,
  loadSession,
  onAuthEvent,
  shouldSkipAnonymousSessionProbe,
  type Session,
  saveSession,
} from '@/lib/auth'

type AuthContextValue = {
  session: Session | null
  ready: boolean
  setSession: (session: Session | null) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false

    const storedSession = loadSession()
    if (storedSession) {
      setSessionState(storedSession)
    }

    if (typeof window !== 'undefined' && shouldSkipAnonymousSessionProbe(window.location.pathname, storedSession)) {
      setReady(true)
      return () => {
        cancelled = true
      }
    }

    void (async () => {
      try {
        const liveSession = await fetchAuthSession()
        if (cancelled) return

        if (liveSession) {
          setSessionState(liveSession)
          saveSession(liveSession)
          return
        }

        if (!storedSession || isCookieBackedSession(storedSession)) {
          setSessionState(null)
          clearSession()
        }
      } catch {
        if (cancelled) return
        if (!storedSession || isCookieBackedSession(storedSession)) {
          setSessionState(null)
          clearSession()
        }
      } finally {
        if (!cancelled) {
          setReady(true)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  const setSession = useCallback((next: Session | null) => {
    setSessionState(next)
    if (next) {
      saveSession(next)
      return
    }
    clearSession()
  }, [])

  const logout = useCallback(() => {
    void logoutCurrentSession()
    setSession(null)
  }, [setSession])

  // Subscribe to auth events (e.g., 401 from API layer)
  useEffect(() => {
    const unsubscribe = onAuthEvent('logout', () => {
      setSession(null)
      // Navigate to login - use window.location for simplicity
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    })
    return unsubscribe
  }, [setSession])

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      ready,
      setSession,
      logout,
    }),
    [session, ready, setSession, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within <AuthProvider>')
  }
  return ctx
}
