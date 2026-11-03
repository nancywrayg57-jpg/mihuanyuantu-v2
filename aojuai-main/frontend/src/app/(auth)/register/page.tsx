import { Suspense } from 'react'

import { DEFAULT_LOCALE, translate } from '@/lib/i18n/registry'

import { RegisterClient } from './register-client'

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">{translate(DEFAULT_LOCALE, 'common.loading')}</div>}>
      <RegisterClient />
    </Suspense>
  )
}
