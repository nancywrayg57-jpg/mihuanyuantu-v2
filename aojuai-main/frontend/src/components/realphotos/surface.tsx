'use client'

import { toast } from 'sonner'

/**
 * Realphotos content surface.
 * Cards follow the aojuai `Card` token (rounded-xl, border, bg-card, shadow-sm).
 * Buttons follow prototype `.btn` density: 10px radius, 180ms ease, hover lift.
 * Palette stays on the existing aojuai tokens (accent hover), not a new theme.
 */
export const rpCardClass =
  'rp-card rounded-xl border border-border bg-card text-card-foreground shadow-sm'

export const rpBtnClass =
  'rp-btn inline-flex items-center justify-center rounded-[10px] border border-border bg-background px-3 py-1 text-sm font-medium transition duration-150 hover:-translate-y-px hover:border-foreground/25 hover:bg-accent hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:bg-background disabled:hover:shadow-none'

/** Success/failure feedback for user-triggered tasks and staff ticket completion. */
export function toastTask(message: string, ok = true) {
  if (!message) return
  if (ok) toast.success(message)
  else toast.error(message)
}
