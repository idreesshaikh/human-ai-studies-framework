# Proposal — retire the Tier A / Tier B split for a single quality-gated corpus

**Status: proposal, not adopted.** Nothing in this document is built; it
exists so the owner can review the shape of the change before any code,
schema, or requirement moves. Elicited from a design conversation
(2026-07-21): *"remove tier a and tier b — the only way to bring them into
some hierarchy would be a quality gate."*

## The critique, stated precisely

Today's corpus (FR-LIT-8, `requirements/specs/fr-lit.md` §1) is split into
two named tiers:

- **Tier A** — 100 hand-curated seeds (`docs/papers/README.md`), each with a
  human-written "why". Never machine-modified.
- **Tier B** — 14,900 harvested rows (`docs/papers/corpus-index.json`),
  each carrying a computed `score` (freshness + citations + influential
  citations + seed-connectivity + venue + open-access).

The names "Tier A" / "Tier B" read as a quality ranking — A is better than
B. But that isn't what the data actually says. Tier A's *original* 58 rows
were picked by hand before `score()` existed at all; Tier B's `score` is
the only rigorous, comparable, machine-checkable quality signal in the
whole corpus. It is entirely possible — likely, even — that dozens of Tier
B rows out-score some original Tier A picks. The one honest quality
hierarchy the corpus has is `score`, and it currently applies to only
14,900 of the 15,000 rows; the other 100 sit in a separately-named bucket
exempted from it by convention, not by merit.

The pipeline already half-admits this: `propose_tier_a(n)` (`scripts/
corpus_harvest.py:281`) is a promotion mechanism that ranks Tier B by
`score` and offers the top N as candidates to *become* Tier A — i.e. the
system already treats `score` as the real gate and "Tier A" as a status a
paper is promoted into, not a quality band it starts in.

## What Tier A actually provides (and must not lose)

Two genuinely different things are bundled into "Tier A" today, and the
merge has to keep both without keeping the false hierarchy:

1. **The human-written "why"** — a one-line rationale tying the paper to
   this project's specific motivation. This is curation content, not a
   quality score; no formula produces it.
2. **The snowball seed set** — `read_seeds()` parses Tier A's README table
   for arXiv IDs and uses them as the starting points the citation-graph
   walk expands from. This is a structural role (every Tier B row exists
   *because* it's reachable from a seed), not a quality claim.

Both roles are worth preserving. Neither requires a separate "tier".

## Proposed model

One corpus, one quality signal (`score`), two independent boolean-ish
properties any row may carry:

```jsonc
{
  "ref": "arxiv:2507.09089",
  "title": "...",
  "year": 2025,
  "score": 14.2,
  "isSeed": true,              // was: "lives in Tier A" (structural role)
  "why": "RCT: devs 19% slower with AI while believing the opposite — ...",
  // "why" is present only on annotated rows (was: the Tier A / Tier B
  // split itself); absent elsewhere. A row can be a seed without a why
  // (inherited from an old seed list) or have a why without being a
  // seed (a well-annotated non-seed paper) — the two properties are
  // independent, where today they're conflated into one tier.
  "citationCount": 412,
  "influentialCitationCount": 38,
  "via": ["arxiv:2205.06537", "..."]   // unchanged — snowball provenance
}
```

- **`docs/papers/corpus-index.json`** gains one flat array (`papers`)
  replacing the `tierA`/`tierB` split; every row carries `score`, and
  `isSeed`/`why` are optional fields present only where they apply.
- **`docs/papers/README.md`** stops being "the Tier A file" and becomes
  *the annotated index* — every row with a `why`, sorted however is most
  readable (by section, as today), explicitly captioned as "these are the
  papers with a human-written rationale, not the top-scored papers" so
  the ranking-by-tier misreading can't recur. The existing 100 rows and
  their `why` text move over unchanged — no curation work is lost.
- **`docs/papers/CORPUS.md`** (generated) becomes the single generated
  view of the *whole* corpus, sorted by `score` descending, with a `why`
  column populated wherever one exists and blank otherwise — replacing
  the current Tier A/Tier B section split with one ranked list, which is
  the more honest "here is the corpus, best-quality-signal first" framing
  the critique is asking for.
- **The quality gate itself does not change.** `quality_gate()` and
  `score()` (`corpus_harvest.py:244-278`) keep gating/ranking every
  candidate exactly as today — this proposal removes a *naming/hierarchy*
  problem, not the actual quality mechanism, which is already sound.

## Pipeline changes (`scripts/corpus_harvest.py`)

- `read_seeds()` keeps reading arXiv IDs from `docs/papers/README.md` (the
  annotated file) as today — seeds are still exactly "whatever's in that
  file", the mechanism doesn't change, only what the file is called and
  how it's framed.
- `propose_tier_a(n)` is renamed `propose_annotation(n)` (or similar): same
  behavior (rank-by-score shortlist for hand-curation), reframed as
  "papers worth writing a why for", not "papers worth promoting to a
  better tier".
- The one-way "promotion" ceremony (§G in `docs/papers/README.md`) goes
  away entirely — there's no tier to promote *into*. Adding a `why` to a
  row is a one-line edit to the annotated index, not a file-to-file move,
  and it never changes the row's `score` or its standing in the ranked
  view.
- `corpus-index.json`'s `generatedAt`/`pipeline`/`scoringVersion` metadata
  is unchanged; only the `tierA`/`tierB` keys collapse into `papers` (a
  `schemaVersion` bump on this file, since consumers branch on shape —
  same discipline as `protocolVersion`).

## What this touches (full blast radius, for when/if this is adopted)

- `requirements/specs/fr-lit.md` §1 "Tiers (provenance is a first-class
  property)" — rewrite to the single-corpus model above; FR-LIT-8's SRS
  row text and traceability entry need matching updates.
- `docs/papers/README.md`, `docs/papers/CORPUS.md`, `corpus-index.json` —
  as described above.
- `scripts/corpus_harvest.py` — `read_seeds()` framing, `propose_tier_a` →
  `propose_annotation`, output writer (single `papers` array).
- Anywhere in the platform that reads `tierA`/`tierB` keys directly
  (`middleware/` matching/knowledge-layer code, if any — needs a grep pass
  at implementation time) to confirm nothing branches on tier membership
  as a quality proxy today (a quick check during this session found no
  such reads outside the harvest script and its own docs, but a full grep
  should be re-run immediately before implementing, since this doc is a
  proposal, not a completed audit).
- `CLAUDE.md`'s repository-map line for `docs/papers/` ("Tier A seeds ... +
  Tier B") needs a matching rewrite.

## What does NOT change

- The 1,000+-paper floor, uncapped-selection policy, quality-gate
  constants, and scoring formula (FR-LIT-8's actual substance).
- PDFs stay gitignored; the index stays the tracked record.
- The snowball-seed mechanism (structurally identical, just no longer
  called "a tier").
- Every existing hand-written "why" (all 100 survive as annotations on
  the unified list).

## Open question for the owner

Should `isSeed` ever be *editable* independent of `why` — i.e. can a
researcher mark a new paper as a future snowball seed without also
writing a why for it? The current Tier A conflates "seed" and "annotated"
into one action (add a row to the README with a why); this proposal keeps
that as the default path (most seeds will keep getting a why at the same
time) but the schema above allows them to diverge if that's ever useful.
Recommend: keep them coupled in the authoring *workflow* (one form, one
edit) even though the *data model* allows independence — simplicity over
flexibility until a real use case asks for the split.
