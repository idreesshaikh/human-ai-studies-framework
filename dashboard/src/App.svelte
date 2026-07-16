<script lang="ts">
  import { api, type Health } from './lib/api'
  import { auth } from './lib/auth.svelte'
  import { lexicon } from './lib/lexicon.svelte'
  import { link, router, type View } from './lib/router.svelte'
  import { tour } from './lib/tour.svelte'
  import { trace } from './lib/trace.svelte'
  import GuidedTour from './lib/components/GuidedTour.svelte'
  import TracePanel from './lib/components/TracePanel.svelte'
  import Overview from './lib/views/Overview.svelte'
  import LifecycleBoard from './lib/views/LifecycleBoard.svelte'
  import TaskBoard from './lib/views/TaskBoard.svelte'
  import LiveSessions from './lib/views/LiveSessions.svelte'
  import SessionTimeline from './lib/views/SessionTimeline.svelte'
  import MetricsCompare from './lib/views/MetricsCompare.svelte'
  import Knowledge from './lib/views/Knowledge.svelte'
  import SignIn from './lib/components/SignIn.svelte'

  let health = $state<Health | null>(null)
  let offline = $state(false)

  const NAV: { view: View; label: string }[] = [
    { view: 'overview', label: 'Overview' },
    { view: 'board', label: 'Lifecycle' },
    { view: 'tasks', label: 'Task board' },
    { view: 'live', label: 'Live sessions' },
    { view: 'metrics', label: 'Metrics' },
    { view: 'knowledge', label: 'Knowledge' },
  ]

  async function boot(): Promise<void> {
    try {
      await auth.init()
      health = await api.health()
      offline = false
      const study = health.studyId ?? 'adhoc'
      if (!router.route.studyId) {
        router.go(`/study/${encodeURIComponent(study)}/overview`, true)
      }
      if (health.protocolLoaded) {
        trace.protocol = await api.protocol(study)
      }
      // Plain-language layer (FR-DASH-9): SRS + glossary tooltips, and the
      // guided tour on a first visit.
      void lexicon.load()
      tour.maybeAutoStart(study)
    } catch {
      offline = true
      setTimeout(boot, 3000)
    }
  }
  boot()

  const studyId = $derived(router.route.studyId)
</script>

<div class="shell">
  <nav aria-label="Views" data-tour="nav">
    <div class="brand">
      <div class="title">Mission Control</div>
      {#if trace.protocol}
        <div class="small muted">{trace.protocol.studyId}</div>
      {/if}
    </div>
    {#each NAV as item (item.view)}
      <a
        href={router.studyHref(item.view)}
        use:link
        class:active={router.route.view === item.view}
      >
        {item.label}
      </a>
    {/each}
    <div class="foot small muted">
      {#if studyId && !offline}
        <button
          type="button"
          class="tour-launch"
          onclick={() => tour.start(studyId)}
        >
          ✦ Take the tour
        </button>
      {/if}
      {#if offline}
        <span class="badge critical">! middleware offline</span>
      {:else if health}
        <span class="badge good">middleware ok</span>
      {/if}
      {#if auth.config.mode !== 'none' && auth.hasToken}
        <button type="button" class="tour-launch" onclick={() => auth.signOut()}>
          Sign out
        </button>
      {/if}
    </div>
  </nav>

  <main>
    {#if offline}
      <div class="card">
        <h2>Middleware unreachable</h2>
        <p class="secondary">
          Start it with <code>uv run python -m middleware</code> (or
          <code>docker compose up</code>) - retrying automatically.
        </p>
      </div>
    {:else if studyId}
      {#if router.route.view === 'overview'}
        <Overview {studyId} />
      {:else if router.route.view === 'board'}
        <LifecycleBoard {studyId} />
      {:else if router.route.view === 'tasks'}
        <TaskBoard {studyId} />
      {:else if router.route.view === 'live'}
        <LiveSessions {studyId} />
      {:else if router.route.view === 'sessions' && router.route.sessionId}
        <SessionTimeline sessionId={router.route.sessionId} />
      {:else if router.route.view === 'metrics'}
        <MetricsCompare {studyId} />
      {:else if router.route.view === 'knowledge'}
        <Knowledge {studyId} />
      {/if}
    {/if}
  </main>
</div>

<TracePanel />
<GuidedTour />
{#if auth.needed}
  <SignIn />
{/if}

<style>
  .shell {
    display: grid;
    grid-template-columns: 190px 1fr;
    min-height: 100vh;
  }
  nav {
    border-right: 1px solid var(--border);
    background: var(--surface-1);
    padding: 16px 10px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    position: sticky;
    top: 0;
    height: 100vh;
  }
  .brand {
    padding: 0 8px 14px;
  }
  .brand .title {
    font-weight: 700;
  }
  nav a {
    color: var(--text-secondary);
    padding: 6px 8px;
    border-radius: 6px;
  }
  nav a:hover {
    background: color-mix(in srgb, var(--text-muted) 10%, transparent);
    text-decoration: none;
  }
  nav a.active {
    color: var(--text-primary);
    background: color-mix(in srgb, var(--series-1) 12%, transparent);
    font-weight: 600;
  }
  .foot {
    margin-top: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
  .tour-launch {
    font-size: 12px;
    color: var(--series-1);
    background: none;
    border: 1px solid color-mix(in srgb, var(--series-1) 35%, transparent);
    border-radius: 6px;
    padding: 4px 8px;
  }
  .tour-launch:hover {
    background: color-mix(in srgb, var(--series-1) 10%, transparent);
  }
  main {
    padding: 20px 24px;
    max-width: 1200px;
    width: 100%;
  }
</style>
