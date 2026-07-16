import { describe, expect, it } from 'vitest'
import type { Finding, ManualTask, SessionStatus, StatusDoc } from '../src/lib/api'
import { deriveCards } from '../src/lib/derive'

function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: 1,
    at: '2026-07-11T12:00:00.000+00:00',
    source: 'analysis/run',
    kind: 'requires-fail',
    requirementId: 'FR-ANA-2',
    message: 'agent-interaction-dynamics (RQ-P5): MISSING DATA',
    context: {},
    status: 'open',
    ...overrides,
  }
}

/** A middleware status fixture mirroring the pilot protocol's shape. */
function makeStatus(overrides: Partial<StatusDoc> = {}): StatusDoc {
  return {
    studyId: 'pilot-2026',
    generatedAt: '2026-07-11T12:00:00.000+00:00',
    lifecycle: {
      currentPhase: 'ethics',
      phases: [
        {
          name: 'design',
          status: 'complete',
          gates: [
            { artifact: 'protocol-validated.txt', satisfied: true, satisfiedBy: { fileId: 1, uploadedAt: 'x', size: 1 } },
            { artifact: 'task-definitions.md', satisfied: true, satisfiedBy: { fileId: 2, uploadedAt: 'x', size: 1 } },
          ],
        },
        {
          name: 'ethics',
          status: 'current',
          gates: [
            { artifact: 'ethics-approval.pdf', satisfied: false, satisfiedBy: null },
            { artifact: 'consent-form.pdf', satisfied: false, satisfiedBy: null },
          ],
        },
        {
          name: 'pilot',
          status: 'upcoming',
          gates: [{ artifact: 'dry-run-report.md', satisfied: false, satisfiedBy: null }],
        },
        { name: 'recruitment', status: 'upcoming', gates: [] },
        { name: 'data-collection', status: 'upcoming', gates: [] },
        { name: 'analysis', status: 'upcoming', gates: [] },
        { name: 'write-up', status: 'upcoming', gates: [] },
      ],
    },
    conditions: ['ai-assisted', 'unassisted'],
    plannedParticipants: 2,
    plannedSessionsPerParticipant: 2,
    sessions: [],
    researchQuestions: [
      { id: 'RQ-P1', recipes: ['fatigue-by-condition'], recipeRuns: [] },
      { id: 'RQ-P2', recipes: ['code-quality-by-condition'], recipeRuns: [] },
    ],
    ...overrides,
  }
}

function session(overrides: Partial<SessionStatus>): SessionStatus {
  return {
    sessionId: 'S1',
    participantId: 'P01',
    condition: 'ai-assisted',
    events: 10,
    metricRows: 0,
    flaggedEvents: 0,
    flagKinds: [],
    gapCount: 0,
    missingEvents: 0,
    complete: true,
    lastReceivedAt: '2026-07-11T11:00:00.000+00:00',
    ...overrides,
  }
}

describe('deriveCards - gate artifacts', () => {
  it('creates one card per unsatisfied gate: current phase actionable, later phases blocked', () => {
    const cards = deriveCards(makeStatus(), [])
    const gates = cards.filter((c) => c.kind === 'gate')
    expect(gates.map((c) => [c.id, c.column])).toEqual(
      expect.arrayContaining([
        ['gate:ethics/ethics-approval.pdf', 'todo'],
        ['gate:ethics/consent-form.pdf', 'todo'],
        ['gate:pilot/dry-run-report.md', 'blocked'],
      ]),
    )
    // Satisfied design gates produce no cards.
    expect(gates.some((c) => c.id.startsWith('gate:design/'))).toBe(false)
    // Every card explains itself: what / why (trace) / how to clear.
    for (const c of gates) {
      expect(c.why).toContain('FR-PROT-3')
      expect(c.how).toBeTruthy()
    }
  })

  it('cards clear themselves when the middleware reports the gate satisfied', () => {
    const status = makeStatus()
    const before = deriveCards(status, [])
    expect(before.some((c) => c.id === 'gate:ethics/ethics-approval.pdf')).toBe(true)

    status.lifecycle.phases[1].gates[0] = {
      artifact: 'ethics-approval.pdf',
      satisfied: true,
      satisfiedBy: { fileId: 9, uploadedAt: 'x', size: 10 },
    }
    const after = deriveCards(status, [])
    expect(after.some((c) => c.id === 'gate:ethics/ethics-approval.pdf')).toBe(false)
  })
})

describe('deriveCards - RQ coverage and recipes', () => {
  it('flags an RQ with no planned recipe', () => {
    const status = makeStatus({
      researchQuestions: [{ id: 'RQ-P9', recipes: [], recipeRuns: [] }],
    })
    const [card] = deriveCards(status, []).filter((c) => c.kind === 'rq-uncovered')
    expect(card.id).toBe('rq:RQ-P9')
    expect(card.column).toBe('todo')
    expect(card.trace).toBe('RQ-P9')
  })

  it('creates un-run recipe cards only after data collection', () => {
    const before = deriveCards(makeStatus(), [])
    expect(before.some((c) => c.kind === 'recipe-unrun')).toBe(false)

    const status = makeStatus()
    status.lifecycle.currentPhase = 'analysis'
    const after = deriveCards(status, [])
    const recipes = after.filter((c) => c.kind === 'recipe-unrun')
    expect(recipes.map((c) => c.id).sort()).toEqual([
      'recipe:code-quality-by-condition',
      'recipe:fatigue-by-condition',
    ])

    // A recorded run clears the card - the board is a projection.
    status.researchQuestions[0].recipeRuns = ['fatigue-by-condition']
    const cleared = deriveCards(status, []).filter((c) => c.kind === 'recipe-unrun')
    expect(cleared.map((c) => c.id)).toEqual(['recipe:code-quality-by-condition'])
  })
})

describe('deriveCards - participants below plan', () => {
  it('cards each participant missing sessions, naming the missing conditions', () => {
    const status = makeStatus({
      sessions: [session({ sessionId: 'S1', participantId: 'P01', condition: 'ai-assisted' })],
    })
    const waiting = deriveCards(status, []).filter((c) => c.kind === 'participant-data')
    expect(waiting.map((c) => c.id)).toEqual(['participant:P01', 'participant:P02'])
    expect(waiting[0].column).toBe('waiting')
    expect(waiting[0].title).toBe('P01: 1/2 sessions')
    expect(waiting[0].what).toContain('unassisted')
    expect(waiting[1].title).toBe('P02: 0/2 sessions')
  })

  it('emits no card for a participant with a full session set', () => {
    const status = makeStatus({
      sessions: [
        session({ sessionId: 'S1', participantId: 'P01', condition: 'ai-assisted' }),
        session({ sessionId: 'S2', participantId: 'P01', condition: 'unassisted' }),
      ],
    })
    const waiting = deriveCards(status, []).filter((c) => c.kind === 'participant-data')
    expect(waiting.map((c) => c.id)).toEqual(['participant:P02'])
  })
})

describe('deriveCards - integrity warnings', () => {
  it('cards seq gaps and flagged rows separately, and they reappear if data regresses', () => {
    const clean = makeStatus({
      sessions: [session({ sessionId: 'S1' }), session({ sessionId: 'S2', participantId: 'P02' })],
    })
    expect(deriveCards(clean, []).filter((c) => c.kind === 'integrity')).toHaveLength(0)

    // Re-flagging a gap makes the corresponding card reappear (acceptance
    // criterion): same projection, changed facts.
    const regressed = makeStatus({
      sessions: [
        session({ sessionId: 'S1', gapCount: 2, missingEvents: 5, complete: false }),
        session({
          sessionId: 'S2',
          participantId: 'P02',
          flaggedEvents: 3,
          flagKinds: ['unknown-participant'],
        }),
      ],
    })
    const cards = deriveCards(regressed, []).filter((c) => c.kind === 'integrity')
    expect(cards.map((c) => c.id)).toEqual([
      'integrity:flags:S2',
      'integrity:gaps:S1',
    ])
    expect(cards.find((c) => c.id === 'integrity:gaps:S1')!.title).toBe('S1: 2 seq gaps')
    expect(cards.find((c) => c.id === 'integrity:flags:S2')!.what).toContain(
      'unknown-participant',
    )
  })
})

describe('deriveCards - operational findings (FR-META-1)', () => {
  it('cards an open finding not already carded from the status doc', () => {
    const [card] = deriveCards(makeStatus(), [], [finding()]).filter(
      (c) => c.kind === 'finding',
    )
    expect(card.id).toBe('finding:1')
    expect(card.column).toBe('todo')
    expect(card.trace).toBe('FR-ANA-2')
    expect(card.what).toContain('MISSING DATA')
  })

  it('does not double-card a seq gap the status doc already surfaces', () => {
    // MP-11 acceptance: a seq gap + a requires-fail yield two cards - the gap
    // via the integrity projection, the requires-fail via the findings feed -
    // not two finding cards for the one gap.
    const status = makeStatus({
      sessions: [session({ sessionId: 'S1', gapCount: 1, missingEvents: 1, complete: false })],
    })
    const findings: Finding[] = [
      finding({ id: 1, kind: 'seq-gap', requirementId: 'FR-ING-3', context: { session: 'S1' } }),
      finding({ id: 2, kind: 'requires-fail' }),
    ]
    const cards = deriveCards(status, [], findings)
    expect(cards.filter((c) => c.kind === 'finding').map((c) => c.id)).toEqual(['finding:2'])
    expect(cards.filter((c) => c.kind === 'integrity').map((c) => c.id)).toEqual([
      'integrity:gaps:S1',
    ])
  })

  it('drops resolved findings - the board is a live projection', () => {
    const cards = deriveCards(makeStatus(), [], [finding({ status: 'resolved' })])
    expect(cards.some((c) => c.kind === 'finding')).toBe(false)
  })
})

describe('deriveCards - manual cards', () => {
  it('keeps manual tasks alongside derived cards; done ones archive to Done', () => {
    const manual: ManualTask[] = [
      { id: 1, title: 'print consent forms', status: 'open', note: '', createdAt: 'x' },
      { id: 2, title: 'book lab room', status: 'done', note: 'room 2.11', createdAt: 'x' },
    ]
    const cards = deriveCards(makeStatus(), manual)
    const open = cards.find((c) => c.id === 'manual:1')!
    const done = cards.find((c) => c.id === 'manual:2')!
    expect(open.column).toBe('todo')
    expect(open.manualId).toBe(1)
    expect(done.column).toBe('done')
    expect(done.what).toBe('room 2.11')
  })
})
