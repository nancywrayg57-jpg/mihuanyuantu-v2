/**
 * 租户主题色预设。
 *
 * 值为 shadcn HSL 令牌格式（"H S% L%"），light/dark 各一档：
 * dark 档提亮以保证暗底对比度。key 与后端
 * tenant_profile.THEME_PRESET_KEYS 保持一致。
 */
export type ThemePreset = {
  key: string
  labelKey: string
  light: string
  dark: string
}

export const THEME_PRESETS: Record<string, ThemePreset> = {
  indigo: { key: 'indigo', labelKey: 'system.theme.indigo', light: '238.7 83.5% 66.7%', dark: '234 89% 74%' },
  blue: { key: 'blue', labelKey: 'system.theme.blue', light: '217 91% 60%', dark: '213 94% 68%' },
  cyan: { key: 'cyan', labelKey: 'system.theme.cyan', light: '192 91% 36%', dark: '187 92% 50%' },
  emerald: { key: 'emerald', labelKey: 'system.theme.emerald', light: '160 84% 39%', dark: '158 64% 52%' },
  orange: { key: 'orange', labelKey: 'system.theme.orange', light: '25 95% 53%', dark: '27 96% 61%' },
  rose: { key: 'rose', labelKey: 'system.theme.rose', light: '347 77% 50%', dark: '351 95% 71%' },
  violet: { key: 'violet', labelKey: 'system.theme.violet', light: '262 83% 58%', dark: '258 90% 66%' },
  slate: { key: 'slate', labelKey: 'system.theme.slate', light: '215 25% 27%', dark: '215 20% 65%' },
}

export const DEFAULT_THEME_PRESET_KEY = 'indigo'

export function resolveThemePreset(key: string | null | undefined): ThemePreset | null {
  const normalized = String(key || '').trim().toLowerCase()
  if (!normalized) return null
  return THEME_PRESETS[normalized] || null
}

/** 把预设应用到 documentElement 的 CSS 变量；传 null 还原为样式表默认值 */
export function applyThemePreset(preset: ThemePreset | null) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (!preset || preset.key === DEFAULT_THEME_PRESET_KEY) {
    root.style.removeProperty('--primary')
    root.style.removeProperty('--ring')
    return
  }
  const dark = root.classList.contains('dark')
  root.style.setProperty('--primary', dark ? preset.dark : preset.light)
  root.style.setProperty('--ring', dark ? preset.dark : preset.light)
}
