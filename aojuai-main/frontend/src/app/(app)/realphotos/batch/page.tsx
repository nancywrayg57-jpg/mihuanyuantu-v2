import { Suspense } from 'react'

import { RealphotosBatchClient } from './batch-client'

export default function RealphotosBatchPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm">加载批量原图…</main>}>
      <RealphotosBatchClient />
    </Suspense>
  )
}
