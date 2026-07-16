<script lang="ts">
  /**
   * Event-rate sparkline (FR-DASH-3): one bar per receive bucket, single
   * hue (one series - no legend, per the dataviz skill), values reachable
   * via the title attribute and the surrounding card's numbers.
   */
  let {
    values,
    width = 160,
    height = 28,
  }: { values: number[]; width?: number; height?: number } = $props()

  const max = $derived(Math.max(...values, 1))
  const barW = $derived(width / values.length)
</script>

<svg
  {width}
  {height}
  viewBox={`0 0 ${width} ${height}`}
  role="img"
  aria-label={`Event rate, ${values.reduce((a, b) => a + b, 0)} events over ${values.length} buckets`}
>
  <line x1="0" y1={height - 0.5} x2={width} y2={height - 0.5} stroke="var(--baseline)" stroke-width="1" />
  {#each values as v, i (i)}
    {#if v > 0}
      <rect
        x={i * barW + 0.5}
        y={height - 1 - (v / max) * (height - 3)}
        width={Math.max(barW - 1, 1)}
        height={(v / max) * (height - 3)}
        rx="1"
        fill="var(--series-1)"
      >
        <title>{v} events</title>
      </rect>
    {/if}
  {/each}
</svg>
