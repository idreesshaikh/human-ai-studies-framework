<script lang="ts">
  import { api, type Gate, type LifecycleDoc } from '../api'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()

  let doc = $state<LifecycleDoc | null>(null)
  let error = $state<string | null>(null)
  /** The missing gate whose "what would satisfy this" panel is open. */
  let selected = $state<{ phase: string; gate: Gate } | null>(null)
  let uploading = $state(false)
  let uploadNote = $state<string | null>(null)

  async function load(): Promise<void> {
    try {
      doc = await api.lifecycle(studyId)
      error = null
    } catch (e) {
      error = String(e)
    }
  }
  $effect(() => {
    load()
    const timer = setInterval(load, 5_000)
    return () => clearInterval(timer)
  })

  async function upload(files: FileList | null): Promise<void> {
    if (!files?.length || !selected) return
    const file = files[0]
    uploading = true
    uploadNote = null
    try {
      await api.uploadFile(file)
      if (file.name !== selected.gate.artifact) {
        uploadNote =
          `Stored as "${file.name}" - the gate needs the exact name ` +
          `"${selected.gate.artifact}", so it stays unsatisfied.`
      } else {
        uploadNote = `"${file.name}" uploaded - gate satisfied.`
        selected = null
      }
      await load()
    } catch (e) {
      uploadNote = `Upload failed: ${e}`
    } finally {
      uploading = false
    }
  }
</script>

<h1>Lifecycle board <TraceChip id="FR-DASH-2" /></h1>
<p class="secondary small">
  The current phase is <strong>computed</strong> by the lifecycle engine from
  uploaded gate artifacts - nothing here is hand-set (FR-PROT-3).
</p>

{#if error}
  <div class="card"><p class="secondary">Failed to load: {error}</p></div>
{:else if doc}
  <div class="board" data-tour="lifecycle-board">
    {#each doc.phases as phase (phase.name)}
      <div class="column {phase.status}">
        <header>
          <span class="name">{phase.name}</span>
          {#if phase.status === 'current'}
            <span class="badge good">● current</span>
          {:else if phase.status === 'complete'}
            <span class="badge">✓ done</span>
          {/if}
        </header>
        {#if phase.gates.length === 0}
          <p class="small muted">No gate artifacts.</p>
        {/if}
        {#each phase.gates as gate (gate.artifact)}
          {#if gate.satisfied}
            <div class="chip satisfied" title={`Uploaded ${gate.satisfiedBy?.uploadedAt}`}>
              <span class="badge good">✓</span>
              <span class="mono small">{gate.artifact}</span>
            </div>
          {:else}
            <button
              class="chip missing"
              onclick={() => {
                selected = { phase: phase.name, gate }
                uploadNote = null
              }}
            >
              <span class="badge serious">!</span>
              <span class="mono small">{gate.artifact}</span>
            </button>
          {/if}
        {/each}
        <footer>
          <TraceChip id={`gate:${phase.name}`} label={`gate: ${phase.name}`} />
        </footer>
      </div>
    {/each}
  </div>
{:else}
  <p class="muted">Loading…</p>
{/if}

{#if selected}
  <aside class="satisfy card" aria-label="How to satisfy this gate">
    <header>
      <h3>Missing: <code>{selected.gate.artifact}</code></h3>
      <button onclick={() => (selected = null)} aria-label="Close">x</button>
    </header>
    <p class="secondary">
      The <strong>{selected.phase}</strong> phase gates on this artifact. The
      lifecycle advances automatically once a file named exactly
      <code>{selected.gate.artifact}</code> is uploaded to the middleware
      artifact store (<code>POST /ingest/files</code>).
    </p>
    <label class="upload">
      <input
        type="file"
        disabled={uploading}
        onchange={(e) => upload(e.currentTarget.files)}
      />
    </label>
    {#if uploadNote}
      <p class="small secondary">{uploadNote}</p>
    {/if}
  </aside>
{/if}

<style>
  .board {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 10px;
    align-items: start;
  }
  .column {
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 120px;
  }
  .column.current {
    border-color: var(--series-1);
    box-shadow: 0 0 0 1px var(--series-1);
  }
  .column.upcoming {
    opacity: 0.75;
  }
  .column header {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: 4px;
  }
  .name {
    font-weight: 600;
    text-transform: capitalize;
  }
  .chip {
    display: flex;
    align-items: center;
    gap: 6px;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 5px 8px;
    background: transparent;
    text-align: left;
    width: 100%;
  }
  .chip.missing {
    cursor: pointer;
    border-style: dashed;
    border-color: var(--status-serious);
  }
  .chip.missing:hover {
    background: color-mix(in srgb, var(--status-serious) 8%, transparent);
  }
  footer {
    margin-top: auto;
    padding-top: 6px;
  }
  .satisfy {
    position: fixed;
    right: 16px;
    bottom: 16px;
    width: 360px;
    z-index: 30;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  }
  .satisfy header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
</style>
