/**
 * Sign-in state for the app shell (FR-OPS-5, D29).
 *
 * The middleware announces its sign-in mode via GET /auth/config; any 401
 * from the API flips `needed` and the shell renders the sign-in surface
 * instead of letting views fail one by one.
 *
 * - token mode: signing in stores the bearer token where the API client
 *   already looks (`middleware.token`).
 * - clerk mode: clerk-js is hot-loaded from the Clerk instance's own
 *   domain (Clerk's documented pattern for non-React apps - the npm
 *   package's ESM build ships without the UI renderer, so self-bundling
 *   mounts nothing; the npm package stays as a types-only devDependency).
 *   Since clerk-js v6 the component renderer lives in a second script,
 *   `@clerk/ui`: it must load first (it sets
 *   `window.__internal_ClerkUICtor`) and the constructor is passed to
 *   `Clerk.load({ ui: { ClerkUI } })` - a bare `load()` initializes
 *   headless and `mountSignIn` throws "not loaded with Ui components".
 *   Clerk's hosted sign-in UI is mounted and the API client gets a live
 *   token getter (Clerk session JWTs are short-lived; clerk-js refreshes
 *   them, we fetch per request). If the script cannot load, the
 *   paste-a-token fallback still works - a manually issued session token
 *   verifies server-side the same way.
 */
import type { Clerk } from '@clerk/clerk-js'

import { api, onUnauthorized, setTokenProvider, type AuthConfig } from './api'

/** The instance's Frontend API domain, encoded in the publishable key
 * (`pk_test_<base64 of "domain$">`). */
function frontendApiFromKey(publishableKey: string): string {
  const b64 = publishableKey.split('_').slice(2).join('_')
  return atob(b64).replace(/\$$/, '')
}

/** The UI-component constructor `@clerk/ui`'s browser build registers on
 * `window`; `Clerk.load()` needs it to render any UI. */
type ClerkUICtor = NonNullable<Parameters<Clerk['load']>[0]> extends {
  ui?: { ClerkUI?: infer U }
}
  ? U
  : unknown

function injectScript(src: string, configure?: (s: HTMLScriptElement) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.crossOrigin = 'anonymous'
    configure?.(script)
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`failed to load ${src}`))
    document.head.appendChild(script)
  })
}

/** Inject Clerk's hotload scripts from the instance domain - `@clerk/ui`
 * first (the component renderer), then clerk-js core; resolves to the
 * auto-instantiated `window.Clerk` plus the UI constructor to pass into
 * `Clerk.load()`. */
async function loadClerkScript(
  publishableKey: string,
): Promise<{ clerk: Clerk; ui: ClerkUICtor | undefined }> {
  const w = window as { Clerk?: Clerk; __internal_ClerkUICtor?: ClerkUICtor }
  const base = `https://${frontendApiFromKey(publishableKey)}/npm`
  if (!w.__internal_ClerkUICtor) {
    // Best-effort: without the UI script the token-paste fallback remains.
    await injectScript(`${base}/@clerk/ui@1/dist/ui.browser.js`).catch(() => {})
  }
  if (!w.Clerk) {
    await injectScript(`${base}/@clerk/clerk-js@6/dist/clerk.browser.js`, (s) =>
      s.setAttribute('data-clerk-publishable-key', publishableKey),
    )
  }
  if (!w.Clerk) throw new Error('clerk-js did not initialize')
  return { clerk: w.Clerk, ui: w.__internal_ClerkUICtor }
}

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
      const { clerk, ui } = await loadClerkScript(publishableKey)
      await clerk.load(ui ? { ui: { ClerkUI: ui } } : undefined)
      this.clerk = clerk
      // Without the UI renderer, mountSignIn throws; keep the token-paste
      // fallback surface instead of an empty scrim.
      this.clerkReady = ui !== undefined
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
