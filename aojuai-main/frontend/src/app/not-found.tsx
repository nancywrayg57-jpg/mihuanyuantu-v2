'use client'

import Link from 'next/link'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useT } from '@/lib/i18n'

export default function NotFound() {
  const t = useT()

  return (
    <div className="mx-auto max-w-lg p-6">
      <Card>
        <CardHeader>
          <CardTitle>{t('system.errors.notFoundTitle')}</CardTitle>
        </CardHeader>
        <CardContent>
          <Button asChild variant="secondary">
            <Link href="/welcome">{t('system.errors.backHome')}</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
