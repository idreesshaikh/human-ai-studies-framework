<script lang="ts">
  /**
   * Metrics compare (FR-DASH-5): per-metric distribution split by condition.
   * Small-n honest (NFR-8): every point is drawn (deterministic jitter),
   * per-cell n is always visible, quartile boxes only appear when n >= 5,
   * and the table view carries exact summaries.
   */
  import { scaleLinear } from 'd3-scale'
  import { api, type DatasetRow } from '../api'
  import { trace } from '../trace.svelte'
  import TraceChip from '../components/TraceChip.svelte'

  let { studyId }: { studyId: string } = $props()

  // Plain-language definitions mirror the cognitive-load-9 set the paper
  // generator cites (analysis/src/analysis/paper.py METRIC_SETS).
  const METRICS: {
    key: string
    label: string
    level: 'function' | 'file'
    definition: string
  }[] = [
    { key: 'nesting_penalty', label: 'Nesting penalty', level: 'function',
      definition: 'How deeply code is nested inside ifs and loops - deeper nesting is harder to hold in your head.' },
    { key: 'cognitive_complexity', label: 'Cognitive complexity', level: 'function',
      definition: 'SonarSource\'s score for how hard a function is to follow (branches, jumps, nesting).' },
    { key: 'parameter_count', label: 'Parameter count', level: 'function',
      definition: 'Arguments per function, against the ~7-item working-memory bound.' },
    { key: 'halstead_effort', label: 'Halstead effort', level: 'function',
      definition: 'A classic estimate of mental effort from how many distinct operators and operands the code uses.' },
    { key: 'mean_scope_distance', label: 'Mean scope distance', level: 'function',
      definition: 'How far (in lines) a variable\'s definition sits from where it is used - far-away definitions strain memory.' },
    { key: 'avg_identifier_length', label: 'Avg identifier length', level: 'function',
      definition: 'Average name length - single letters and huge names both hurt readability.' },
    { key: 'indentation_variance', label: 'Indentation variance', level: 'file',
      definition: 'How irregular the file\'s indentation depth is - a shape proxy for structural complexity.' },
    { key: 'mean_line_width', label: 'Mean line width', level: 'file',
      definition: 'Average source-line length - long lines force horizontal reading.' },
    { key: 'comment_ratio', label: 'Comment ratio', level: 'file',
      definition: 'Comment lines relative to code lines.' },
  ]

  let rows = $state<DatasetRow[]>([])
  let error = $state<string | null>(null)
  let metricKey = $state('nesting_penalty')
  let showTable = $state(false)
  let containerW = $state(900)
  let tooltip = $state<{ x: number; y: number; text: string } | null>(null)

  async function load(): Promise<void> {
    try {
      rows = (await api.dataset(studyId)).rows.filter((r) => r.source === 'metrics')
      error = null
    } catch (e) {
      error = String(e)
    }
  }
  $effect(() => {
    load()
  })

  const metric = $derived(METRICS.find((m) => m.key === metricKey) ?? METRICS[0])

  /** Fixed condition order from the protocol - color follows the entity. */
  const conditions = $derived(
    trace.protocol?.conditions ??
      [...new Set(rows.map((r) => r.condition))].sort(),
  )

  interface Point {
    value: number
    condition: string
    detail: string
  }
  const points = $derived(
    rows.flatMap((r): Point[] => {
      const v = r.payload[metric.key]
      if (typeof v !== 'number' || !Number.isFinite(v)) return []
      const fn = typeof r.payload.function === 'string' ? r.payload.function : null
      const file = typeof r.payload.file === 'string' ? r.payload.file : '?'
      return [
        {
          value: v,
          condition: r.condition,
          detail: `${file}${fn ? ` · ${fn}()` : ''} · ${r.participantId}`,
        },
      ]
    }),
  )

  function summary(values: number[]): { n: number; min: number; q1: number; median: number; q3: number; max: number } | null {
    if (values.length === 0) return null
    const v = [...values].sort((a, b) => a - b)
    const q = (p: number) => {
      const idx = (v.length - 1) * p
      const lo = Math.floor(idx)
      return v[lo] + (v[Math.min(lo + 1, v.length - 1)] - v[lo]) * (idx - lo)
    }
    return { n: v.length, min: v[0], q1: q(0.25), median: q(0.5), q3: q(0.75), max: v[v.length - 1] }
  }

  const byCondition = $derived(
    conditions.map((c, i) => {
      const values = points.filter((p) => p.condition === c)
      return {
        condition: c,
        slot: (i % 8) + 1,
        points: values,
        stats: summary(values.map((p) => p.value)),
      }
    }),
  )

  // ---- geometry ----
  const M = { left: 64, right: 16, top: 12, bottom: 44 }
  const H = 300
  const plotW = $derived(Math.max(containerW - M.left - M.right, 100))
  const plotH = H - M.top - M.bottom
  const y = $derived.by(() => {
    const vals = points.map((p) => p.value)
    const max = vals.length ? Math.max(...vals) : 1
    const min = Math.min(0, ...(vals.length ? vals : [0]))
    return scaleLinear().domain([min, max]).nice().range([plotH, 0])
  })
  const bandW = $derived(plotW / Math.max(conditions.length, 1))

  /** Deterministic jitter - stable across renders, no Math.random. */
  const jitter = (i: number): number => {
    const f = Math.sin((i + 1) * 12.9898) * 43758.5453
    return (f - Math.floor(f) - 0.5) * 0.55
  }
</script>

<h1>
  Metrics compare
  <TraceChip id="FR-DASH-5" />
  <TraceChip id="RQ-P2" />
  <TraceChip id="NFR-8" />
</h1>

<div class="controls">
  <label>
    Metric
    <select bind:value={metricKey}>
      {#each METRICS as m (m.key)}
        <option value={m.key}>{m.label} ({m.level}-level)</option>
      {/each}
    </select>
  </label>
  <button onclick={() => (showTable = !showTable)}>
    {showTable ? 'Chart view' : 'Table view'}
  </button>
</div>
<p class="small muted">{metric.definition}</p>

{#if error}
  <div class="card"><p class="secondary">Failed to load: {error}</p></div>
{:else if points.length === 0}
  <div class="card">
    <p class="secondary">No metric rows carry <code>{metric.key}</code> yet.</p>
    <p class="small muted">
      Metric rows appear after the metrics tool analyzes a session's code
      (<code>uv run python metrics/src/main.py … --format jsonl</code>, or
      the seeded demo data) - see RUNBOOK.md §3.4.
    </p>
  </div>
{:else if showTable}
  <div class="card">
    <table class="data">
      <thead>
        <tr><th>Condition</th><th>n</th><th>min</th><th>q1</th><th>median</th><th>q3</th><th>max</th></tr>
      </thead>
      <tbody>
        {#each byCondition as c (c.condition)}
          {#if c.stats}
            <tr>
              <td>{c.condition}</td>
              <td>{c.stats.n}</td>
              <td>{c.stats.min.toFixed(2)}</td>
              <td>{c.stats.q1.toFixed(2)}</td>
              <td>{c.stats.median.toFixed(2)}</td>
              <td>{c.stats.q3.toFixed(2)}</td>
              <td>{c.stats.max.toFixed(2)}</td>
            </tr>
          {:else}
            <tr><td>{c.condition}</td><td>0</td><td colspan="5" class="muted">no data</td></tr>
          {/if}
        {/each}
      </tbody>
    </table>
  </div>
{:else}
  <div class="card chart" data-tour="metrics-chart" bind:clientWidth={containerW}>
    <svg width={containerW} height={H} role="img"
      aria-label={`${metric.label} by condition, every point drawn`}>
      <g transform={`translate(${M.left},${M.top})`}>
        <!-- y grid + ticks -->
        {#each y.ticks(5) as tick (tick)}
          <g transform={`translate(0,${y(tick)})`}>
            <line x1="0" x2={plotW} stroke="var(--grid)" stroke-width="1" />
            <text x="-8" dy="0.35em" text-anchor="end" class="ticklabel num">{tick}</text>
          </g>
        {/each}
        <line x1="0" y1={plotH} x2={plotW} y2={plotH} stroke="var(--baseline)" />

        {#each byCondition as c, ci (c.condition)}
          {@const cx = ci * bandW + bandW / 2}
          <!-- quartile box only when n >= 5 (small-n honesty) -->
          {#if c.stats && c.stats.n >= 5}
            <rect
              x={cx - bandW * 0.18}
              y={y(c.stats.q3)}
              width={bandW * 0.36}
              height={Math.max(y(c.stats.q1) - y(c.stats.q3), 1)}
              fill={`var(--series-${c.slot})`}
              opacity="0.12"
              rx="3"
            />
          {/if}
          {#if c.stats}
            <line
              x1={cx - bandW * 0.22}
              x2={cx + bandW * 0.22}
              y1={y(c.stats.median)}
              y2={y(c.stats.median)}
              stroke={`var(--series-${c.slot})`}
              stroke-width="2"
            />
          {/if}
          {#each c.points as p, pi (pi)}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <!-- hover enhances; exact values live in the table view -->
            <circle
              cx={cx + jitter(pi) * bandW * 0.5}
              cy={y(p.value)}
              r="4.5"
              fill={`var(--series-${c.slot})`}
              stroke="var(--surface-1)"
              stroke-width="2"
              onpointermove={(e) => (tooltip = {
                x: e.clientX + 12,
                y: e.clientY + 12,
                text: `${p.value} - ${p.detail}`,
              })}
              onpointerleave={() => (tooltip = null)}
            />
          {/each}
          <text x={cx} y={plotH + 18} text-anchor="middle" class="condlabel">
            {c.condition}
          </text>
          <text x={cx} y={plotH + 34} text-anchor="middle" class="ticklabel num">
            n = {c.stats?.n ?? 0}
          </text>
        {/each}
      </g>
    </svg>
    <p class="small muted">
      {metric.label} ({metric.level}-level) · every observation plotted ·
      median line{points.length >= 5 ? ' + interquartile box' : ''} · exact
      values in the table view.
    </p>
  </div>
{/if}

{#if tooltip}
  <div class="tooltip" style:left={`${tooltip.x}px`} style:top={`${tooltip.y}px`}>
    {tooltip.text}
  </div>
{/if}

<style>
  .controls {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 12px;
  }
  .controls label {
    display: flex;
    gap: 8px;
    align-items: center;
    color: var(--text-secondary);
  }
  .chart {
    overflow: hidden;
  }
  .ticklabel {
    fill: var(--text-muted);
    font-size: 11px;
  }
  .condlabel {
    fill: var(--text-secondary);
    font-size: 12px;
    font-weight: 600;
  }
  .tooltip {
    position: fixed;
    z-index: 50;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18);
    padding: 6px 10px;
    font-size: 12px;
    pointer-events: none;
  }
</style>
