<script lang="ts">
  /**
   * Swimlane timeline (FR-DASH-4): heterogeneous events from every leg on
   * one shared time axis. Geometry comes from lanes.ts; this component only
   * draws. Brush horizontally to zoom, double-click to reset, hover any
   * mark for its payload; a table view carries every value (tooltips
   * enhance, never gate).
   */
  import { scaleUtc } from 'd3-scale'
  import type { Lane, LaneItem } from '../lanes'
  import { timeDomain } from '../lanes'

  let {
    lanes,
    selectedSeqs = [],
    onselect,
  }: {
    lanes: Lane[]
    selectedSeqs?: number[]
    onselect?: (item: LaneItem) => void
  } = $props()

  const LANE_H = 36
  const M = { left: 118, right: 14, top: 6, bottom: 30 }

  let containerW = $state(900)
  let showTable = $state(false)
  let zoom = $state<[number, number] | null>(null)
  let brush = $state<{ x0: number; x1: number } | null>(null)
  let tooltip = $state<{ x: number; y: number; item: LaneItem } | null>(null)

  const plotW = $derived(Math.max(containerW - M.left - M.right, 100))
  const plotH = $derived(lanes.length * LANE_H)
  const height = $derived(plotH + M.top + M.bottom)
  const domain = $derived(zoom ?? timeDomain(lanes))
  const x = $derived(scaleUtc().domain(domain.map((d) => new Date(d))).range([0, plotW]))

  const COLOR: Record<string, string> = {
    'series-1': 'var(--series-1)',
    'series-2': 'var(--series-2)',
    'series-3': 'var(--series-3)',
    'series-4': 'var(--series-4)',
    'series-5': 'var(--series-5)',
    'series-6': 'var(--series-6)',
    'series-8': 'var(--series-8)',
    'status-good': 'var(--status-good)',
    'status-serious': 'var(--status-serious)',
    muted: 'var(--text-muted)',
    ink: 'var(--text-secondary)',
  }
  const color = (key: string) => COLOR[key] ?? 'var(--text-muted)'

  const fmtTime = (t: number) =>
    new Date(t).toISOString().slice(11, 19) + 'Z'

  function px(e: PointerEvent | MouseEvent, svg: SVGSVGElement): number {
    return e.clientX - svg.getBoundingClientRect().left - M.left
  }

  function brushStart(e: PointerEvent): void {
    const svg = (e.currentTarget as SVGRectElement).ownerSVGElement!
    const x0 = px(e, svg)
    brush = { x0, x1: x0 }
    ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
  }
  function brushMove(e: PointerEvent): void {
    if (!brush) return
    const svg = (e.currentTarget as SVGRectElement).ownerSVGElement!
    brush = { ...brush, x1: px(e, svg) }
  }
  function brushEnd(): void {
    if (brush && Math.abs(brush.x1 - brush.x0) > 6) {
      const [a, b] = [Math.min(brush.x0, brush.x1), Math.max(brush.x0, brush.x1)]
      zoom = [x.invert(a).getTime(), x.invert(b).getTime()]
    }
    brush = null
  }

  function hover(e: PointerEvent, item: LaneItem): void {
    tooltip = { x: e.clientX + 12, y: e.clientY + 12, item }
  }

  /** Span x/width clamped to the plot, with a 3px floor so it stays visible. */
  function spanBox(item: LaneItem): { x: number; w: number } {
    const a = x(new Date(item.t0))
    const b = x(new Date(item.t1 ?? item.t0))
    const left = Math.max(Math.min(a, b), 0)
    const right = Math.min(Math.max(a, b), plotW)
    return { x: left, w: Math.max(right - left, 3) }
  }

  const inPlot = (item: LaneItem): boolean => {
    const a = x(new Date(item.t0))
    const b = x(new Date(item.t1 ?? item.t0))
    return Math.max(a, b) >= 0 && Math.min(a, b) <= plotW
  }

  const isSelected = (item: LaneItem): boolean =>
    item.seqs.some((s) => selectedSeqs.includes(s))

  const allItems = $derived(
    lanes.flatMap((l) => l.items.map((it) => ({ lane: l.label, ...it })))
      .sort((a, b) => a.t0 - b.t0),
  )
</script>

<div class="wrap" bind:clientWidth={containerW}>
  <div class="toolbar small">
    <span class="muted">
      drag across the chart to zoom · double-click to reset{zoom ? ' · zoomed' : ''}
    </span>
    <span class="legend">
      <span class="key"><i style:background="var(--series-1)"></i>human edit</span>
      <span class="key"><i style:background="var(--series-2)"></i>ai edit / accept</span>
      <span class="key"><i style:background="var(--series-3)"></i>paste</span>
      <span class="key"><i style:background="var(--series-4)"></i>undo-redo</span>
      <span class="key"><i style:background="var(--series-5)"></i>self-report</span>
      <span class="key"><i style:background="var(--series-6)"></i>stuck / loop</span>
      <span class="key"><i style:background="var(--series-8)"></i>agent</span>
      <span class="key"><i class="band"></i>paused / idle</span>
    </span>
    <button onclick={() => (showTable = !showTable)}>
      {showTable ? 'Chart view' : 'Table view'}
    </button>
  </div>

  {#if !showTable}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <svg
      width={containerW}
      {height}
      role="img"
      aria-label="Session timeline: one lane per instrument leg"
      ondblclick={() => (zoom = null)}
    >
      <g transform={`translate(${M.left},${M.top})`}>
        <!-- lane rows + labels -->
        {#each lanes as lane, i (lane.key)}
          <g transform={`translate(0,${i * LANE_H})`}>
            <line x1="0" y1={LANE_H} x2={plotW} y2={LANE_H} stroke="var(--grid)" stroke-width="1" />
            <text x={-10} y={LANE_H / 2} dy="0.35em" text-anchor="end" class="lanelabel">
              {lane.label}
            </text>
          </g>
        {/each}

        <!-- time axis -->
        <g transform={`translate(0,${plotH})`}>
          <line x1="0" y1="0" x2={plotW} y2="0" stroke="var(--baseline)" stroke-width="1" />
          {#each x.ticks(Math.max(Math.floor(plotW / 130), 2)) as tick (tick.getTime())}
            <g transform={`translate(${x(tick)},0)`}>
              <line y1="0" y2="4" stroke="var(--baseline)" stroke-width="1" />
              <text y="16" text-anchor="middle" class="ticklabel num">{fmtTime(tick.getTime())}</text>
            </g>
          {/each}
        </g>

        <!-- brush capture layer (below marks so marks keep hover) -->
        <rect
          x="0"
          y="0"
          width={plotW}
          height={plotH}
          fill="transparent"
          style="cursor: crosshair"
          onpointerdown={brushStart}
          onpointermove={brushMove}
          onpointerup={brushEnd}
        />

        <!-- items -->
        <clipPath id="plot-clip"><rect x="0" y="0" width={plotW} height={plotH} /></clipPath>
        <g clip-path="url(#plot-clip)">
          {#each lanes as lane, i (lane.key)}
            {@const cy = i * LANE_H + LANE_H / 2}
            {#each lane.items.filter(inPlot) as item (item.seqs.join('-') + item.type)}
              {@const sel = isSelected(item)}
              {#if item.kind === 'band'}
                {@const box = spanBox(item)}
                <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
                <!-- pointer interaction enhances, never gates: the table view carries every value -->
                <rect
                  x={box.x}
                  y={i * LANE_H + 2}
                  width={box.w}
                  height={LANE_H - 4}
                  fill={color(item.colorKey)}
                  opacity="0.13"
                  onpointermove={(e) => hover(e, item)}
                  onpointerleave={() => (tooltip = null)}
                  onclick={() => onselect?.(item)}
                />
              {:else if item.kind === 'span'}
                {@const box = spanBox(item)}
                <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
                <rect
                  x={box.x}
                  y={cy - 6}
                  width={box.w}
                  height="12"
                  rx="3"
                  fill={color(item.colorKey)}
                  opacity="0.85"
                  stroke={sel ? 'var(--text-primary)' : 'var(--surface-1)'}
                  stroke-width={sel ? 2 : 1}
                  onpointermove={(e) => hover(e, item)}
                  onpointerleave={() => (tooltip = null)}
                  onclick={() => onselect?.(item)}
                />
              {:else}
                {@const cx = x(new Date(item.t0))}
                {@const r = 4.5 * (item.weight ?? 1)}
                <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
                <g
                  onpointermove={(e) => hover(e, item)}
                  onpointerleave={() => (tooltip = null)}
                  onclick={() => onselect?.(item)}
                >
                  <!-- hit target bigger than the mark -->
                  <circle cx={cx} cy={cy} r="12" fill="transparent" />
                  {#if item.glyph === 'tick'}
                    <line x1={cx} y1={cy - 8} x2={cx} y2={cy + 8}
                      stroke={color(item.colorKey)} stroke-width={sel ? 3 : 1.5} />
                  {:else if item.glyph === 'ring'}
                    <circle cx={cx} cy={cy} r={r} fill="none"
                      stroke={color(item.colorKey)} stroke-width="1.5" />
                  {:else if item.glyph === 'cross'}
                    <path
                      d={`M${cx - r},${cy - r}L${cx + r},${cy + r}M${cx - r},${cy + r}L${cx + r},${cy - r}`}
                      stroke={color(item.colorKey)} stroke-width="1.5" fill="none" />
                  {:else if item.glyph === 'diamond'}
                    <path
                      d={`M${cx},${cy - r - 1}L${cx + r + 1},${cy}L${cx},${cy + r + 1}L${cx - r - 1},${cy}Z`}
                      fill={color(item.colorKey)} stroke="var(--surface-1)" stroke-width="1.5" />
                  {:else if item.glyph === 'flag'}
                    <path
                      d={`M${cx},${cy + 9}V${cy - 9}l${r * 2},4l-${r * 2},4`}
                      fill={color(item.colorKey)} stroke={color(item.colorKey)} stroke-width="1.5" />
                  {:else}
                    <circle cx={cx} cy={cy} r={sel ? r + 1.5 : r}
                      fill={color(item.colorKey)}
                      stroke={sel ? 'var(--text-primary)' : 'var(--surface-1)'} stroke-width="2" />
                  {/if}
                </g>
              {/if}
            {/each}
          {/each}
        </g>

        <!-- active brush -->
        {#if brush}
          <rect
            x={Math.min(brush.x0, brush.x1)}
            y="0"
            width={Math.abs(brush.x1 - brush.x0)}
            height={plotH}
            fill="var(--series-1)"
            opacity="0.12"
            pointer-events="none"
          />
        {/if}
      </g>
    </svg>
  {:else}
    <div class="tablewrap">
      <table class="data">
        <thead>
          <tr><th>Time</th><th>Lane</th><th>Seq</th><th>Event</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {#each allItems as item (item.lane + item.seqs.join('-') + item.type)}
            <tr>
              <td class="mono">{fmtTime(item.t0)}{item.t1 ? ` - ${fmtTime(item.t1)}` : ''}</td>
              <td>{item.lane}</td>
              <td class="mono">{item.seqs.join(', ')}</td>
              <td class="mono">{item.type}</td>
              <td>{item.label}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

{#if tooltip}
  <div class="tooltip" style:left={`${tooltip.x}px`} style:top={`${tooltip.y}px`}>
    <div class="tt-title">{tooltip.item.label}</div>
    <div class="small muted mono">
      {fmtTime(tooltip.item.t0)}{tooltip.item.t1 ? ` - ${fmtTime(tooltip.item.t1)}` : ''}
      · seq {tooltip.item.seqs.join(', ')}
    </div>
    <table>
      <tbody>
        {#each Object.entries(tooltip.item.payload) as [k, v] (k)}
          <tr><td class="muted">{k}</td><td class="num">{JSON.stringify(v)}</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .wrap {
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 8px 6px 2px;
  }
  .toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 2px 10px 6px;
  }
  .legend {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-left: auto;
  }
  .key {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--text-secondary);
  }
  .key i {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    display: inline-block;
  }
  .key i.band {
    background: color-mix(in srgb, var(--text-muted) 20%, transparent);
    border: 1px solid var(--grid);
  }
  .lanelabel {
    fill: var(--text-secondary);
    font-size: 12px;
  }
  .ticklabel {
    fill: var(--text-muted);
    font-size: 11px;
  }
  .tablewrap {
    max-height: 420px;
    overflow: auto;
    padding: 0 8px 8px;
  }
  .tooltip {
    position: fixed;
    z-index: 50;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18);
    padding: 8px 10px;
    max-width: 320px;
    pointer-events: none;
    font-size: 12px;
  }
  .tt-title {
    font-weight: 600;
  }
  .tooltip table td {
    padding: 0 8px 0 0;
    vertical-align: top;
  }
</style>
