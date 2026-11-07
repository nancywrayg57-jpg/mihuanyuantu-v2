'use client'

import Link from 'next/link'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function RealphotosAdminPage() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/realphotos/workspace')
  }, [router])

  return (
    <main className="space-y-4 p-6 text-sm">
      <p>
        运营指标已并入
        <Link className="mx-1 underline" href="/realphotos/workspace">
          工作台
        </Link>
        （管理员视图）。本页仅保留跳转。
      </p>
    </main>
  )
}
