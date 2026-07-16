<script lang="ts">
  import { lexicon } from '../lexicon.svelte'
  import { trace } from '../trace.svelte'
  import Tip from './Tip.svelte'

  let { id, label }: { id: string; label?: string } = $props()

  const text = $derived(label ?? id)

  // Plain-language hover text (FR-DASH-9): RQ text from the protocol,
  // requirement text from the live SRS, gates explained generically.
  const tip = $derived.by(() => {
    if (id.startsWith('RQ-')) {
      const rq = trace.protocol?.researchQuestions.find((r) => r.id === id)
      if (rq?.text) return `${id}: ${rq.text}`
    }
    if (id.startsWith('gate:')) {
      return `The "${id.slice(5)}" phase advances only when its gate artifacts are uploaded - click for the chain.`
    }
    const desc = lexicon.describe(id)
    return desc ? `${id}: ${desc}` : `Open the trace chain for ${id}.`
  })
</script>

<Tip text={tip}>
  <button class="trace-chip" type="button" onclick={() => trace.open(id)}>
    {text}
  </button>
</Tip>
