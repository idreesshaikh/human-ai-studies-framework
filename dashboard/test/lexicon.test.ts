import { describe, expect, it } from 'vitest'
import { buildLexicon, FALLBACK_REQUIREMENTS, lookup } from '../src/lib/lexicon'

const LIVE = buildLexicon(
  [
    { id: 'FR-DASH-1', priority: 'M', text: 'Live SRS text wins.', status: '✅' },
    { id: 'FR-PROT-7', priority: 'S', text: 'Replication kit.', status: '✅' },
  ],
  [
    { term: 'Recipe', definition: 'A registered, versioned analysis unit.' },
    { term: 'Seq gap', definition: 'A hole in the event sequence = data loss.' },
  ],
)

describe('lexicon lookup precedence (FR-DASH-9)', () => {
  it('live SRS text beats the built-in fallback', () => {
    expect(FALLBACK_REQUIREMENTS['FR-DASH-1']).toBeTruthy()
    expect(lookup(LIVE, 'FR-DASH-1')).toBe('Live SRS text wins.')
  })

  it('resolves ids the fallback never knew (the drift this fixes)', () => {
    expect(FALLBACK_REQUIREMENTS['FR-PROT-7']).toBeUndefined()
    expect(lookup(LIVE, 'FR-PROT-7')).toBe('Replication kit.')
  })

  it('falls back to the built-in map when the SRS is not served', () => {
    const offline = buildLexicon([], [])
    expect(lookup(offline, 'FR-DASH-7')).toBe(FALLBACK_REQUIREMENTS['FR-DASH-7'])
    expect(lookup(null, 'FR-DASH-7')).toBe(FALLBACK_REQUIREMENTS['FR-DASH-7'])
  })

  it('resolves glossary terms case-insensitively', () => {
    expect(lookup(LIVE, 'recipe')).toContain('analysis unit')
    expect(lookup(LIVE, 'Seq Gap')).toContain('data loss')
  })

  it('returns empty string for unknown keys (caller shows the bare id)', () => {
    expect(lookup(LIVE, 'FR-NOPE-99')).toBe('')
    expect(lookup(null, 'whatever')).toBe('')
  })
})
