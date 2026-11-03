'use client'

import Link from 'next/link'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useT } from '@/lib/i18n'

export default function AccessDeniedPage() {
  const t = useT()

  return (
    <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-lg items-center p-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{t('system.errors.accessDeniedTitle')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-sm text-muted-foreground">{t('system.errors.accessDeniedDescription')}</div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link href="/welcome">{t('system.errors.backHome')}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/login">{t('system.errors.loginAgain')}</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
