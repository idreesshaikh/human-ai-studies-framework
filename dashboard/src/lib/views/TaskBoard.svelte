<script lang="ts">
  import { dndzone, type DndEvent } from 'svelte-dnd-action'
  import { api, type ManualTask, type StatusDoc } from '../api'
  import { deriveCards, type Card } from '../derive'
  import { link, router } from '../router.svelte'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()
  let status = $state<StatusDoc | null>(null)
  let manual = $state<ManualTask[]>([])
  let error = $state<string | null>(null)
  let newTitle = $state('')
  let newNote = $state('')
  let todoItems = $state<Card[]>([])
  let doneItems = $state<Card[]>([])
  let exiting = $state<Card[]>([])
  let knownDerived = new Map<string, Card>()
  let newIds = $state<Set<string>>(new Set())

  const severity: Record<Card['kind'], number> = { integrity: 0, gate: 1, 'rq-uncovered': 1, 'recipe-unrun': 1, finding: 1, 'participant-data': 2, manual: 3 }
  const kindLabel: Record<Card['kind'], string> = { integrity: 'Data integrity', gate: 'Missing gate', 'rq-uncovered': 'Research coverage', 'recipe-unrun': 'Analysis pending', finding: 'Operational finding', 'participant-data': 'Collection progress', manual: 'Researcher task' }
  const derived = $derived(status ? deriveCards(status, manual).filter((card) => card.kind !== 'manual').sort((a, b) => severity[a.kind] - severity[b.kind] || a.title.localeCompare(b.title)) : [])

  function syncManual(): void {
    const cards = status ? deriveCards(status, manual).filter((card) => card.kind === 'manual') : []
    todoItems = cards.filter((card) => card.column !== 'done')
    doneItems = cards.filter((card) => card.column === 'done')
  }

  function animateDerived(next: Card[]): void {
    const nextMap = new Map(next.map((card) => [card.id, card]))
    const arrivals = next.filter((card) => !knownDerived.has(card.id)).map((card) => card.id)
    const removals = [...knownDerived.values()].filter((card) => !nextMap.has(card.id))
    newIds = new Set(arrivals)
    if (removals.length) {
      exiting = [...exiting, ...removals]
      setTimeout(() => (exiting = exiting.filter((card) => !removals.some((old) => old.id === card.id))), 250)
    }
    knownDerived = nextMap
    setTimeout(() => (newIds = new Set()), 300)
  }

  async function load(): Promise<void> {
    try {
      ;[status, manual] = await Promise.all([api.status(studyId), api.tasks()])
      const next = status ? deriveCards(status, manual).filter((card) => card.kind !== 'manual') : []
      animateDerived(next)
      syncManual()
      error = null
    } catch (cause) { error = String(cause) }
  }

  $effect(() => {
    studyId
    load()
    const timer = setInterval(load, 5_000)
    return () => clearInterval(timer)
  })

  async function addManual(event: SubmitEvent): Promise<void> {
    event.preventDefault()
    if (!newTitle.trim()) return
    await api.addTask(newTitle.trim(), newNote.trim())
    newTitle = ''; newNote = ''; await load()
  }

  async function persist(card: Card, done: boolean): Promise<void> {
    if (card.manualId === undefined) return
    try { await api.setTaskStatus(card.manualId, done ? 'done' : 'open'); await load() }
    catch (cause) { error = String(cause); await load() }
  }

  function consider(event: CustomEvent<DndEvent<Card>>, target: 'todo' | 'done'): void {
    if (target === 'todo') todoItems = event.detail.items
    else doneItems = event.detail.items
  }

  async function finalize(event: CustomEvent<DndEvent<Card>>, target: 'todo' | 'done'): Promise<void> {
    const moved = [...todoItems, ...doneItems, ...event.detail.items].find(
      (item) => item.id === event.detail.info.id,
    )
    consider(event, target)
    if (moved) await persist(moved, target === 'done')
  }

  function actionHref(card: Card): string {
    if (card.kind === 'gate') return router.studyHref('board')
    if (card.kind === 'integrity') {
      const sessionId = card.id.split(':').at(-1)
      return sessionId ? router.studyHref('sessions', sessionId) : router.studyHref('live')
    }
    if (card.kind === 'recipe-unrun' || card.kind === 'rq-uncovered') return router.studyHref('metrics')
    return router.studyHref('overview')
  }
</script>

<header class="page-head">
  <div><p class="eyebrow">Research operations</p><h1>Task board <TraceChip id="FR-DASH-7" /></h1><p class="secondary">Platform-filed issues heal themselves when their underlying cause is fixed. Researcher tasks are yours to move.</p></div>
  <button onclick={load}>Refresh</button>
</header>

{#if error}<div class="card error" role="alert"><strong>Board unavailable</strong><span>{error}</span><button onclick={load}>Try again</button></div>{/if}

{#if status}
  <div class="board" data-tour="task-board">
    <section class="column attention" aria-labelledby="attention-title">
      <header><div><p class="kicker">Platform queue</p><h2 id="attention-title">Needs attention</h2></div><span class="count">{derived.length}</span></header>
      <div class="stack">
        {#each derived as card (card.id)}
          <article class:arriving={newIds.has(card.id)} class="task derived {card.kind}">
            <p class="kind">{kindLabel[card.kind]}</p><h3>{card.title}</h3><p>{card.what}</p>
            <div class="card-foot"><span>filed by the platform</span><a href={actionHref(card)} use:link>Fix this</a></div>
          </article>
        {/each}
        {#each exiting as card (card.id)}<article class="task derived clearing {card.kind}" aria-hidden="true"><p class="kind">Resolved</p><h3>{card.title}</h3></article>{/each}
        {#if derived.length === 0 && exiting.length === 0}<div class="empty"><strong>Nothing needs you.</strong><p>The platform will file a card here the moment something does.</p></div>{/if}
      </div>
    </section>

    <section class="column" aria-labelledby="todo-title">
      <header><div><p class="kicker">Researcher queue</p><h2 id="todo-title">To do</h2></div><span class="count">{todoItems.length}</span></header>
      <div class="stack manual-zone" use:dndzone={{ items: todoItems, flipDurationMs: 180, dropTargetStyle: { outline: '1px dashed var(--series-1)' } }} onconsider={(e) => consider(e, 'todo')} onfinalize={(e) => finalize(e, 'todo')}>
        {#each todoItems as card (card.id)}<article class="task manual"><span class="drag" aria-hidden="true">⋮⋮</span><h3>{card.title}</h3><p>{card.what}</p><div class="card-foot"><span>filed by researcher</span><button onclick={() => persist(card, true)}>Move to Done</button></div></article>{/each}
      </div>
      <form class="add" onsubmit={addManual}><label for="task-title">New researcher task</label><input id="task-title" placeholder="What needs doing?" bind:value={newTitle} />{#if newTitle.trim()}<input aria-label="Task note" placeholder="Note (optional)" bind:value={newNote} /><button class="primary" type="submit">Add task</button>{/if}</form>
    </section>

    <section class="column" aria-labelledby="done-title">
      <header><div><p class="kicker">Completed</p><h2 id="done-title">Done</h2></div><span class="count">{doneItems.length}</span></header>
      <div class="stack manual-zone" use:dndzone={{ items: doneItems, flipDurationMs: 180, dropTargetStyle: { outline: '1px dashed var(--series-1)' } }} onconsider={(e) => consider(e, 'done')} onfinalize={(e) => finalize(e, 'done')}>
        {#each doneItems as card (card.id)}<article class="task manual complete"><span class="drag" aria-hidden="true">⋮⋮</span><h3>{card.title}</h3><p>{card.what}</p><div class="card-foot"><span>completed</span><button onclick={() => persist(card, false)}>Reopen</button></div></article>{/each}
      </div>
    </section>
  </div>
{:else if !error}<div class="loading" aria-live="polite">Assembling the live task projection…</div>{/if}

<style>
  .page-head,.column>header,.card-foot{display:flex;align-items:center;justify-content:space-between;gap:12px}.page-head{margin-bottom:18px}.page-head h1{margin:2px 0}.page-head p{max-width:720px;margin:0}.eyebrow,.kicker,.kind{margin:0;color:var(--text-muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.board{display:grid;grid-template-columns:minmax(260px,1.2fr) repeat(2,minmax(230px,1fr));gap:12px;align-items:start}.column{min-height:420px;background:color-mix(in srgb,var(--text-muted) 5%,var(--surface-1));border:1px solid var(--border);border-radius:12px;padding:12px}.column h2{font-size:16px;margin:2px 0}.count{display:grid;place-items:center;min-width:28px;height:28px;border:1px solid var(--border);border-radius:999px;font-variant-numeric:tabular-nums}.stack{display:flex;flex-direction:column;gap:8px;margin-top:12px;min-height:48px}.task{position:relative;background:var(--surface-1);border:1px solid var(--border);border-radius:9px;padding:11px 12px}.task h3{font-size:14px;margin:3px 0}.task p:not(.kind){margin:0;color:var(--text-secondary);font-size:12px;line-height:1.5}.derived{border-left:3px solid var(--series-1)}.derived.integrity{border-left-color:var(--status-serious)}.derived.participant-data{border-left-color:var(--status-good)}.card-foot{margin-top:10px;color:var(--text-muted);font-size:11px}.card-foot a,.card-foot button{font-size:12px}.manual{cursor:grab;padding-left:28px}.manual:active{cursor:grabbing}.manual.complete{opacity:.68}.drag{position:absolute;left:9px;top:11px;color:var(--text-muted);letter-spacing:-2px}.arriving{animation:arrive 240ms ease-out}.clearing{animation:heal 250ms ease-in forwards;overflow:hidden}.empty{border:1px dashed var(--border);border-radius:9px;padding:22px 14px;text-align:center;color:var(--text-secondary)}.empty p{margin:6px 0 0;font-size:12px}.add{display:flex;flex-direction:column;gap:7px;margin-top:12px;padding-top:12px;border-top:1px solid var(--grid)}.add label{font-size:12px;color:var(--text-secondary)}.error{display:flex;align-items:center;gap:12px;margin-bottom:12px}.loading{padding:30px;color:var(--text-muted)}@keyframes arrive{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}@keyframes heal{to{opacity:0;transform:scaleY(.85);max-height:0;padding-block:0;margin:0}}@media(max-width:850px){.board{grid-template-columns:1fr}.column{min-height:auto}.page-head{align-items:flex-start}}@media(prefers-reduced-motion:reduce){.arriving,.clearing{animation:none}}
</style>
