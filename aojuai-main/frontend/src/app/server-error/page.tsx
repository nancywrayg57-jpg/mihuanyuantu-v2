'use client'

import Link from 'next/link'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useT } from '@/lib/i18n'

export default function ServerErrorPage() {
  const t = useT()

  return (
    <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-lg items-center p-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{t('system.errors.serverErrorTitle')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-sm text-muted-foreground">{t('system.errors.serverErrorDescription')}</div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link href="/welcome">{t('system.errors.backHome')}</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
