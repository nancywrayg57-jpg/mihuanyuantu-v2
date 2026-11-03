'use client'

import { useEffect } from 'react'
import Link from 'next/link'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useT } from '@/lib/i18n'

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useT()

  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-lg items-center p-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{t('system.errors.pageErrorTitle')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-sm text-muted-foreground">{t('system.errors.pageErrorDescription')}</div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={reset}>{t('system.errors.retry')}</Button>
            <Button asChild variant="secondary">
              <Link href="/welcome">{t('system.errors.backHome')}</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
