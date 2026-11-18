'use client'

import type { ReactNode } from 'react'

import { RequireAuth } from '@/components/auth/require-auth'
import { AssistantDock } from '@/components/assistant/assistant-dock'
import { AppLayout } from '@/components/layout/app-layout'
import { BusinessRouteGuard } from '@/components/layout/business-route-guard'
import { ModuleRouteGuard } from '@/components/layout/module-route-guard'

export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <>
        <AppLayout>
          <BusinessRouteGuard>
            <ModuleRouteGuard>{children}</ModuleRouteGuard>
          </BusinessRouteGuard>
        </AppLayout>
        <AssistantDock />
      </>
    </RequireAuth>
  )
}
