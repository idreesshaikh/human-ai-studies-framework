<script lang="ts">
  import { scaleUtc } from 'd3-scale'
  import type { Lane, LaneItem } from '../lanes'
  import { timeDomain } from '../lanes'

  let { lanes, selectedSeqs = [], ghostTime = null, onselect, onhover }: { lanes: Lane[]; selectedSeqs?: number[]; ghostTime?: number | null; onselect?: (item: LaneItem) => void; onhover?: (time: number | null) => void } = $props()
  const LANE_H = 44
  const M = { left: 128, right: 16, top: 20, bottom: 34 }
  const ROW_H = 34
  let containerW = $state(900)
  let showTable = $state(false)
  let zoom = $state<[number, number] | null>(null)
  let brush = $state<{ x0: number; x1: number } | null>(null)
  let cursor = $state<{ x: number; time: number } | null>(null)
  let activeTime = $state<number | null>(null)
  let tooltip = $state<{ x: number; y: number; item: LaneItem } | null>(null)
  let scrollTop = $state(0)
  const plotW = $derived(Math.max(containerW - M.left - M.right, 100))
  const plotH = $derived(lanes.length * LANE_H)
  const height = $derived(plotH + M.top + M.bottom)
  const domain = $derived(zoom ?? timeDomain(lanes))
  const x = $derived(scaleUtc().domain(domain.map((value) => new Date(value))).range([0, plotW]))
  const allItems = $derived(lanes.flatMap((lane) => lane.items.map((item) => ({ lane: lane.label, ...item }))).sort((a, b) => a.t0 - b.t0))
  const startRow = $derived(Math.max(0, Math.floor(scrollTop / ROW_H) - 5))
  const visibleRows = $derived(allItems.slice(startRow, startRow + 24))
  const color = (key: string) => `var(--${key})`
  const fmt = (time: number) => new Date(time).toISOString().slice(11, 19) + 'Z'
  const px = (event: PointerEvent | MouseEvent, svg: SVGSVGElement) => event.clientX - svg.getBoundingClientRect().left - M.left
  const inPlot = (item: LaneItem) => Math.max(x(new Date(item.t0)), x(new Date(item.t1 ?? item.t0))) >= 0 && Math.min(x(new Date(item.t0)), x(new Date(item.t1 ?? item.t0))) <= plotW
  const selected = (item: LaneItem) => item.seqs.some((seq) => selectedSeqs.includes(seq))
  const sameInstant = (item: LaneItem) => activeTime !== null && Math.abs(item.t0 - activeTime) < 250
  function span(item: LaneItem): { x: number; width: number } { const a = x(new Date(item.t0)); const b = x(new Date(item.t1 ?? item.t0)); return { x: Math.max(Math.min(a, b), 0), width: Math.max(Math.min(Math.max(a, b), plotW) - Math.max(Math.min(a, b), 0), 3) } }
  function brushStart(event: PointerEvent): void { const svg = (event.currentTarget as SVGRectElement).ownerSVGElement!; const value = px(event, svg); brush = { x0: value, x1: value }; (event.currentTarget as Element).setPointerCapture(event.pointerId) }
  function move(event: PointerEvent): void { const svg = (event.currentTarget as SVGRectElement).ownerSVGElement!; const value = Math.max(0, Math.min(plotW, px(event, svg))); if (brush) brush = { ...brush, x1: value }; cursor = { x: value, time: x.invert(value).getTime() } }
  function brushEnd(): void { if (brush && Math.abs(brush.x1 - brush.x0) > 6) { const [a, b] = [Math.min(brush.x0, brush.x1), Math.max(brush.x0, brush.x1)]; zoom = [x.invert(a).getTime(), x.invert(b).getTime()] } brush = null }
  function hover(event: PointerEvent, item: LaneItem): void { tooltip = { x: event.clientX + 12, y: event.clientY + 12, item }; activeTime = item.t0; onhover?.(item.t0) }
  function leaveMark(): void { tooltip = null; activeTime = null; onhover?.(null) }
</script>

<div class="wrap" bind:clientWidth={containerW}>
  <div class="toolbar"><div><strong>Shared session clock</strong><span>Drag to zoom · double-click to reset</span></div><div class="legend"><span><i class="self"></i>self-report</span><span><i class="edit"></i>editing</span><span><i class="ai"></i>AI</span><span><i class="metric"></i>metrics</span><span><i class="agent"></i>agent</span></div><button aria-pressed={showTable} onclick={() => (showTable = !showTable)}>{showTable ? 'Timeline' : 'Audit table'}</button></div>
  {#if !showTable}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <svg width={containerW} {height} role="img" aria-label="Multi-instrument session timeline" ondblclick={() => (zoom = null)}>
      <g transform={`translate(${M.left},${M.top})`}>
        {#each lanes as lane, index (lane.key)}<g transform={`translate(0,${index * LANE_H})`}><rect width={plotW} height={LANE_H} fill={index % 2 ? 'color-mix(in srgb, var(--grid) 20%, transparent)' : 'transparent'} /><line y1={LANE_H} y2={LANE_H} x2={plotW} stroke="var(--grid)"/><text x="-10" y={LANE_H/2} dy=".35em" text-anchor="end" class="lane-label">{lane.label}</text></g>{/each}
        <g transform={`translate(0,${plotH})`}><line x2={plotW} stroke="var(--baseline)"/>{#each x.ticks(Math.max(2,Math.floor(plotW/140))) as tick (tick.getTime())}<g transform={`translate(${x(tick)},0)`}><line y2="5" stroke="var(--baseline)"/><text y="19" text-anchor="middle" class="tick">{fmt(tick.getTime())}</text></g>{/each}</g>
        <rect width={plotW} height={plotH} fill="transparent" class="capture" onpointerdown={brushStart} onpointermove={move} onpointerup={brushEnd} onpointerleave={() => (cursor = null)} />
        <clipPath id="timeline-clip"><rect width={plotW} height={plotH}/></clipPath><g clip-path="url(#timeline-clip)">
          {#each lanes as lane, index (lane.key)}{@const cy=index*LANE_H+LANE_H/2}{#each lane.items.filter(inPlot) as item (item.seqs.join('-')+item.type)}{@const box=span(item)}{@const hot=sameInstant(item)}
            <!-- svelte-ignore a11y_no_static_element_interactions, a11y_click_events_have_key_events -->
            {#if item.kind === 'span' || item.kind === 'band'}<rect class:hot x={box.x} y={item.kind==='band'?index*LANE_H+4:cy-5} width={box.width} height={item.kind==='band'?LANE_H-8:10} rx="4" fill={color(item.colorKey)} opacity={item.kind==='band'?.16:.85} stroke={selected(item)?'var(--text-primary)':'transparent'} stroke-width="2" onpointermove={(event)=>hover(event,item)} onpointerleave={leaveMark} onclick={()=>onselect?.(item)}/>{:else}<g class:hot onpointermove={(event)=>hover(event,item)} onpointerleave={leaveMark} onclick={()=>onselect?.(item)}><circle cx={x(new Date(item.t0))} cy={cy} r="12" fill="transparent"/><circle cx={x(new Date(item.t0))} cy={cy} r={selected(item)?6:4.5} fill={color(item.colorKey)} stroke={selected(item)?'var(--text-primary)':'var(--surface-1)'} stroke-width="2"/></g>{/if}
          {/each}{/each}
        </g>
        {#if cursor}<g class="cursor" transform={`translate(${cursor.x},0)`}><line y2={plotH}/><text y="-6" text-anchor="middle">{fmt(cursor.time)}</text></g>{/if}
        {#if ghostTime !== null && x(new Date(ghostTime)) >= 0 && x(new Date(ghostTime)) <= plotW}<line class="ghost" x1={x(new Date(ghostTime))} x2={x(new Date(ghostTime))} y2={plotH}/>{/if}
        {#if brush}<rect x={Math.min(brush.x0,brush.x1)} width={Math.abs(brush.x1-brush.x0)} height={plotH} fill="color-mix(in srgb,var(--series-1) 12%,transparent)" pointer-events="none"/>{/if}
      </g>
    </svg>
  {:else}
    <div class="virtual" onscroll={(event)=>(scrollTop=(event.currentTarget as HTMLDivElement).scrollTop)}><div style:height={`${allItems.length*ROW_H}px`}><table class="data audit" style:transform={`translateY(${startRow*ROW_H}px)`}><thead><tr><th>Time</th><th>Lane</th><th>Seq</th><th>Event</th><th>Detail</th></tr></thead><tbody>{#each visibleRows as item (item.lane+item.seqs.join('-')+item.type)}<tr><td class="mono">{fmt(item.t0)}</td><td>{item.lane}</td><td class="mono">{item.seqs.join(', ')}</td><td class="mono">{item.type}</td><td>{item.label}</td></tr>{/each}</tbody></table></div></div>
  {/if}
</div>
{#if tooltip}<div class="tooltip" style:left={`${tooltip.x}px`} style:top={`${tooltip.y}px`}><strong>{tooltip.item.label}</strong><p class="mono">{fmt(tooltip.item.t0)} · seq {tooltip.item.seqs.join(', ')}</p>{#each Object.entries(tooltip.item.payload).slice(0,5) as [key,value] (key)}<div><span>{key}</span><code>{JSON.stringify(value)}</code></div>{/each}</div>{/if}

<style>
  .wrap{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;overflow:hidden}.toolbar{display:flex;align-items:center;gap:14px;padding:10px 12px;border-bottom:1px solid var(--grid);font-size:12px}.toolbar>div:first-child{display:flex;flex-direction:column}.toolbar>div:first-child span{color:var(--text-muted)}.legend{display:flex;align-items:center;gap:10px;margin-left:auto;color:var(--text-secondary);font-size:11px}.legend span{display:flex;align-items:center;gap:4px}.legend i{width:8px;height:8px;border-radius:50%;background:var(--series-1)}.legend .edit{background:var(--series-2)}.legend .ai{background:var(--series-3)}.legend .metric{background:var(--series-5)}.legend .agent{background:var(--series-8)}svg{display:block}.lane-label{fill:var(--text-secondary);font-size:12px}.tick{fill:var(--text-muted);font:11px monospace}.capture{cursor:crosshair}.hot{filter:brightness(1.25);transform:scale(1.18);transform-box:fill-box;transform-origin:center;transition:transform 120ms,filter 120ms}.cursor line{stroke:var(--text-secondary);stroke-width:1;pointer-events:none}.cursor text{fill:var(--text-secondary);font:10px monospace}.ghost{stroke:var(--series-8);stroke-width:1;stroke-dasharray:3 3;opacity:.55}.tooltip{position:fixed;z-index:50;max-width:320px;padding:10px;background:var(--surface-1);border:1px solid var(--border);border-radius:8px;box-shadow:0 8px 24px color-mix(in srgb,var(--text-primary) 15%,transparent);pointer-events:none;font-size:11px}.tooltip p{margin:3px 0;color:var(--text-muted)}.tooltip div{display:flex;justify-content:space-between;gap:10px}.tooltip span{color:var(--text-muted)}.virtual{height:420px;overflow:auto;position:relative}.audit{position:absolute;width:100%;font-variant-numeric:tabular-nums}.audit tr{height:34px}@media(max-width:850px){.toolbar{align-items:flex-start;flex-wrap:wrap}.legend{order:3;width:100%;margin-left:0;overflow:auto}svg{min-width:620px}.wrap{overflow-x:auto}}@media(prefers-reduced-motion:reduce){.hot{transition:none}}
</style>
