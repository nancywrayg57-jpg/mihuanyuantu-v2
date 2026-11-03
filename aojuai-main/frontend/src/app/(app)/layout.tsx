'use client'

import type { ReactNode } from 'react'

import { RequireAuth } from '@/components/auth/require-auth'
import { AssistantDock } from '@/components/assistant/assistant-dock'
import { AppLayout } from '@/components/layout/app-layout'
import { ModuleRouteGuard } from '@/components/layout/module-route-guard'

export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <>
        <AppLayout>
          <ModuleRouteGuard>{children}</ModuleRouteGuard>
        </AppLayout>
        <AssistantDock />
      </>
    </RequireAuth>
  )
}
