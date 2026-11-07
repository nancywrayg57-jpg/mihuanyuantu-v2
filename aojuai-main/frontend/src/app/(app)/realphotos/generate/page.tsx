import { Suspense } from 'react'

import { RealphotosGenerateClient } from './generate-client'

export default function RealphotosGeneratePage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm">加载生图入库…</main>}>
      <RealphotosGenerateClient />
    </Suspense>
  )
}
