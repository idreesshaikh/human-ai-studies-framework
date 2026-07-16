<script lang="ts">
  import { api, type LiveDoc, type SessionSummary } from '../api'
  import { link, router } from '../router.svelte'
  import Sparkline from '../components/Sparkline.svelte'
  import Tip from '../components/Tip.svelte'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()

  let live = $state<LiveDoc | null>(null)
  let all = $state<SessionSummary[]>([])
  let error = $state<string | null>(null)

  async function poll(): Promise<void> {
    try {
      live = await api.live(studyId)
      error = null
    } catch (e) {
      error = String(e)
    }
  }
  async function loadAll(): Promise<void> {
    try {
      all = await api.sessions(studyId)
    } catch {
      /* the live poll already reports connectivity */
    }
  }
  // 2 s polling (FR-DASH-3); WebSockets are gold-plating at this scale.
  $effect(() => {
    poll()
    loadAll()
    const fast = setInterval(poll, 2_000)
    const slow = setInterval(loadAll, 10_000)
    return () => {
      clearInterval(fast)
      clearInterval(slow)
    }
  })
</script>

<h1>Live sessions <TraceChip id="FR-DASH-3" /></h1>
<p class="secondary small">
  Sessions with ingests in the last {live ? live.windowSeconds / 60 : 5} minutes,
  polled every 2 s.
</p>

{#if error}
  <div class="card"><p class="secondary">Failed to load: {error}</p></div>
{:else if live}
  {#if live.sessions.length === 0}
    <div class="card">
      <p class="secondary">No live sessions right now.</p>
      <p class="small muted">
        Replay the sample session to see this view move:
        <code>uv run python middleware/scripts/replay_session.py</code>
      </p>
    </div>
  {/if}
  <div class="cards" data-tour="live-cards">
    {#each live.sessions as s (s.sessionId)}
      <div class="card">
        {#if s.gapCount > 0}
          <div class="gapbanner">
            <Tip
              text="Every event carries a sequence number; a hole in the numbering means events were lost in transit. The loss is detected and shown here - it can never go silently missing. In the demo data this gap is planted on purpose."
            >
              <span class="badge serious underline-dotted">! seq gaps</span>
            </Tip>
            {s.missingEvents} event{s.missingEvents === 1 ? '' : 's'} missing
            across {s.gapCount} gap{s.gapCount === 1 ? '' : 's'} - detected,
            never silent
          </div>
        {/if}
        <h3>
          <a href={router.studyHref('sessions', s.sessionId)} use:link class="mono">
            {s.sessionId}
          </a>
        </h3>
        <div class="small secondary">
          {s.participantId} · {s.condition}
        </div>
        <Sparkline values={s.rate} />
        <div class="small muted">
          last event <code>{s.lastEventType}</code> · seq {s.lastSeq} ·
          {s.eventsInWindow} events in window
        </div>
      </div>
    {/each}
  </div>

  <section class="card allsessions">
    <h2>All sessions</h2>
    {#if all.length === 0}
      <p class="small muted">Nothing ingested yet.</p>
    {:else}
      <table class="data">
        <thead>
          <tr>
            <th>Session</th><th>Participant</th><th>Condition</th>
            <th>Events</th><th>Metric rows</th><th>First</th><th>Last</th>
          </tr>
        </thead>
        <tbody>
          {#each all as s (s.sessionId)}
            <tr>
              <td>
                <a href={router.studyHref('sessions', s.sessionId)} use:link class="mono">
                  {s.sessionId}
                </a>
              </td>
              <td class="mono">{s.participantId}</td>
              <td>{s.condition}</td>
              <td>{s.events}</td>
              <td>{s.metricRows}</td>
              <td class="mono small">{s.firstTs ?? '-'}</td>
              <td class="mono small">{s.lastTs ?? '-'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
{:else}
  <p class="muted">Loading…</p>
{/if}

<style>
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
    margin-bottom: 14px;
  }
  .gapbanner {
    background: color-mix(in srgb, var(--status-serious) 10%, transparent);
    border: 1px solid var(--status-serious);
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 12px;
    margin-bottom: 8px;
  }
  .allsessions {
    margin-top: 6px;
  }
</style>
