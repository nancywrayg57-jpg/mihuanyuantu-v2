import { translateActive } from '@/lib/i18n/registry'

export function isDemoMode(): boolean {
  const raw = process.env.NEXT_PUBLIC_DEMO_MODE
  return raw === '1' || raw === 'true'
}

export function getDemoModeMessage(): string {
  return process.env.NEXT_PUBLIC_DEMO_MODE_MESSAGE ?? translateActive('system.demo.readonlyMessage')
}
