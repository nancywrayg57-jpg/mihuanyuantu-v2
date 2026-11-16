'use client'

import { toast } from 'sonner'

/**
 * Realphotos content surface.
 * Cards follow the aojuai `Card` token (rounded-xl, border, bg-card, shadow-sm).
 * Buttons follow prototype `.btn` density: 10px radius, 180ms ease, hover lift.
 * Palette stays on the existing aojuai tokens (accent hover), not a new theme.
 *
 * Visual chrome for `.rp-btn` / `.rp-card` lives in `realphotos-surface.css`
 * so pages share one export instead of copying the long hover class string.
 */
export const rpCardClass =
  'rp-card rounded-xl border border-border bg-card text-card-foreground shadow-sm'

export const rpBtnClass = 'rp-btn'

export const rpBtnSmClass = 'rp-btn rp-btn-sm'

export const rpBtnPrimaryClass = 'rp-btn rp-btn-primary'

export const rpBtnDangerClass = 'rp-btn rp-btn-danger'

export const rpInputClass = 'rp-input'

export const rpSelectClass = 'rp-input rp-select'

export const rpTableClass = 'rp-table w-full border-collapse text-sm'

export const rpFilterClass = 'rp-filter'

export const rpEmptyClass = 'rp-empty'

/** Success/failure feedback for user-triggered tasks and staff ticket completion. */
export function toastTask(message: string, ok = true) {
  if (!message) return
  if (ok) toast.success(message)
  else toast.error(message)
}
