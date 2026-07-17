/**
 * Traceability chips (FR-DASH-6): every chart/card names the RQ or
 * requirement it answers; clicking a chip opens the full trace chain.
 * Chains are sourced from the protocol's analysis plan and gate
 * definitions plus a registry of the SRS requirements this UI cites.
 */

import type { ProtocolSummary } from './api'
import { lexicon } from './lexicon.svelte'

export interface TraceStep {
  label: string
  detail: string
}

class TraceState {
  /** Chip id currently open in the side panel, or null. */
  openId = $state<string | null>(null)
  protocol = $state<ProtocolSummary | null>(null)

  open(id: string): void {
    this.openId = id
  }

  close(): void {
    this.openId = null
  }

  chain(id: string): TraceStep[] {
    const p = this.protocol
    if (id.startsWith('RQ-')) {
      const rq = p?.researchQuestions.find((r) => r.id === id)
      return [
        {
          label: 'Research question',
          detail: rq?.text ?? 'Research question (protocol not loaded).',
        },
        {
          label: 'Planned recipes',
          detail: rq?.recipes.length
            ? rq.recipes.join(', ')
            : 'None - this RQ is uncovered.',
        },
        {
          label: 'Runs',
          detail:
            'Recorded when `analysis run` executes this study\'s plan - the task board clears the recipe card automatically.',
        },
        {
          label: 'Paper section',
          detail:
            'The generated paper draft (`analysis paper`) inserts this question\'s results, tables, and figures into its Results section.',
        },
      ]
    }
    if (id.startsWith('gate:')) {
      const phase = id.slice(5)
      const gates = p?.phases.find((ph) => ph.name === phase)?.gates ?? []
      return [
        { label: `Phase: ${phase}`, detail: `Declared in the protocol's phases list.` },
        {
          label: 'Gate artifacts',
          detail: gates.length ? gates.join(', ') : 'No gates declared.',
        },
        { label: 'Why phases lock', detail: lexicon.describe('FR-PROT-3') },
        {
          label: 'How it clears',
          detail: 'Upload a file with the exact artifact name; the lifecycle engine recomputes the phase.',
        },
      ]
    }
    const desc = lexicon.describe(id)
    if (desc) {
      return [
        { label: 'In plain terms', detail: desc },
        {
          label: 'Where this is recorded',
          detail:
            `This panel exists to satisfy requirement ${id}, kept in the ` +
            `project's requirements document; its build-and-proof history ` +
            `lives in the traceability matrix.`,
        },
      ]
    }
    return [{ label: 'No description registered', detail: id }]
  }
}

export const trace = new TraceState()
