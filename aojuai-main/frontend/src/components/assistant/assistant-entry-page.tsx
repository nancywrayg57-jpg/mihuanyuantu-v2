'use client'

import { useEffect } from 'react'
import { Bot, Settings2, Sparkles } from 'lucide-react'
import { useRouter, useSearchParams } from 'next/navigation'

import { emitAssistantOpen } from '@/components/assistant/assistant-events'
import { PageHeader } from '@/components/page/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useT } from '@/lib/i18n'

export default function AssistantEntryPage({ currentPath }: { currentPath: string }) {
  const t = useT()
  const router = useRouter()
  const searchParams = useSearchParams()

  const routePath = searchParams.get('routePath') || searchParams.get('from') || currentPath || '/assistant'
  const prompt = searchParams.get('prompt') || ''
  const autoSend = ['1', 'true', 'yes'].includes(String(searchParams.get('autoSend') || '').toLowerCase())

  useEffect(() => {
    emitAssistantOpen({
      routePath,
      prompt: prompt || undefined,
      autoSend,
      forceNewSession: true,
    })
  }, [autoSend, prompt, routePath])

  return (
    <div className="grid gap-3">
      <Card>
        <CardHeader>
          <PageHeader
            title={t('system.assistant.title')}
            description={t('system.assistant.entry.description')}
            actions={(
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  onClick={() =>
                    emitAssistantOpen({
                      routePath,
                      prompt: prompt || undefined,
                      autoSend,
                      forceNewSession: true,
                    })
                  }
                >
                  <Sparkles className="mr-1 h-4 w-4" />
                  {t('system.assistant.entry.open')}
                </Button>
                <Button variant="outline" size="sm" onClick={() => router.push('/personal/settings')}>
                  <Settings2 className="mr-1 h-4 w-4" />
                  {t('system.assistant.entry.personalSettings')}
                </Button>
                <Button variant="outline" size="sm" onClick={() => router.push('/system/tenant-settings?tab=ai')}>
                  <Bot className="mr-1 h-4 w-4" />
                  {t('system.assistant.entry.tenantAiConfig')}
                </Button>
              </div>
            )}
          />
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('system.assistant.entry.currentPath')}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <div className="font-mono text-foreground">{currentPath}</div>
              <div className="mt-2">{t('system.assistant.entry.currentPathDesc')}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('system.assistant.entry.context')}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <div className="font-mono text-foreground">{routePath}</div>
              <div className="mt-2">{t('system.assistant.entry.contextDesc')}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('system.assistant.entry.compat')}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <div>{t('system.assistant.entry.compatDesc')}</div>
              <div className="mt-2">{t('system.assistant.entry.configDesc')}</div>
            </CardContent>
          </Card>
        </CardContent>
      </Card>
    </div>
  )
}
