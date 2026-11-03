import { Suspense } from 'react'

import { DEFAULT_LOCALE, translate } from '@/lib/i18n/registry'

import { LoginClient } from './login-client'

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">{translate(DEFAULT_LOCALE, 'common.loading')}</div>}>
      <LoginClient />
    </Suspense>
  )
}
