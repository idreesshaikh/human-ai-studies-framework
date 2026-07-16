/**
 * Sign-in state for the app shell (FR-OPS-5, D29).
 *
 * The middleware announces its sign-in mode via GET /auth/config; any 401
 * from the API flips `needed` and the shell renders the sign-in surface
 * instead of letting views fail one by one.
 *
 * - token mode: signing in stores the bearer token where the API client
 *   already looks (`middleware.token`).
 * - clerk mode: clerk-js is loaded on demand (code-split - token/none
 *   deployments never download it), Clerk's hosted sign-in UI is mounted,
 *   and the API client gets a live token getter (Clerk session JWTs are
 *   short-lived; clerk-js refreshes them, we fetch per request). If the
 *   Clerk script cannot load, the paste-a-token fallback still works - a
 *   manually issued session token verifies server-side the same way.
 */
import type { Clerk } from '@clerk/clerk-js'

import { api, onUnauthorized, setTokenProvider, type AuthConfig } from './api'

class AuthState {
  needed = $state(false)
  config = $state<AuthConfig>({ mode: 'none' })
  /** Signed-in Clerk identity, for the nav footer. */
  user = $state<{ id: string; label: string } | null>(null)
  /** True once clerk-js is loaded and can mount its sign-in UI. */
  clerkReady = $state(false)
  private clerk: Clerk | null = null

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
    if (this.config.mode === 'clerk' && this.config.clerkPublishableKey) {
      await this.initClerk(this.config.clerkPublishableKey)
    }
  }

  private async initClerk(publishableKey: string): Promise<void> {
    try {
      const { Clerk } = await import('@clerk/clerk-js')
      const clerk = new Clerk(publishableKey)
      await clerk.load()
      this.clerk = clerk
      this.clerkReady = true
      if (clerk.user) {
        this.user = {
          id: clerk.user.id,
          label:
            clerk.user.primaryEmailAddress?.emailAddress ??
            clerk.user.username ??
            clerk.user.id,
        }
        setTokenProvider(async () => (await clerk.session?.getToken()) ?? null)
        this.needed = false
      }
      // The mounted sign-in UI completes in-page: when a session appears
      // while the sign-in surface is up, reload to restart views signed in.
      clerk.addListener(({ session }) => {
        if (session && this.needed) location.reload()
      })
    } catch {
      // clerk-js unreachable (offline, blocked CDN…): the token-paste
      // fallback surface stays usable; never a hard failure.
    }
  }

  /** Mount Clerk's hosted sign-in UI (clerk mode, once clerkReady). */
  mountSignIn(el: HTMLDivElement): void {
    this.clerk?.mountSignIn(el, {})
  }

  get hasToken(): boolean {
    return this.user !== null || localStorage.getItem('middleware.token') !== null
  }

  signIn(token: string): void {
    localStorage.setItem('middleware.token', token.trim())
    this.needed = false
    // Views cache failed loads; a clean reload restarts them signed in.
    location.reload()
  }

  signOut(): void {
    localStorage.removeItem('middleware.token')
    const clerk = this.clerk
    if (clerk?.user) {
      void clerk.signOut().finally(() => location.reload())
    } else {
      location.reload()
    }
  }
}

export const auth = new AuthState()
