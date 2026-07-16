/**
 * Fetch-once store over the pure lexicon (FR-DASH-9). Loads the SRS +
 * glossary from the middleware in the background; until then (and on any
 * failure) `describe()` degrades to the built-in fallback map, then to ''.
 */

import { api } from './api'
import { buildLexicon, type Lexicon, lookup } from './lexicon'

class LexiconState {
  data = $state<Lexicon | null>(null)
  private started = false

  /** Fire-and-forget; safe to call more than once. */
  async load(): Promise<void> {
    if (this.started) return
    this.started = true
    const [reqs, glossary] = await Promise.allSettled([
      api.requirements(),
      api.glossary(),
    ])
    this.data = buildLexicon(
      reqs.status === 'fulfilled' ? reqs.value : [],
      glossary.status === 'fulfilled' ? glossary.value : [],
    )
  }

  /** Plain-English text for a requirement id or glossary term ('' if unknown). */
  describe(key: string): string {
    return lookup(this.data, key)
  }
}

export const lexicon = new LexiconState()
