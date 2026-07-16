<script lang="ts">
  import { api, type ProtocolSummary, type SessionStatus, type StatusDoc } from '../api'
  import { link, router } from '../router.svelte'
  import Tip from '../components/Tip.svelte'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()

  let protocol = $state<ProtocolSummary | null>(null)
  let status = $state<StatusDoc | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(true)
  let refreshing = $state(false)

  async function load(): Promise<void> {
    refreshing = !loading
    try {
      ;[protocol, status] = await Promise.all([
        api.protocol(studyId),
        api.status(studyId),
      ])
      error = null
    } catch {
      error = 'Mission Control could not reach the study service.'
    } finally {
      loading = false
      refreshing = false
    }
  }

  $effect(() => {
    studyId
    loading = true
    void load()
    const timer = setInterval(load, 10_000)
    return () => clearInterval(timer)
  })

  const participantIds = $derived(
    Array.from({ length: status?.plannedParticipants ?? 0 }, (_, i) =>
      `P${String(i + 1).padStart(2, '0')}`,
    ),
  )

  function cell(pid: string, condition: string): SessionStatus | undefined {
    const n = parseInt(pid.slice(1), 10)
    return status?.sessions.find(
      (session) =>
        session.condition === condition &&
        parseInt(session.participantId.slice(1) || 'NaN', 10) === n,
    )
  }

  function integrity(session: SessionStatus): { cls: string; mark: string; label: string } {
    if (session.flaggedEvents > 0) return { cls: 'serious', mark: '!', label: 'Flagged rows' }
    if (session.gapCount > 0) return { cls: 'warning', mark: '!', label: 'Sequence gaps' }
    return { cls: 'good', mark: '✓', label: 'Gap-free' }
  }

  function formatRefresh(value: string | undefined): string {
    if (!value) return 'Awaiting first reading'
    const date = new Date(value)
    return Number.isNaN(date.getTime())
      ? 'Recently refreshed'
      : `Updated ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
  }

  const collected = $derived(status?.sessions.filter((session) => session.events > 0).length ?? 0)
  const plannedTotal = $derived(
    (status?.plannedParticipants ?? 0) * (status?.plannedSessionsPerParticipant ?? 0),
  )
  const collectionPercent = $derived(plannedTotal > 0 ? Math.round((collected / plannedTotal) * 100) : 0)
  const observedSessions = $derived(status?.sessions.filter((session) => session.events > 0) ?? [])
  const soundSessions = $derived(observedSessions.filter((session) => session.flaggedEvents === 0 && session.gapCount === 0).length)
  const flaggedSessions = $derived(observedSessions.filter((session) => session.flaggedEvents > 0 || session.gapCount > 0).length)
  const plannedRecipes = $derived(status?.researchQuestions.reduce((sum, rq) => sum + rq.recipes.length, 0) ?? 0)
  const completedRuns = $derived(status?.researchQuestions.reduce((sum, rq) => sum + rq.recipeRuns.length, 0) ?? 0)
</script>

<div class="overview">
  <header class="study-header">
    <div>
      <div class="eyebrow"><span class="live-dot" aria-hidden="true"></span>Study instrument</div>
      <h1>
        {protocol?.title ?? 'Study overview'}
        <span data-tour="trace-chip"><TraceChip id="FR-DASH-1" /></span>
      </h1>
      <p class="secondary">A live view of collection coverage, data integrity, and analysis readiness.</p>
    </div>
    {#if status && protocol}
      <div class="header-status" aria-label="Study status">
        <span class="phase">{status.lifecycle.currentPhase}</span>
        <span class="small muted">Protocol v{protocol.protocolVersion}</span>
        <span class="small muted">{refreshing ? 'Refreshing readings…' : formatRefresh(status.generatedAt)}</span>
      </div>
    {/if}
  </header>

  {#if error}
    <section class="state-card" aria-live="polite">
      <span class="state-mark" aria-hidden="true">!</span>
      <div>
        <h2>Readings are temporarily unavailable</h2>
        <p class="secondary">{error} Existing observations are unchanged. Check the connection and try again.</p>
      </div>
      <button type="button" onclick={load}>Retry now</button>
    </section>
  {:else if loading || !protocol || !status}
    <section class="loading-grid" aria-label="Loading study overview" aria-busy="true">
      <div class="skeleton wide"></div>
      <div class="skeleton"></div>
      <div class="skeleton"></div>
      <div class="skeleton full"></div>
      <p class="small muted">Calibrating collection and protocol readings…</p>
    </section>
  {:else}
    <section class="instrument-grid" aria-label="Study readings">
      <article class="instrument primary-reading" data-tour="overview-sessions">
        <div class="panel-head">
          <span>Collection coverage</span>
          <TraceChip id="FR-DASH-1" />
        </div>
        <div class="reading-row">
          <strong class="reading num">{collected}</strong>
          <span class="reading-unit">of {plannedTotal}<br />sessions observed</span>
        </div>
        <div class="track" aria-label={`${collectionPercent}% of sessions collected`}>
          <span style:width={`${collectionPercent}%`}></span>
        </div>
        <div class="reading-foot"><span>{collectionPercent}% complete</span><span>{Math.max(0, plannedTotal - collected)} remaining</span></div>
      </article>

      <article class="instrument">
        <div class="panel-head"><span>Data integrity</span><TraceChip id="FR-DASH-3" /></div>
        <div class="reading-row">
          <strong class="reading num">{soundSessions}</strong>
          <span class="reading-unit">gap-free<br />observations</span>
        </div>
        <div class="reading-foot">
          <span class="signal good"><b>✓</b> {soundSessions} clear</span>
          <span class:attention={flaggedSessions > 0} class="signal"><b>{flaggedSessions > 0 ? '!' : '✓'}</b> {flaggedSessions} review</span>
        </div>
      </article>

      <article class="instrument">
        <div class="panel-head"><span>Analysis readiness</span><TraceChip id="FR-DASH-4" /></div>
        <div class="reading-row">
          <strong class="reading num">{completedRuns}</strong>
          <span class="reading-unit">of {plannedRecipes}<br />recipe runs</span>
        </div>
        <div class="reading-foot"><span>{protocol.researchQuestions.length} questions tracked</span><span>{plannedRecipes} recipes planned</span></div>
      </article>
    </section>

    {#if plannedTotal === 0}
      <section class="empty-card">
        <h2>No collection plan is defined</h2>
        <p class="secondary">Add participants and conditions to the protocol to establish the observation matrix.</p>
      </section>
    {:else}
      <section class="workspace-grid">
        <article class="card protocol-panel">
          <div class="section-heading"><div><span class="section-index">01</span><h2>Protocol facts</h2></div><TraceChip id="FR-DASH-2" /></div>
          <dl class="facts">
            <div><dt>Researchers</dt><dd>{protocol.researchers.join(', ') || 'Not recorded'}</dd></div>
            <div><dt>Ethics reference</dt><dd>{protocol.ethicsRef || 'Not recorded'}</dd></div>
            <div><dt>Study design</dt><dd><Tip text="Within-subjects means every participant works in every condition, making each person their own comparison. Counterbalancing rotates the order to reduce practice effects."><span class="underline-dotted">{protocol.participants.design ?? 'Not specified'}{protocol.participants.counterbalanced ? ', counterbalanced' : ''}</span></Tip></dd></div>
            <div><dt>Conditions</dt><dd>{protocol.conditions.join(' · ')}</dd></div>
            <div><dt>Session duration</dt><dd>{protocol.session.durationMinutes ? `${protocol.session.durationMinutes} minutes` : 'Not specified'}</dd></div>
          </dl>
        </article>

        <article class="card rq-panel" data-tour="overview-rqs">
          <div class="section-heading"><div><span class="section-index">02</span><h2>Question coverage</h2></div><TraceChip id="FR-DASH-4" /></div>
          <div class="rq-list">
            {#each protocol.researchQuestions as rq, index (rq.id)}
              {@const coverage = status.researchQuestions.find((item) => item.id === rq.id)}
              <div class="rq-row">
                <span class="rq-number num">Q{String(index + 1).padStart(2, '0')}</span>
                <p>{rq.text}</p>
                <div class="rq-state">
                  {#if coverage && coverage.recipes.length > 0}
                    <span class="badge good">✓ {coverage.recipes.length} planned</span>
                    <span class="badge">{coverage.recipeRuns.length} run</span>
                  {:else}
                    <span class="badge critical">! Analysis missing</span>
                  {/if}
                  <TraceChip id={rq.id} />
                </div>
              </div>
            {/each}
          </div>
          {#if protocol.researchQuestions.length === 0}
            <p class="secondary empty-copy">No research questions are connected to this protocol yet.</p>
          {/if}
        </article>
      </section>

      <section class="card matrix-panel">
        <div class="section-heading">
          <div><span class="section-index">03</span><h2>Participant × condition matrix</h2></div>
          <div class="matrix-key small"><span><b>✓</b> Gap-free</span><span><b>!</b> Review</span><span>— Not collected</span><TraceChip id="FR-DASH-3" /></div>
        </div>
        <p class="secondary matrix-intro">Every planned observation remains visible. Open any collected cell to inspect its event timeline.</p>
        <div class="table-wrap">
          <table class="matrix">
            <thead><tr><th>Participant</th>{#each protocol.conditions as condition (condition)}<th>{condition}</th>{/each}</tr></thead>
            <tbody>
              {#each participantIds as pid (pid)}
                <tr>
                  <th scope="row" class="participant mono">{pid}</th>
                  {#each protocol.conditions as condition (condition)}
                    {@const session = cell(pid, condition)}
                    <td>
                      {#if session}
                        {@const state = integrity(session)}
                        <a class="session-cell {state.cls}" href={router.studyHref('sessions', session.sessionId)} use:link aria-label={`${pid}, ${condition}: ${state.label}, ${session.events} events. Open timeline.`}>
                          <span class="cell-top"><b>{state.mark} {state.label}</b><span class="num">{session.events} ev</span></span>
                          <span class="cell-action">Open timeline <span aria-hidden="true">→</span></span>
                        </a>
                      {:else}
                        <span class="uncollected"><b>—</b> Not collected</span>
                      {/if}
                    </td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}
  {/if}
</div>

<style>
  .overview { max-width: 1180px; }
  .study-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 22px; padding-bottom: 18px; border-bottom: 1px solid var(--baseline); }
  .study-header h1 { display: flex; align-items: center; gap: 8px; margin: 3px 0 2px; font-size: clamp(24px, 4vw, 38px); letter-spacing: -0.035em; line-height: 1.15; }
  .study-header p { margin: 0; max-width: 620px; }
  .eyebrow, .panel-head, .section-index { font-family: var(--mono); font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--text-muted); }
  .live-dot { display: inline-block; width: 7px; height: 7px; margin-right: 7px; border-radius: 50%; background: var(--status-good); }
  .header-status { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; white-space: nowrap; }
  .phase { align-self: flex-end; padding: 3px 9px; border: 1px solid var(--series-1); border-radius: 999px; color: var(--series-1); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
  .instrument-grid { display: grid; grid-template-columns: 1.25fr 1fr 1fr; gap: 1px; padding: 1px; margin-bottom: 14px; background: var(--border); border-radius: 11px; overflow: hidden; }
  .instrument { min-width: 0; padding: 15px 16px; background: var(--surface-1); }
  .primary-reading { box-shadow: inset 3px 0 0 var(--series-1); }
  .panel-head, .section-heading, .reading-row, .reading-foot, .cell-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .reading-row { justify-content: flex-start; margin: 18px 0 16px; }
  .reading { font-size: clamp(34px, 5vw, 52px); line-height: .9; letter-spacing: -.05em; font-weight: 650; }
  .reading-unit { color: var(--text-muted); font-size: 12px; line-height: 1.35; }
  .track { height: 4px; overflow: hidden; background: var(--grid); }
  .track span { display: block; height: 100%; background: var(--series-1); }
  .reading-foot { margin-top: 10px; color: var(--text-muted); font-size: 11px; }
  .signal b, .matrix-key b { color: var(--status-good); }
  .signal.attention b { color: var(--status-serious); }
  .workspace-grid { display: grid; grid-template-columns: minmax(250px, .75fr) minmax(360px, 1.25fr); gap: 14px; margin-bottom: 14px; }
  .section-heading { margin-bottom: 13px; padding-bottom: 10px; border-bottom: 1px solid var(--grid); }
  .section-heading > div:first-child { display: flex; align-items: baseline; gap: 10px; }
  .section-heading h2 { margin: 0; }
  .section-index { color: var(--series-1); }
  .facts { margin: 0; }
  .facts div { display: grid; grid-template-columns: 105px 1fr; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--grid); }
  .facts div:last-child { border-bottom: 0; }
  .facts dt { color: var(--text-muted); font-size: 12px; }
  .facts dd { margin: 0; }
  .rq-list { display: flex; flex-direction: column; }
  .rq-row { display: grid; grid-template-columns: 36px 1fr auto; align-items: center; gap: 10px; min-height: 52px; padding: 7px 0; border-bottom: 1px solid var(--grid); }
  .rq-row:last-child { border-bottom: 0; }
  .rq-row p { margin: 0; color: var(--text-secondary); }
  .rq-number { color: var(--series-1); font-size: 11px; }
  .rq-state { display: flex; align-items: center; justify-content: flex-end; gap: 5px; }
  .empty-copy { padding: 16px 0 4px; }
  .matrix-panel { padding-bottom: 8px; }
  .matrix-key { display: flex; align-items: center; gap: 12px; color: var(--text-muted); }
  .matrix-intro { margin: -4px 0 12px; font-size: 12px; }
  .table-wrap { overflow-x: auto; }
  .matrix { width: 100%; min-width: 620px; border-collapse: collapse; }
  .matrix th { padding: 8px 10px; color: var(--text-muted); font-size: 11px; font-weight: 600; text-align: left; border-bottom: 1px solid var(--baseline); }
  .matrix td { min-width: 185px; padding: 5px; border-bottom: 1px solid var(--grid); border-left: 1px solid var(--grid); }
  .matrix tbody tr:last-child td, .matrix tbody tr:last-child th { border-bottom: 0; }
  .participant { width: 95px; color: var(--text-primary) !important; }
  .session-cell { display: flex; flex-direction: column; gap: 5px; min-height: 50px; padding: 7px 9px; border-left: 2px solid var(--status-good); color: var(--text-primary); background: color-mix(in srgb, var(--status-good) 5%, transparent); }
  .session-cell:hover { background: color-mix(in srgb, var(--status-good) 9%, transparent); text-decoration: none; }
  .session-cell.warning, .session-cell.serious { border-left-color: var(--status-serious); background: color-mix(in srgb, var(--status-serious) 6%, transparent); }
  .cell-top { font-size: 11px; }
  .cell-top b { font-weight: 600; }
  .cell-top .num, .cell-action { color: var(--text-muted); }
  .cell-action { font-size: 11px; }
  .uncollected { display: flex; align-items: center; gap: 7px; min-height: 50px; padding: 7px 9px; color: var(--text-muted); font-size: 11px; }
  .state-card, .empty-card { display: flex; align-items: center; gap: 16px; padding: 22px; background: var(--surface-1); border: 1px solid var(--border); border-left: 3px solid var(--status-serious); border-radius: 10px; }
  .state-card div { flex: 1; }
  .state-card h2, .state-card p, .empty-card h2, .empty-card p { margin: 0; }
  .state-mark { display: grid; place-items: center; flex: 0 0 32px; height: 32px; border: 1px solid var(--status-serious); border-radius: 50%; color: var(--status-serious); font-weight: 700; }
  .empty-card { display: block; border-left-color: var(--series-1); }
  .loading-grid { display: grid; grid-template-columns: 1.25fr 1fr 1fr; gap: 14px; }
  .skeleton { min-height: 148px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface-1); position: relative; overflow: hidden; }
  .skeleton::after { content: ''; position: absolute; inset: 18px; border-top: 8px solid var(--grid); border-bottom: 8px solid var(--grid); opacity: .55; }
  .skeleton.full { grid-column: 1 / -1; min-height: 260px; }
  .loading-grid p { grid-column: 1 / -1; }
  @media (prefers-reduced-motion: no-preference) {
    .live-dot { animation: breathe 2.4s ease-in-out infinite; }
    .instrument, .workspace-grid > *, .matrix-panel { animation: settle .35s ease-out both; }
    .workspace-grid > * { animation-delay: .06s; }
    .matrix-panel { animation-delay: .12s; }
    @keyframes breathe { 50% { opacity: .35; } }
    @keyframes settle { from { opacity: 0; transform: translateY(5px); } }
  }
  @media (max-width: 920px) {
    .instrument-grid { grid-template-columns: 1fr 1fr; }
    .primary-reading { grid-column: 1 / -1; }
    .workspace-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 620px) {
    .study-header { align-items: flex-start; flex-direction: column; }
    .header-status { align-items: flex-start; }
    .phase { align-self: flex-start; }
    .instrument-grid, .loading-grid { grid-template-columns: 1fr; }
    .primary-reading, .skeleton.full { grid-column: auto; }
    .rq-row { grid-template-columns: 32px 1fr; }
    .rq-state { grid-column: 2; justify-content: flex-start; }
    .section-heading { align-items: flex-start; }
    .matrix-panel .section-heading { flex-direction: column; }
    .matrix-key { flex-wrap: wrap; }
    .state-card { align-items: flex-start; flex-wrap: wrap; }
    .state-card button { margin-left: 48px; }
  }
</style>
