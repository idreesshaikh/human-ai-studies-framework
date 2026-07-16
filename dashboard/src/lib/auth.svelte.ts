/**
 * Sign-in state for the app shell.
 *
 * The middleware announces its sign-in mode via GET /auth/config; any 401
 * from the API flips `needed` and the shell renders the sign-in surface
 * instead of letting views fail one by one. Signing in stores the bearer
 * token where the API client already looks for it (`middleware.token`).
 */
import { api, onUnauthorized, type AuthConfig } from './api'

class AuthState {
  needed = $state(false)
  config = $state<AuthConfig>({ mode: 'none' })

  /** Wire the 401 listener and learn which sign-in surface to render. */
  async init(): Promise<void> {
    onUnauthorized(() => {
      this.needed = true
    })
    try {
      this.config = await api.authConfig()
    } catch {
      // Older middleware without /auth/config: keep the token-mode
      // fallback so a 401 still gets a sign-in surface.
      this.config = { mode: 'token' }
    }
  }

  get hasToken(): boolean {
    return localStorage.getItem('middleware.token') !== null
  }

  signIn(token: string): void {
    localStorage.setItem('middleware.token', token.trim())
    this.needed = false
    // Views cache failed loads; a clean reload restarts them signed in.
    location.reload()
  }

  signOut(): void {
    localStorage.removeItem('middleware.token')
    location.reload()
  }
}

export const auth = new AuthState()
