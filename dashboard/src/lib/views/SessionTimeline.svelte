<script lang="ts">
  import { api, type GapReport, type StudyEvent } from '../api'
  import { assembleLanes, type LaneItem } from '../lanes'
  import Timeline from '../components/Timeline.svelte'
  import TraceChip from '../components/TraceChip.svelte'

  // Sessions are addressed directly by id; the study only scopes the route.
  let { sessionId }: { sessionId: string } = $props()

  let events = $state<StudyEvent[]>([])
  let gaps = $state<GapReport | null>(null)
  let error = $state<string | null>(null)
  let selectedSeqs = $state<number[]>([])

  async function load(): Promise<void> {
    try {
      events = await api.events(sessionId)
      error = null
    } catch (e) {
      error = String(e)
      return
    }
    try {
      gaps = await api.gaps(sessionId)
    } catch {
      gaps = null
    }
  }
  $effect(() => {
    sessionId
    selectedSeqs = []
    load()
  })

  const lanes = $derived(assembleLanes(events))
  const first = $derived(events[0])
  const legsPresent = $derived(new Set(lanes.map((l) => l.leg)).size)

  // ---- conversation view (agent leg, MP-12) --------------------------------
  const AGENT_TYPES = new Set(['agent_turn', 'tool_call', 'task_outcome'])
  const agentEvents = $derived(events.filter((e) => AGENT_TYPES.has(e.type)))

  /** Content policy (FR-ETH-2 rev 2/FR-AGENT-5): text renders only when the
   * capture stored it - i.e. the protocol allowed `redacted`/`full`. A
   * metadata-only capture has no text fields, so structure-only is what a
   * metadata-only policy shows. */
  const turnText = (e: StudyEvent): string | null => {
    const t = e.payload.text ?? e.payload.content
    return typeof t === 'string' ? t : null
  }

  const str = (v: unknown): string => (typeof v === 'string' ? v : '')
  const num = (v: unknown): number | null =>
    typeof v === 'number' && Number.isFinite(v) ? v : null

  function onTimelineSelect(item: LaneItem): void {
    selectedSeqs = item.seqs
    const el = document.getElementById(`turn-${item.seqs[0]}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  function selectTurn(e: StudyEvent): void {
    selectedSeqs = [e.seq]
  }
</script>

<h1>
  Session <span class="mono">{sessionId}</span>
  <TraceChip id="FR-DASH-4" />
</h1>

{#if error}
  <div class="card"><p class="secondary">Failed to load: {error}</p></div>
{:else if events.length === 0}
  <div class="card"><p class="muted">No events for this session yet.</p></div>
{:else}
  <p class="secondary small">
    {#if first}
      {first.participantId} · {first.condition} · {events.length} events ·
      {lanes.length} lanes from {legsPresent} leg{legsPresent === 1 ? '' : 's'}
      on one time axis
    {/if}
    {#if gaps && !gaps.complete}
      <span class="badge serious">
        ! {gaps.expected - gaps.received} missing (seq gaps: {gaps.gaps.length})
      </span>
    {:else if gaps}
      <span class="badge good">✓ gap-free</span>
    {/if}
  </p>

  <div data-tour="timeline">
    <Timeline {lanes} {selectedSeqs} onselect={onTimelineSelect} />
  </div>

  <section class="card conversation">
    <h2>
      Agent conversation
      <span class="small muted">linked with the timeline - click either side</span>
    </h2>
    {#if agentEvents.length === 0}
      <p class="secondary">
        No AI conversation in this session - this panel fills when the
        participant works with an AI agent (Claude Code) during the session.
        What is stored (full text, redacted, or structure only) follows the
        content policy the participant consented to.
      </p>
    {:else}
      <ol class="turns">
        {#each agentEvents as e (e.seq)}
          <li
            id={`turn-${e.seq}`}
            class:selected={selectedSeqs.includes(e.seq)}
          >
            <button class="turn" onclick={() => selectTurn(e)}>
              <span class="mono small muted">seq {e.seq}</span>
              {#if e.type === 'agent_turn'}
                <strong>{str(e.payload.role) || 'agent'}</strong>
                {#if num(e.payload.responseChars) !== null}
                  <span class="small muted num">{num(e.payload.responseChars)} chars</span>
                {/if}
                {#if turnText(e)}
                  <div class="text secondary">{turnText(e)}</div>
                {:else}
                  <div class="small muted">
                    structure and sizes only - the consented privacy policy
                    (metadata-only) stores no conversation text
                  </div>
                {/if}
              {:else if e.type === 'tool_call'}
                <strong>tool</strong>
                <code>{str(e.payload.tool) || 'unknown'}</code>
              {:else}
                <strong>task outcome</strong>
                <span class="badge {e.payload.passed ? 'good' : 'serious'}">
                  {e.payload.passed ? '✓ passed' : '! failed'}
                </span>
              {/if}
            </button>
          </li>
        {/each}
      </ol>
    {/if}
  </section>
{/if}

<style>
  section.conversation {
    margin-top: 14px;
  }
  .turns {
    list-style: none;
    margin: 0;
    padding: 0;
    max-height: 320px;
    overflow-y: auto;
  }
  .turns li {
    border-left: 3px solid var(--grid);
    margin: 4px 0;
  }
  .turns li.selected {
    border-left-color: var(--series-8);
    background: color-mix(in srgb, var(--series-8) 8%, transparent);
  }
  .turn {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    padding: 6px 10px;
    cursor: pointer;
  }
  .text {
    white-space: pre-wrap;
    margin-top: 4px;
  }
</style>
