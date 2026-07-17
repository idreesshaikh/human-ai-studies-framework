<script lang="ts">
  import { api, type LiveDoc, type SessionSummary } from '../api'
  import { link, router } from '../router.svelte'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()
  let live = $state<LiveDoc | null>(null)
  let all = $state<SessionSummary[]>([])
  let error = $state<string | null>(null)
  let now = $state(Date.now())
  let flashed = new Set<string>()
  let freshGaps = $state<Set<string>>(new Set())
  let changedRates = $state<Set<string>>(new Set())
  let previousRateTail = new Map<string, number>()

  const conditionColor = (condition: string): string => {
    const value = [...condition].reduce((sum, char) => sum + char.charCodeAt(0), 0)
    return `var(--series-${(value % 6) + 1})`
  }
  const ageSeconds = (iso: string): number => Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000))
  const ageCopy = (iso: string): string => { const age = ageSeconds(iso); return age < 60 ? `${age}s ago` : age < 3600 ? `${Math.floor(age / 60)}m ago` : `${Math.floor(age / 3600)}h ago` }
  const maxRate = (rate: number[]): number => Math.max(...rate, 1)

  async function poll(): Promise<void> {
    try {
      const next = await api.live(studyId)
      const gaps = new Set<string>()
      const shifted = new Set<string>()
      for (const session of next.sessions) {
        const tail = session.rate.at(-1) ?? 0
        if (previousRateTail.has(session.sessionId) && previousRateTail.get(session.sessionId) !== tail) shifted.add(session.sessionId)
        previousRateTail.set(session.sessionId, tail)
        if (session.gapCount > 0 && !flashed.has(session.sessionId)) { gaps.add(session.sessionId); flashed.add(session.sessionId) }
      }
      live = next; freshGaps = gaps; changedRates = shifted; error = null
      setTimeout(() => { freshGaps = new Set(); changedRates = new Set() }, 350)
    } catch (cause) { error = String(cause) }
  }
  async function loadAll(): Promise<void> { try { all = await api.sessions(studyId) } catch { /* live poll reports connectivity */ } }
  $effect(() => {
    studyId; poll(); loadAll()
    const fast = setInterval(poll, 2_000); const slow = setInterval(loadAll, 10_000); const clock = setInterval(() => (now = Date.now()), 1_000)
    return () => { clearInterval(fast); clearInterval(slow); clearInterval(clock) }
  })
</script>

<header class="page-head"><div><p class="eyebrow">Streaming instrumentation</p><h1>Live sessions <TraceChip id="FR-DASH-3" /></h1><p class="secondary">Every instrument reports into one five-minute observation window. This screen polls every two seconds.</p></div><button onclick={poll}>Refresh</button></header>

{#if error}<div class="card error" role="alert"><strong>Observatory link interrupted</strong><span>{error}</span><button onclick={poll}>Reconnect</button></div>{/if}

{#if live}
  {#if live.sessions.length > 0}
    <div class="observatory" data-tour="live-cards">
      {#each live.sessions as session (session.sessionId)}
        {@const quiet = ageSeconds(session.lastReceivedAt) >= 30}
        {@const peak = maxRate(session.rate)}
        <article class="session-card">
          <header><div><div class="condition"><i style:background={conditionColor(session.condition)}></i>{session.condition}</div><h2><a href={router.studyHref('sessions', session.sessionId)} use:link>{session.participantId}</a></h2><span class="mono id">{session.sessionId}</span></div><div class:quiet class="signal"><i></i>{quiet ? 'quiet' : 'receiving'}</div></header>
          <div class="rate" class:shift={changedRates.has(session.sessionId)} aria-label={`Event rate over five minutes, peak ${peak}`}>
            {#each session.rate as value, index (index)}<span class:latest={index === session.rate.length - 1} style:height={`${Math.max(8, (value / peak) * 100)}%`}></span>{/each}
          </div>
          <div class="rate-meta"><span>5 min ago</span><strong>{session.eventsInWindow} events</strong><span>now</span></div>
          <p class="last mono">last event: {session.lastEventType} · {ageCopy(session.lastReceivedAt)}</p>
          {#if session.gapCount > 0}<div class:flash={freshGaps.has(session.sessionId)} class="integrity" role="status"><strong>{session.missingEvents} event{session.missingEvents === 1 ? '' : 's'} lost in transit</strong><span>recoverable from local files · {session.gapCount} sequence gap{session.gapCount === 1 ? '' : 's'}</span></div>{/if}
        </article>
      {/each}
    </div>
  {:else}
    <section class="empty card"><div class="schematic" aria-hidden="true"><span>IDE</span><span>PROBE</span><span>AGENT</span><i></i><b>LIVE</b></div><div><h2>No sessions in the last 5 minutes.</h2><p>Cards appear here the moment an instrument sends data.</p></div></section>
  {/if}

  <section class="card allsessions"><header><div><p class="eyebrow">Audit index</p><h2>All sessions</h2></div><span class="count">{all.length}</span></header>{#if all.length === 0}<p class="muted">Nothing ingested yet.</p>{:else}<div class="tablewrap"><table class="data"><thead><tr><th>Session</th><th>Participant</th><th>Condition</th><th>Events</th><th>Metrics</th><th>Last signal</th></tr></thead><tbody>{#each all as session (session.sessionId)}<tr><td><a href={router.studyHref('sessions', session.sessionId)} use:link class="mono">{session.sessionId}</a></td><td class="mono">{session.participantId}</td><td>{session.condition}</td><td>{session.events}</td><td>{session.metricRows}</td><td class="mono small">{session.lastTs ?? '-'}</td></tr>{/each}</tbody></table></div>{/if}</section>
{:else if !error}<div class="loading" aria-live="polite">Listening for instrument signals…</div>{/if}

<style>
  .page-head,.session-card>header,.allsessions>header,.rate-meta,.error{display:flex;align-items:center;justify-content:space-between;gap:12px}.page-head{margin-bottom:18px}.page-head h1{margin:2px 0}.page-head p{margin:0;max-width:720px}.eyebrow{margin:0;color:var(--text-muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.observatory{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}.session-card{overflow:hidden;background:var(--surface-1);border:1px solid var(--border);border-radius:12px}.session-card>header{padding:14px 14px 8px;align-items:flex-start}.session-card h2{font-size:18px;margin:3px 0 0}.condition{display:flex;align-items:center;gap:6px;color:var(--text-secondary);font-size:12px}.condition i{width:7px;height:7px;border-radius:50%}.id{color:var(--text-muted);font-size:11px}.signal{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--status-good);text-transform:uppercase;letter-spacing:.06em}.signal i{width:6px;height:6px;border-radius:50%;background:var(--status-good);animation:breathe 2s ease-in-out infinite}.signal.quiet{color:var(--text-muted)}.signal.quiet i{background:var(--text-muted);animation:none}.rate{height:92px;display:flex;align-items:flex-end;gap:3px;padding:12px 14px 4px;overflow:hidden}.rate span{flex:1;min-width:2px;background:color-mix(in srgb,var(--series-1) 72%,var(--surface-1));border-radius:2px 2px 0 0;transform-origin:right center}.rate span.latest{background:var(--series-1)}.rate.shift span{animation:slide 150ms ease-out}.rate-meta{padding:0 14px;color:var(--text-muted);font-size:10px}.rate-meta strong{color:var(--text-secondary);font-weight:500}.last{margin:12px 14px 14px;color:var(--text-secondary);font-size:12px}.integrity{display:flex;flex-direction:column;gap:2px;padding:9px 14px;background:color-mix(in srgb,var(--status-serious) 10%,var(--surface-1));border-top:1px solid var(--status-serious);font-size:11px;color:var(--text-secondary)}.integrity strong{color:var(--status-serious)}.integrity.flash{animation:alarm 300ms ease-out}.allsessions{margin-top:14px}.allsessions h2{margin:2px 0}.count{font-variant-numeric:tabular-nums;color:var(--text-muted)}.tablewrap{overflow:auto}.empty{min-height:210px;display:flex;align-items:center;justify-content:center;gap:36px}.empty h2{margin:0}.empty p{color:var(--text-secondary)}.schematic{display:grid;grid-template-columns:repeat(3,44px);gap:8px;align-items:center;color:var(--text-muted);font:9px monospace}.schematic span{border:1px solid var(--grid);padding:6px 2px;text-align:center}.schematic i{grid-column:1/4;height:1px;background:var(--grid)}.schematic b{grid-column:1/4;justify-self:center;border:1px solid var(--grid);padding:8px 20px;font-weight:500}.loading{padding:36px;color:var(--text-muted)}@keyframes breathe{50%{opacity:.35;transform:scale(.75)}}@keyframes slide{from{transform:translateX(6px);opacity:.7}}@keyframes alarm{0%{background:color-mix(in srgb,var(--status-serious) 35%,var(--surface-1))}100%{background:color-mix(in srgb,var(--status-serious) 10%,var(--surface-1))}}@media(max-width:700px){.observatory{grid-template-columns:1fr}.page-head{align-items:flex-start}.empty{flex-direction:column;text-align:center}}@media(prefers-reduced-motion:reduce){.signal i,.rate.shift span,.integrity.flash{animation:none}}
</style>
