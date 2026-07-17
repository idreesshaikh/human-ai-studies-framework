<script lang="ts">
  import { auth } from '../auth.svelte'

  let token = $state('')
  let submitted = $state(false)
  let clerkEl = $state<HTMLDivElement | null>(null)

  const useClerkWidget = $derived(
    auth.config.mode === 'clerk' && auth.clerkReady,
  )

  // Mount Clerk's hosted sign-in UI once its container exists.
  $effect(() => {
    if (useClerkWidget && clerkEl) auth.mountSignIn(clerkEl)
  })

  function submit(e: SubmitEvent): void {
    e.preventDefault()
    if (!token.trim()) return
    submitted = true
    auth.signIn(token)
  }
</script>

<div class="scrim" role="dialog" aria-modal="true" aria-labelledby="signin-title">
  {#if useClerkWidget}
    <div class="clerk-mount" bind:this={clerkEl}></div>
  {:else}
    <form class="card" onsubmit={submit}>
      <h2 id="signin-title">Sign in</h2>
      {#if auth.config.mode === 'clerk'}
        <p class="secondary">
          This deployment verifies Clerk sessions, but the sign-in widget
          could not load. Paste a session token issued for this instance to
          continue.
        </p>
      {:else}
        <p class="secondary">
          This instance is protected by an access token (set by whoever runs
          it, via <code>MIDDLEWARE_TOKEN</code>).
        </p>
      {/if}
      <input
        type="password"
        placeholder="Access token"
        bind:value={token}
        autocomplete="current-password"
        aria-label="Access token"
      />
      <button type="submit" disabled={!token.trim() || submitted}>
        {submitted ? 'Signing in…' : 'Sign in'}
      </button>
      <p class="small muted">
        Data capture is never blocked by sign-in — only these views are.
      </p>
    </form>
  {/if}
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    background: color-mix(in srgb, var(--surface-1) 65%, transparent);
    backdrop-filter: blur(6px);
    display: grid;
    place-items: center;
    z-index: 40;
  }
  .card {
    width: min(360px, calc(100vw - 32px));
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  input {
    width: 100%;
  }
  button {
    align-self: flex-start;
  }
</style>
