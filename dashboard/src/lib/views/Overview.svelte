<script lang="ts">
  import { api, type ProtocolSummary, type SessionStatus, type StatusDoc } from '../api'
  import { link, router } from '../router.svelte'
  import Tip from '../components/Tip.svelte'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()

  let protocol = $state<ProtocolSummary | null>(null)
  let status = $state<StatusDoc | null>(null)
  let error = $state<string | null>(null)

  async function load(): Promise<void> {
    try {
      ;[protocol, status] = await Promise.all([
        api.protocol(studyId),
        api.status(studyId),
      ])
      error = null
    } catch (e) {
      error = String(e)
    }
  }
  $effect(() => {
    load()
    const timer = setInterval(load, 10_000)
    return () => clearInterval(timer)
  })

  /** P1..P<planned>, zero-padded like the pilot convention. */
  const participantIds = $derived(
    Array.from({ length: status?.plannedParticipants ?? 0 }, (_, i) =>
      `P${String(i + 1).padStart(2, '0')}`,
    ),
  )

  function cell(pid: string, condition: string): SessionStatus | undefined {
    const n = parseInt(pid.slice(1), 10)
    return status?.sessions.find(
      (s) =>
        s.condition === condition &&
        parseInt(s.participantId.slice(1) || 'NaN', 10) === n,
    )
  }

  function integrity(s: SessionStatus): { cls: string; label: string } {
    if (s.flaggedEvents > 0) return { cls: 'serious', label: 'flagged rows' }
    if (s.gapCount > 0) return { cls: 'warning', label: 'seq gaps' }
    return { cls: 'good', label: 'gap-free' }
  }

  const collected = $derived(status?.sessions.filter((s) => s.events > 0).length ?? 0)
  const plannedTotal = $derived(
    (status?.plannedParticipants ?? 0) * (status?.plannedSessionsPerParticipant ?? 0),
  )
</script>

<h1>Overview <span data-tour="trace-chip"><TraceChip id="FR-DASH-1" /></span></h1>

{#if error}
  <div class="card"><p class="secondary">Failed to load: {error}</p></div>
{:else if protocol && status}
  <section class="grid">
    <div class="card">
      <h2>{protocol.title}</h2>
      <table class="facts">
        <tbody>
          <tr><td class="muted">Protocol</td><td><code>{protocol.studyId}</code> v{protocol.protocolVersion}</td></tr>
          <tr><td class="muted">Researchers</td><td>{protocol.researchers.join(', ')}</td></tr>
          <tr><td class="muted">Ethics</td><td>{protocol.ethicsRef}</td></tr>
          <tr>
            <td class="muted">Design</td>
            <td>
              <Tip
                text="Within-subjects: every participant works in every condition, so each person is their own comparison. Counterbalanced: the order is rotated between participants so practice effects don't favor one condition."
              >
                <span class="underline-dotted"
                  >{protocol.participants.design}, {protocol.conditions.join(' vs ')},
                  counterbalanced</span
                >
              </Tip>
            </td>
          </tr>
          <tr><td class="muted">Phase</td><td><span class="badge">{status.lifecycle.currentPhase}</span> (computed)</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card" data-tour="overview-sessions">
      <h2>Sessions collected</h2>
      <div class="hero num-plain">{collected}<span class="of muted">/ {plannedTotal} planned</span></div>
      <p class="small muted">
        {status.plannedParticipants} participants x {status.plannedSessionsPerParticipant}
        conditions ({protocol.participants.design}).
      </p>
    </div>
  </section>

  <section class="card" data-tour="overview-rqs">
    <h2>Research questions <span class="small muted">coverage from the analysis plan</span></h2>
    <ul class="rqs">
      {#each protocol.researchQuestions as rq (rq.id)}
        {@const cov = status.researchQuestions.find((r) => r.id === rq.id)}
        <li>
          <TraceChip id={rq.id} />
          <span class="rq-text secondary">{rq.text}</span>
          {#if cov && cov.recipes.length > 0}
            <span class="badge good">✓ {cov.recipes.length} recipe{cov.recipes.length === 1 ? '' : 's'} planned</span>
            <span class="badge">{cov.recipeRuns.length} ran</span>
          {:else}
            <span class="badge critical">! no recipe planned</span>
          {/if}
        </li>
      {/each}
    </ul>
  </section>

  <section class="card">
    <h2>Participant grid <span class="small muted">planned vs collected, with integrity badges</span></h2>
    <p class="small muted">
      ✓ gap-free: every event arrived · ! seq gaps: some events were lost in
      transit (always detected, never silent) · ! flagged rows: data outside
      the plan (kept and marked, never dropped)
    </p>
    <table class="data">
      <thead>
        <tr>
          <th>Participant</th>
          {#each protocol.conditions as c (c)}
            <th>{c}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each participantIds as pid (pid)}
          <tr>
            <td class="mono">{pid}</td>
            {#each protocol.conditions as c (c)}
              {@const s = cell(pid, c)}
              <td>
                {#if s}
                  {@const badge = integrity(s)}
                  <a href={router.studyHref('sessions', s.sessionId)} use:link class="mono small">
                    {s.sessionId}
                  </a>
                  <span class="badge {badge.cls}">
                    {badge.cls === 'good' ? '✓' : '!'} {badge.label}
                  </span>
                  <span class="small muted num">{s.events} ev</span>
                {:else}
                  <span class="muted">- not collected</span>
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
{:else}
  <p class="muted">Loading…</p>
{/if}

<style>
  .grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 14px;
    margin-bottom: 14px;
  }
  section.card {
    margin-bottom: 14px;
  }
  .facts td {
    padding: 2px 12px 2px 0;
    vertical-align: top;
  }
  .hero {
    font-size: 48px;
    font-weight: 600;
    line-height: 1.1;
  }
  .hero .of {
    font-size: 16px;
    font-weight: 400;
    margin-left: 8px;
  }
  .rqs {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .rqs li {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 6px 0;
    border-bottom: 1px solid var(--grid);
  }
  .rqs li:last-child {
    border-bottom: none;
  }
  .rq-text {
    flex: 1;
  }
</style>
