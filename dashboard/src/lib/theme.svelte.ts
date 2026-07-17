/**
 * Color-theme state: light / dark / system, persisted in localStorage and
 * applied as data-theme="light|dark" on <html> (the tokens in app.css key
 * off that attribute). "system" tracks the OS live via matchMedia. A
 * pre-paint script in index.html applies the same rule before first paint
 * so a saved theme never flashes.
 */

export type ThemeMode = 'light' | 'dark' | 'system'

const KEY = 'dashboard.theme'

function systemPrefersDark(): boolean {
  return (
    typeof matchMedia !== 'undefined' &&
    matchMedia('(prefers-color-scheme: dark)').matches
  )
}

class ThemeState {
  mode = $state<ThemeMode>('system')

  constructor() {
    const saved =
      typeof localStorage !== 'undefined' ? localStorage.getItem(KEY) : null
    if (saved === 'light' || saved === 'dark' || saved === 'system') {
      this.mode = saved
    }
    this.apply()
    if (typeof matchMedia !== 'undefined') {
      matchMedia('(prefers-color-scheme: dark)').addEventListener(
        'change',
        () => {
          if (this.mode === 'system') this.apply()
        },
      )
    }
  }

  /** The mode resolved to what is actually on screen. */
  get resolved(): 'light' | 'dark' {
    if (this.mode === 'system') return systemPrefersDark() ? 'dark' : 'light'
    return this.mode
  }

  set(mode: ThemeMode): void {
    this.mode = mode
    try {
      localStorage.setItem(KEY, mode)
    } catch {
      // storage unavailable (private mode) - theme still applies this visit
    }
    this.apply()
  }

  private apply(): void {
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = this.resolved
    }
  }
}

export const theme = new ThemeState()
