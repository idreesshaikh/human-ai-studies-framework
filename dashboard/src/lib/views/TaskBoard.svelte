<script lang="ts">
  import { api, type ManualTask, type StatusDoc } from '../api'
  import { deriveCards, type Card, type Column } from '../derive'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()

  let status = $state<StatusDoc | null>(null)
  let manual = $state<ManualTask[]>([])
  let error = $state<string | null>(null)
  let selected = $state<Card | null>(null)
  let newTitle = $state('')
  let newNote = $state('')

  async function load(): Promise<void> {
    try {
      ;[status, manual] = await Promise.all([api.status(studyId), api.tasks()])
      error = null
    } catch (e) {
      error = String(e)
    }
  }
  // The board is a projection: re-derived on every poll, cards clear
  // themselves when the middleware reports the condition satisfied.
  $effect(() => {
    load()
    const timer = setInterval(load, 5_000)
    return () => clearInterval(timer)
  })

  const cards = $derived(status ? deriveCards(status, manual) : [])

  const COLUMNS: { key: Column; label: string; hint: string }[] = [
    { key: 'blocked', label: 'Blocked', hint: 'gated behind an earlier phase' },
    { key: 'todo', label: 'To do', hint: 'actionable now' },
    { key: 'waiting', label: 'Waiting on data', hint: 'clears as sessions land' },
    { key: 'done', label: 'Done', hint: 'auto-archived' },
  ]

  async function addManual(e: SubmitEvent): Promise<void> {
    e.preventDefault()
    if (!newTitle.trim()) return
    await api.addTask(newTitle.trim(), newNote.trim())
    newTitle = ''
    newNote = ''
    await load()
  }

  async function setDone(card: Card, done: boolean): Promise<void> {
    if (card.manualId === undefined) return
    await api.setTaskStatus(card.manualId, done ? 'done' : 'open')
    await load()
  }

  const KIND_LABEL: Record<Card['kind'], string> = {
    gate: 'gate artifact',
    'rq-uncovered': 'uncovered RQ',
    'recipe-unrun': 'un-run recipe',
    'participant-data': 'missing sessions',
    integrity: 'integrity',
    finding: 'operational finding',
    manual: 'manual',
  }
</script>

<h1>Task board <TraceChip id="FR-DASH-7" /></h1>
<p class="secondary small">
  Derived cards are a <strong>projection</strong> of the protocol + middleware
  state - they appear and clear themselves; only manual cards are stored.
</p>

{#if error}
  <div class="card"><p class="secondary">Failed to load: {error}</p></div>
{:else if status}
  <div class="board" data-tour="task-board">
    {#each COLUMNS as col (col.key)}
      {@const colCards = cards.filter((c) => c.column === col.key)}
      <div class="column">
        <header>
          <h3>{col.label} <span class="muted num">{colCards.length}</span></h3>
          <div class="small muted">{col.hint}</div>
        </header>
        {#each colCards as card (card.id)}
          <button class="task {card.kind}" onclick={() => (selected = card)}>
            <div class="kind small muted">
              {KIND_LABEL[card.kind]}
              {#if card.kind !== 'manual'}<span class="auto">auto</span>{/if}
            </div>
            <div class="title">{card.title}</div>
            <div class="small secondary">{card.what}</div>
          </button>
        {/each}
        {#if col.key === 'todo'}
          <form class="add" onsubmit={addManual}>
            <input placeholder="Add a manual task…" bind:value={newTitle} />
            {#if newTitle.trim()}
              <input placeholder="Note (optional)" bind:value={newNote} />
              <button class="primary" type="submit">Add</button>
            {/if}
          </form>
        {/if}
      </div>
    {/each}
  </div>
{:else}
  <p class="muted">Loading…</p>
{/if}

{#if selected}
  <aside class="detail card" aria-label="Card detail">
    <header>
      <h3>{selected.title}</h3>
      <button onclick={() => (selected = null)} aria-label="Close">x</button>
    </header>
    <dl>
      <dt>What</dt>
      <dd>{selected.what}</dd>
      <dt>Why</dt>
      <dd>{selected.why}</dd>
      <dt>How to clear it</dt>
      <dd>{selected.how}</dd>
    </dl>
    <TraceChip id={selected.trace} />
    {#if selected.manualId !== undefined}
      <div class="actions">
        {#if selected.column === 'done'}
          <button onclick={() => selected && setDone(selected, false)}>Reopen</button>
        {:else}
          <button class="primary" onclick={() => selected && setDone(selected, true)}>
            Mark done
          </button>
        {/if}
      </div>
    {/if}
  </aside>
{/if}

<style>
  .board {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    align-items: start;
  }
  .column {
    background: color-mix(in srgb, var(--text-muted) 5%, transparent);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .column header {
    margin-bottom: 2px;
  }
  .task {
    text-align: left;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 10px;
    cursor: pointer;
    display: block;
    width: 100%;
  }
  .task:hover {
    border-color: var(--text-muted);
  }
  .task .title {
    font-weight: 600;
    margin: 2px 0;
  }
  .task.integrity {
    border-left: 3px solid var(--status-serious);
  }
  .task.gate {
    border-left: 3px solid var(--series-1);
  }
  .task.participant-data {
    border-left: 3px solid var(--series-3);
  }
  .task.manual {
    border-left: 3px solid var(--baseline);
  }
  .auto {
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0 4px;
    margin-left: 4px;
    font-size: 10px;
  }
  .add {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .detail {
    position: fixed;
    right: 16px;
    bottom: 16px;
    width: 380px;
    z-index: 30;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  }
  .detail header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
  }
  dt {
    font-weight: 600;
    margin-top: 8px;
  }
  dd {
    margin: 2px 0 0;
    color: var(--text-secondary);
  }
  .actions {
    margin-top: 10px;
  }
</style>
