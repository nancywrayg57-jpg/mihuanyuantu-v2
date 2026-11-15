'use client'

import type { ButtonHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

import { rpBtnClass, rpBtnDangerClass, rpBtnPrimaryClass, rpBtnSmClass } from './surface'

type Variant = 'primary' | 'secondary' | 'danger'
type Size = 'md' | 'sm'

type RpButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
  pressed?: boolean
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary: rpBtnPrimaryClass,
  secondary: rpBtnClass,
  danger: rpBtnDangerClass,
}

export function RpButton({
  variant = 'secondary',
  size = 'md',
  pressed,
  className,
  type = 'button',
  ...props
}: RpButtonProps) {
  const sized = size === 'sm' ? rpBtnSmClass : VARIANT_CLASS[variant]
  const tone = size === 'sm' && variant === 'primary' ? 'rp-btn-primary' : size === 'sm' && variant === 'danger' ? 'rp-btn-danger' : ''
  return (
    <button
      type={type}
      aria-pressed={pressed}
      className={cn(sized, tone, pressed && 'is-active', className)}
      {...props}
    />
  )
}
