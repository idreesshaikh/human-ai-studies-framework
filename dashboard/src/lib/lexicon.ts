/**
 * Plain-language lookup for everything the dashboard cites (FR-DASH-9).
 *
 * Requirement IDs resolve to live SRS text served by the middleware
 * (`GET /requirements`), domain terms to glossary definitions
 * (`GET /glossary`) - with a built-in fallback map so chips still explain
 * themselves when the documents aren't served (older deployment, files
 * absent, offline). Pure module: node-testable, no runes, no DOM.
 */

import type { GlossaryEntry, RequirementInfo } from './api'

export interface Lexicon {
  /** Requirement id -> SRS requirement text (verbatim from srs.md). */
  requirements: Map<string, string>
  /** Lowercased term -> glossary definition. */
  glossary: Map<string, string>
}

/**
 * Fallback descriptions for the requirement IDs this UI cites, used only
 * when the live SRS isn't available. The document of record always wins.
 */
export const FALLBACK_REQUIREMENTS: Record<string, string> = {
  'FR-DASH-1': 'Study overview: protocol summary, RQs, planned-vs-collected sessions per condition.',
  'FR-DASH-2': 'Lifecycle board: columns are phases; current state computed from gate artifacts, never hand-set.',
  'FR-DASH-3': 'Live sessions with recent events and seq-gap warnings.',
  'FR-DASH-4': 'Per-session swimlane timeline interleaving events from all legs on one time axis.',
  'FR-DASH-5': 'Static-metric distributions split by condition.',
  'FR-DASH-6': 'Every chart displays which RQ/requirement it answers.',
  'FR-DASH-7': 'Dynamic project manager: task board auto-derived from the protocol; cards clear themselves.',
  'FR-DASH-8': 'Dashboard hosts the knowledge views (papers graph, assistant panel).',
  'FR-DASH-9': 'The dashboard explains itself: guided tour + plain-language tooltips sourced from the SRS.',
  'FR-PROT-3': "Lifecycle phases advance only when the previous phase's gate artifacts exist.",
  'FR-ING-3': 'Seq-gap integrity report: data loss is detectable, never silent.',
  'FR-ING-6': 'Rows outside the protocol are stored and flagged, never dropped.',
  'FR-LIT-2': 'Literature graph: ingested papers plus their references, citations, and suggestions.',
  'FR-LIT-3': 'Papers link to the protocol elements they justify.',
  'FR-LIT-4': 'Knowledge assistant: cited answers grounded in the ingested papers and aggregates only.',
  'NFR-2': 'Never lose data: local JSONL is the source of truth; loss must be detectable via seq gaps.',
  'NFR-8': 'Honest statistics: exact tests, effect sizes, per-cell n; never bare p-values.',
}

export function buildLexicon(
  reqs: RequirementInfo[],
  glossary: GlossaryEntry[],
): Lexicon {
  return {
    requirements: new Map(reqs.map((r) => [r.id, r.text])),
    glossary: new Map(glossary.map((g) => [g.term.toLowerCase(), g.definition])),
  }
}

/**
 * Plain-English text for a requirement id or a glossary term; '' when the
 * key is unknown (callers show the bare key). Precedence: live SRS text →
 * built-in fallback → glossary term (case-insensitive).
 */
export function lookup(lex: Lexicon | null, key: string): string {
  return (
    lex?.requirements.get(key) ??
    FALLBACK_REQUIREMENTS[key] ??
    lex?.glossary.get(key.toLowerCase()) ??
    ''
  )
}
