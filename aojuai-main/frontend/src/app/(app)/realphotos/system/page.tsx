import { Suspense } from 'react'

import { RealphotosSystemClient } from './system-client'

export default function RealphotosSystemPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm">加载系统管理…</main>}>
      <RealphotosSystemClient />
    </Suspense>
  )
}
