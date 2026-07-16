<script lang="ts">
  /**
   * Knowledge layer (FR-DASH-8): the related-papers graph (FR-LIT-2), paper
   * ingest (FR-LIT-1), protocol-element links (FR-LIT-3), and the grounded
   * assistant (FR-LIT-4). Seed -> neighbourhood -> grow, ResearchRabbit-style
   * on open data; the assistant only ever sees aggregates (FR-ETH-4, enforced
   * server-side).
   */
  import { api, type Paper, type PaperGraph, type AssistantAnswer } from '../api'
  import { layoutGraph, ingestIdForRef, type PositionedNode } from '../graph'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()

  let papers = $state<Paper[]>([])
  let graph = $state<PaperGraph | null>(null)
  let error = $state<string | null>(null)
  let busy = $state(false)

  let idInput = $state('')
  let zoteroInput = $state('')
  let zoteroNote = $state<string | null>(null)
  let selected = $state<string | null>(null)
  let linkDraft = $state('')

  const EDGE_COLOR: Record<string, string> = {
    references: 'var(--series-1)',
    citations: 'var(--series-2)',
    recommendations: 'var(--series-5)',
  }
  const W = 640
  const H = 440

  async function load(): Promise<void> {
    try {
      ;[papers, graph] = await Promise.all([
        api.papers(studyId),
        api.papersGraph(studyId),
      ])
      error = null
    } catch (e) {
      error = String(e)
    }
  }
  $effect(() => {
    load()
  })

  const positioned = $derived<PositionedNode[]>(
    graph ? layoutGraph(graph.nodes, graph.edges, { width: W, height: H }) : [],
  )
  const posByRef = $derived(new Map(positioned.map((n) => [n.paperRef, n])))
  const selectedPaper = $derived(papers.find((p) => p.paperRef === selected) ?? null)
  const selectedNode = $derived(positioned.find((n) => n.paperRef === selected) ?? null)

  function radius(n: PositionedNode): number {
    const base = n.ingested ? 9 : 5
    return base + Math.min(6, Math.log10((n.citationCount ?? 0) + 1) * 2)
  }

  async function ingestById(): Promise<void> {
    const raw = idInput.trim()
    if (!raw) return
    const id = raw.toLowerCase().includes('arxiv')
      ? { arxivId: raw.replace(/.*arxiv[:/]?/i, '') }
      : /^10\./.test(raw)
        ? { doi: raw }
        : { arxivId: raw }
    await run(() => api.ingestPaper(studyId, id))
    idInput = ''
  }

  async function addSuggestion(ref: string): Promise<void> {
    const id = ingestIdForRef(ref)
    if (id) await run(() => api.ingestPaper(studyId, id))
  }

  async function importZotero(): Promise<void> {
    const collection = zoteroInput.trim()
    if (!collection) return
    zoteroNote = null
    await run(async () => {
      const res = await api.zoteroImport(studyId, collection)
      zoteroNote = `${res.imported} imported, ${res.duplicates} already present`
    })
    zoteroInput = ''
  }

  async function uploadPdf(ev: Event): Promise<void> {
    const file = (ev.target as HTMLInputElement).files?.[0]
    if (file) await run(() => api.uploadPaperPdf(studyId, file))
  }

  async function removePaper(ref: string): Promise<void> {
    await run(() => api.deletePaper(studyId, ref))
    if (selected === ref) selected = null
  }

  async function run<T>(fn: () => Promise<T>): Promise<void> {
    busy = true
    try {
      await fn()
      await load()
      error = null
    } catch (e) {
      error = String(e)
    } finally {
      busy = false
    }
  }

  function select(ref: string): void {
    selected = ref
    const p = papers.find((x) => x.paperRef === ref)
    linkDraft = (p?.links ?? []).join(', ')
  }

  async function saveLinks(): Promise<void> {
    if (!selected) return
    const targets = linkDraft.split(',').map((t) => t.trim()).filter(Boolean)
    await run(() => api.setPaperLinks(studyId, selected!, targets))
  }

  // --- assistant chat ---
  type ChatMsg = { role: 'user' | 'assistant'; content: string; citations?: string[] }
  let chat = $state<ChatMsg[]>([])
  let question = $state('')
  let asking = $state(false)
  let assistantNote = $state<string | null>(null)

  async function ask(): Promise<void> {
    const q = question.trim()
    if (!q || asking) return
    chat = [...chat, { role: 'user', content: q }]
    question = ''
    asking = true
    assistantNote = null
    try {
      const history = chat
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }))
      const res: AssistantAnswer = await api.assistant(studyId, q, history.slice(0, -1))
      chat = [...chat, { role: 'assistant', content: res.answer, citations: res.citations }]
    } catch (e) {
      assistantNote = String(e).includes('503')
        ? 'The assistant needs GEMINI_API_KEY or MISTRAL_API_KEY set on the middleware. Every other view works offline.'
        : String(e)
    } finally {
      asking = false
    }
  }
</script>

<h1>Knowledge <TraceChip id="FR-DASH-8" /></h1>

{#if error}<p class="err">{error}</p>{/if}

<div class="cols">
  <section class="card" data-tour="knowledge-graph">
    <div class="head">
      <h2>Related-papers graph <TraceChip id="FR-LIT-2" /></h2>
      <span class="secondary small">{papers.length} ingested</span>
    </div>

    <div class="ingest">
      <input
        placeholder="arXiv id or DOI, e.g. 2302.06590"
        bind:value={idInput}
        onkeydown={(e) => e.key === 'Enter' && ingestById()}
      />
      <button onclick={ingestById} disabled={busy}>Add</button>
      <label class="pdf">
        PDF<input type="file" accept="application/pdf" onchange={uploadPdf} hidden />
      </label>
    </div>
    <div class="ingest">
      <input
        placeholder="Zotero collection name (Zotero app must be running)"
        bind:value={zoteroInput}
        onkeydown={(e) => e.key === 'Enter' && importZotero()}
      />
      <button onclick={importZotero} disabled={busy}>Import from Zotero</button>
      {#if zoteroNote}<span class="small muted">{zoteroNote}</span>{/if}
    </div>

    {#if graph && graph.nodes.length}
      <svg viewBox={`0 0 ${W} ${H}`} class="graph" role="img" aria-label="citation graph">
        {#each graph.edges as e (e.src + e.dst + e.kind)}
          {@const a = posByRef.get(e.src)}
          {@const b = posByRef.get(e.dst)}
          {#if a && b}
            <line
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={EDGE_COLOR[e.kind]} stroke-width="1" opacity="0.35"
            />
          {/if}
        {/each}
        {#each positioned as n (n.paperRef)}
          <g
            class="node" class:sel={n.paperRef === selected}
            transform={`translate(${n.x},${n.y})`}
            onclick={() => select(n.paperRef)}
            role="button" tabindex="0"
            onkeydown={(e) => e.key === 'Enter' && select(n.paperRef)}
          >
            <circle
              r={radius(n)}
              fill={n.ingested ? 'var(--series-1)' : 'var(--surface-1)'}
              stroke={n.ingested ? 'var(--series-1)' : 'var(--baseline)'}
              stroke-width={n.ingested ? 0 : 1.5}
            />
          </g>
        {/each}
      </svg>
      <div class="legend secondary small">
        <span><i class="dot solid"></i> ingested</span>
        <span><i class="dot hollow"></i> suggested</span>
        <span style="color:var(--series-1)">— references</span>
        <span style="color:var(--series-2)">— citations</span>
        <span style="color:var(--series-5)">— recommended</span>
      </div>
    {:else}
      <p class="secondary">
        No papers yet. Add an arXiv id / DOI / PDF above, or import a Zotero
        collection - then the neighbourhood grows from Semantic Scholar.
      </p>
    {/if}
  </section>

  <section class="card assistant" data-tour="knowledge-assistant">
    <div class="head">
      <h2>Assistant <TraceChip id="FR-LIT-4" /></h2>
      <span class="secondary small">aggregates only</span>
    </div>
    <div class="chat">
      {#each chat as m}
        <div class="msg {m.role}">
          <div class="body">{m.content}</div>
          {#if m.citations?.length}
            <div class="chips">
              {#each m.citations as c}<span class="chip">{c}</span>{/each}
            </div>
          {/if}
        </div>
      {/each}
      {#if asking}<div class="msg assistant"><div class="body secondary">thinking…</div></div>{/if}
      {#if assistantNote}<p class="note secondary small">{assistantNote}</p>{/if}
    </div>
    <div class="ask">
      <input
        placeholder="Ask about the papers, protocol, or aggregate data…"
        bind:value={question}
        onkeydown={(e) => e.key === 'Enter' && ask()}
      />
      <button onclick={ask} disabled={asking}>Ask</button>
    </div>
  </section>
</div>

{#if selectedNode}
  <aside class="drawer card">
    <button class="x" onclick={() => (selected = null)} aria-label="close">×</button>
    <h3>{selectedNode.title || selected}</h3>
    <p class="secondary small">
      {selected}{selectedNode.year ? ` · ${selectedNode.year}` : ''}
      {selectedNode.citationCount != null ? ` · ${selectedNode.citationCount} citations` : ''}
    </p>
    {#if selectedPaper}
      {#if selectedPaper.abstract}
        <p class="abstract secondary">{selectedPaper.abstract}</p>
      {/if}
      <label class="field">
        Protocol links <TraceChip id="FR-LIT-3" />
        <input
          bind:value={linkDraft}
          placeholder="RQ-P4, metric:parameter_count, recipe:ziegler-acceptance-rate"
        />
      </label>
      <div class="row">
        <button onclick={saveLinks} disabled={busy}>Save links</button>
        {#if selectedPaper.url}<a href={selectedPaper.url} target="_blank" rel="noreferrer">open</a>{/if}
        <button class="danger" onclick={() => removePaper(selected!)} disabled={busy}>Remove</button>
      </div>
    {:else}
      <p class="secondary">Suggested paper (not yet ingested).</p>
      <button onclick={() => addSuggestion(selected!)} disabled={busy}>Add to study</button>
    {/if}
  </aside>
{/if}

<style>
  .cols {
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 14px;
    align-items: start;
  }
  .card {
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 10px;
  }
  h2 {
    font-size: 15px;
    margin: 0;
  }
  .ingest {
    display: flex;
    gap: 6px;
    margin-bottom: 10px;
  }
  .ingest input {
    flex: 1;
  }
  input {
    padding: 5px 8px;
    border: 1px solid var(--border);
    border-radius: 5px;
    background: var(--page);
    color: var(--text-primary);
    font: inherit;
  }
  button {
    padding: 5px 12px;
    border: 1px solid var(--border);
    border-radius: 5px;
    background: var(--page);
    color: var(--text-primary);
    cursor: pointer;
    font: inherit;
  }
  button:hover {
    border-color: var(--series-1);
  }
  button.danger:hover {
    border-color: var(--status-critical);
    color: var(--status-critical);
  }
  .pdf {
    padding: 5px 12px;
    border: 1px dashed var(--border);
    border-radius: 5px;
    cursor: pointer;
    font-size: 13px;
  }
  .graph {
    width: 100%;
    height: auto;
    background: var(--page);
    border-radius: 6px;
  }
  .node {
    cursor: pointer;
  }
  .node:hover circle,
  .node.sel circle {
    stroke: var(--series-3);
    stroke-width: 2.5;
  }
  .legend {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-top: 8px;
  }
  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .dot.solid {
    background: var(--series-1);
  }
  .dot.hollow {
    border: 1.5px solid var(--baseline);
  }
  .assistant .chat {
    min-height: 220px;
    max-height: 360px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 10px;
  }
  .msg .body {
    padding: 7px 10px;
    border-radius: 8px;
    white-space: pre-wrap;
    font-size: 13px;
  }
  .msg.user {
    align-self: flex-end;
    max-width: 85%;
  }
  .msg.user .body {
    background: var(--series-1);
    color: #fff;
  }
  .msg.assistant .body {
    background: var(--page);
    border: 1px solid var(--border);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
  }
  .chip {
    font: 11px var(--mono);
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--grid);
    color: var(--text-secondary);
  }
  .ask {
    display: flex;
    gap: 6px;
  }
  .ask input {
    flex: 1;
  }
  .drawer {
    margin-top: 14px;
    position: relative;
  }
  .drawer .x {
    position: absolute;
    top: 8px;
    right: 8px;
    border: none;
    font-size: 18px;
    line-height: 1;
    padding: 2px 8px;
  }
  .abstract {
    font-size: 13px;
    line-height: 1.5;
  }
  .field {
    display: block;
    font-size: 13px;
    margin: 10px 0;
  }
  .field input {
    width: 100%;
    margin-top: 4px;
  }
  .row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .row a {
    color: var(--series-1);
    font-size: 13px;
  }
  .err {
    color: var(--status-critical);
  }
  .note {
    font-style: italic;
  }
  .secondary {
    color: var(--text-secondary);
  }
  .small {
    font-size: 12px;
  }
</style>
