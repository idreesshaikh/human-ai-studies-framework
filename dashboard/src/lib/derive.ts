/**
 * Task-card derivation (FR-DASH-7) - the dynamic project manager's core.
 *
 * The board is a *projection*: derived cards are computed from the
 * middleware's factual status document on every poll, so a card exists
 * exactly as long as the condition behind it holds. Nothing derived is
 * stored; only manual cards live in the middleware.
 */

import type { Finding, ManualTask, StatusDoc } from './api'

export type Column = 'blocked' | 'todo' | 'waiting' | 'done'

export type CardKind =
  | 'gate'
  | 'rq-uncovered'
  | 'recipe-unrun'
  | 'participant-data'
  | 'integrity'
  | 'finding'
  | 'manual'

/** Finding kinds the status doc already projects into cards (seq gaps and
 *  integrity flags become integrity cards) - skip them here to avoid a
 *  duplicate card for the same defect. */
const STATUS_CARDED_KINDS = new Set(['seq-gap', 'integrity-flag'])

export interface Card {
  /** Stable identity: the condition it projects, so re-derivation is a no-op. */
  id: string
  kind: CardKind
  column: Column
  title: string
  /** What is outstanding. */
  what: string
  /** Why it exists - the requirement / protocol clause it traces to. */
  why: string
  /** How to clear it. */
  how: string
  /** Traceability chip target (FR-DASH-6). */
  trace: string
  /** Manual cards only: the middleware task id. */
  manualId?: number
}

const PHASE_ORDER = [
  'design',
  'ethics',
  'pilot',
  'recruitment',
  'data-collection',
  'analysis',
  'write-up',
]

/** Participant ids follow the pilot convention P1..P<planned> (P01 == P1). */
function participantNumber(id: string): number | null {
  const m = id.match(/^P(\d+)$/)
  return m ? parseInt(m[1], 10) : null
}

function participantLabel(n: number): string {
  return `P${String(n).padStart(2, '0')}`
}

export function deriveCards(
  status: StatusDoc,
  manual: ManualTask[],
  findings: Finding[] = [],
): Card[] {
  const cards: Card[] = []
  const currentIndex = PHASE_ORDER.indexOf(status.lifecycle.currentPhase)

  // 1. One card per unsatisfied gate artifact (FR-DASH-2 made actionable).
  //    Gates of the current phase are workable now; gates of later phases
  //    are blocked behind it.
  for (const phase of status.lifecycle.phases) {
    for (const gate of phase.gates) {
      if (gate.satisfied) continue
      const blocked = PHASE_ORDER.indexOf(phase.name) > currentIndex
      cards.push({
        id: `gate:${phase.name}/${gate.artifact}`,
        kind: 'gate',
        column: blocked ? 'blocked' : 'todo',
        title: `Gate artifact missing: ${gate.artifact}`,
        what: `The ${phase.name} phase requires ${gate.artifact}.`,
        why:
          `Protocol phase "${phase.name}" declares this gate; the lifecycle ` +
          `cannot advance past ${phase.name} without it (FR-PROT-3).`,
        how: `Upload a file named "${gate.artifact}" on the lifecycle board.`,
        trace: `gate:${phase.name}`,
      })
    }
  }

  // 2. One card per RQ with no planned recipe: the protocol declares a
  //    question nothing will answer.
  for (const rq of status.researchQuestions) {
    if (rq.recipes.length === 0) {
      cards.push({
        id: `rq:${rq.id}`,
        kind: 'rq-uncovered',
        column: 'todo',
        title: `${rq.id} has no analysis recipe`,
        what: `${rq.id} is declared but no recipe in the analysis plan targets it.`,
        why: 'Every RQ must trace to at least one recipe (FR-ANA-*, RQ-F2).',
        how: `Add a recipes entry for ${rq.id} to the protocol's analysisPlan.`,
        trace: rq.id,
      })
    }
  }

  // 3. Un-run recipes become actionable once data collection is behind us.
  if (currentIndex > PHASE_ORDER.indexOf('data-collection')) {
    for (const rq of status.researchQuestions) {
      for (const recipe of rq.recipes) {
        if (!rq.recipeRuns.includes(recipe)) {
          cards.push({
            id: `recipe:${recipe}`,
            kind: 'recipe-unrun',
            column: 'todo',
            title: `Recipe not yet run: ${recipe}`,
            what: `${recipe} (answers ${rq.id}) has no recorded run.`,
            why: `The analysis plan maps ${rq.id} to this recipe; without a run the RQ is unanswered.`,
            how: `Run \`analysis run ${recipe}\` against the collected dataset.`,
            trace: rq.id,
          })
        }
      }
    }
  }

  // 4. One card per participant below the planned session count. Sessions
  //    with integrity flags still count as collected - they get their own
  //    integrity card instead of double-penalizing the participant.
  const perParticipant = new Map<number, Set<string>>()
  for (const s of status.sessions) {
    const n = participantNumber(s.participantId)
    if (n === null) continue
    if (!perParticipant.has(n)) perParticipant.set(n, new Set())
    perParticipant.get(n)!.add(s.condition)
  }
  for (let n = 1; n <= status.plannedParticipants; n++) {
    const collected = perParticipant.get(n)?.size ?? 0
    if (collected >= status.plannedSessionsPerParticipant) continue
    const missing = status.conditions.filter(
      (c) => !perParticipant.get(n)?.has(c),
    )
    cards.push({
      id: `participant:${participantLabel(n)}`,
      kind: 'participant-data',
      column: 'waiting',
      title: `${participantLabel(n)}: ${collected}/${status.plannedSessionsPerParticipant} sessions`,
      what: `Missing condition${missing.length === 1 ? '' : 's'}: ${missing.join(', ') || 'n/a'}.`,
      why: `The protocol plans ${status.plannedParticipants} participants x ${status.plannedSessionsPerParticipant} sessions (within-subjects).`,
      how: 'Schedule and run the remaining sessions; cards clear as data lands.',
      trace: 'FR-DASH-1',
    })
  }

  // 5. One card per open integrity warning (seq gaps, flagged rows).
  for (const s of status.sessions) {
    if (s.gapCount > 0) {
      cards.push({
        id: `integrity:gaps:${s.sessionId}`,
        kind: 'integrity',
        column: 'todo',
        title: `${s.sessionId}: ${s.gapCount} seq gap${s.gapCount === 1 ? '' : 's'}`,
        what: `${s.missingEvents} event${s.missingEvents === 1 ? '' : 's'} missing from the sequence.`,
        why: 'Loss must be detectable and accounted for (NFR-2, FR-ING-3).',
        how: `Re-import the session's local JSONL (the source of truth) via /ingest/events; the gap report clears when seqs are contiguous.`,
        trace: 'FR-ING-3',
      })
    }
    if (s.flaggedEvents > 0) {
      cards.push({
        id: `integrity:flags:${s.sessionId}`,
        kind: 'integrity',
        column: 'todo',
        title: `${s.sessionId}: ${s.flaggedEvents} flagged row${s.flaggedEvents === 1 ? '' : 's'}`,
        what: `Integrity flags: ${s.flagKinds.join(', ')}.`,
        why: 'Rows outside the protocol are stored and flagged, never dropped (FR-ING-6).',
        how: 'Check participant/condition spelling in the session config, or amend the protocol; re-ingest corrected rows.',
        trace: 'FR-ING-6',
      })
    }
  }

  // 6. One card per open operational finding not already carded from the
  //    status doc (FR-META-1): recipe requires-failures, gate blocks logged
  //    by the scan, protocol-validation defects, facilitator notes. The
  //    framework's own flaws are work items (RQ-F2).
  for (const f of findings) {
    if (f.status !== 'open') continue
    if (STATUS_CARDED_KINDS.has(f.kind)) continue
    cards.push({
      id: `finding:${f.id}`,
      kind: 'finding',
      column: 'todo',
      title: `Finding: ${f.kind || 'operational defect'}`,
      what: f.message,
      why: `Operational defect evidencing ${f.requirementId || 'a requirement'} (FR-META-1).`,
      how: 'Resolve the defect, or fold it into the retrospective proposal.',
      trace: f.requirementId || 'FR-META-1',
    })
  }

  // 7. Manual cards - the only mutable dashboard state (stored middleware-side).
  for (const t of manual) {
    cards.push({
      id: `manual:${t.id}`,
      kind: 'manual',
      column: t.status === 'done' ? 'done' : 'todo',
      title: t.title,
      what: t.note || 'Researcher-added task.',
      why: 'Manually added by a researcher.',
      how: 'Mark it done when finished.',
      trace: 'FR-DASH-7',
      manualId: t.id,
    })
  }

  const columnOrder: Record<Column, number> = {
    todo: 0,
    waiting: 1,
    blocked: 2,
    done: 3,
  }
  return cards.sort(
    (a, b) =>
      columnOrder[a.column] - columnOrder[b.column] ||
      a.kind.localeCompare(b.kind) ||
      a.id.localeCompare(b.id),
  )
}
