export type ThemeMode = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'applyguard.theme'

const THEME_COLORS: Record<ThemeMode, string> = {
  light: '#F3F7F6',
  dark: '#0B100E',
}

export function readStoredTheme(): ThemeMode {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY)
    if (value === 'light' || value === 'dark') return value
  } catch { /* optional preference */ }
  return 'dark'
}

export function applyTheme(theme: ThemeMode) {
  document.documentElement.setAttribute('data-theme', theme)
  document.documentElement.style.colorScheme = theme
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', THEME_COLORS[theme])
  try { localStorage.setItem(THEME_STORAGE_KEY, theme) } catch { /* optional preference */ }
}

export function toggleTheme(current: ThemeMode): ThemeMode {
  const next = current === 'dark' ? 'light' : 'dark'
  applyTheme(next)
  return next
}
