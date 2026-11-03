'use client'

import type { ReactNode } from 'react'

import { Toaster } from 'sonner'

import { AuthProvider } from '@/hooks/useAuth'
import { LocaleProvider } from '@/lib/i18n'
import { TenantProvider } from '@/hooks/useTenant'
import { ThemeProvider } from '@/hooks/useTheme'
import { SiteSeoBootstrap } from '@/components/layout/site-seo-bootstrap'
import { TenantThemeApplier } from '@/components/layout/tenant-theme-applier'

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <LocaleProvider>
      <AuthProvider>
        <TenantProvider>
          <SiteSeoBootstrap />
          <TenantThemeApplier />
          {children}
          <Toaster position="top-right" richColors closeButton />
        </TenantProvider>
      </AuthProvider>
      </LocaleProvider>
    </ThemeProvider>
  )
}
