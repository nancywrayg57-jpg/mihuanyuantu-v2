'use client'

import { useMemo, useState } from 'react'

type UseSharePasswordGateOptions = {
  requiresPassword?: boolean
  initialPassword?: string
  initialOpen?: boolean
}

export function useSharePasswordGate(options: UseSharePasswordGateOptions = {}) {
  const [open, setOpen] = useState(Boolean(options.initialOpen))
  const [password, setPassword] = useState(String(options.initialPassword || ''))
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const requiresPassword = Boolean(options.requiresPassword)
  const trimmedPassword = useMemo(() => password.trim(), [password])
  const canSubmit = useMemo(
    () => !submitting && (!requiresPassword || Boolean(trimmedPassword)),
    [requiresPassword, submitting, trimmedPassword],
  )

  function openGate() {
    setOpen(true)
    setError(null)
  }

  function closeGate() {
    setOpen(false)
    setSubmitting(false)
    setError(null)
  }

  function resetGate(nextPassword = '') {
    setPassword(nextPassword)
    setSubmitting(false)
    setError(null)
  }

  function beginSubmit() {
    setSubmitting(true)
    setError(null)
  }

  function finishSubmit(nextError?: string | null) {
    setSubmitting(false)
    setError(nextError ?? null)
  }

  function buildPayload<T extends Record<string, unknown>>(extra?: T) {
    return {
      ...(extra || {}),
      password: trimmedPassword || undefined,
    } as T & { password?: string }
  }

  return {
    open,
    setOpen,
    openGate,
    closeGate,
    resetGate,
    password,
    setPassword,
    trimmedPassword,
    error,
    setError,
    submitting,
    setSubmitting,
    beginSubmit,
    finishSubmit,
    requiresPassword,
    canSubmit,
    buildPayload,
  }
}
