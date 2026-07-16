<script lang="ts">
  import { lexicon } from '../lexicon.svelte'
  import { trace } from '../trace.svelte'
  import Tip from './Tip.svelte'

  let { id }: { id: string } = $props()

  // Plain-language hover text (FR-DASH-9): RQ text from the protocol,
  // requirement text from the live SRS, gates explained generically. The
  // requirement/RQ id itself stays out of the surface UI (it lives in the
  // trace panel the click opens) - the toggle reads as plain info.
  const tip = $derived.by(() => {
    if (id.startsWith('RQ-')) {
      const rq = trace.protocol?.researchQuestions.find((r) => r.id === id)
      if (rq?.text) return rq.text
    }
    if (id.startsWith('gate:')) {
      return `The "${id.slice(5)}" phase advances only when its gate artifacts are uploaded - click for the chain.`
    }
    const desc = lexicon.describe(id)
    return desc || 'Click for what this answers and where it comes from.'
  })
</script>

<Tip text={tip}>
  <button
    class="trace-chip"
    type="button"
    aria-label="What this answers"
    onclick={() => trace.open(id)}
  >
    i
  </button>
</Tip>
