# FR-LIT-8/9/10: Corpus at scale, matching, living literature (detailed spec)

**SRS rows:** FR-LIT-8 (corpus scale + pipeline), FR-LIT-9 (idea→paper
matching), FR-LIT-10 (living literature view / scoped RAG).
**Phases:** FR-LIT-8 pipeline + importer (phase 15); FR-LIT-9 phase 15;
FR-LIT-10 phases 15/17. The corpus is uncapped and metric-rich: 1,000 is
the floor, not the ceiling; Tier A is a continuing curation program.
Design detail: `docs/design/sequences.md` §2/3/5,
`docs/design/ui-motion-spec.md` §4.

## 1. FR-LIT-8: the corpus (1,000-paper floor, uncapped)

### Tiers (provenance is a first-class property)

- **Tier A**: the hand-curated seeds (`docs/papers/README.md`), each
  with a human "why it's here". Never machine-modified. **A continuing
  curation program** (rev 2): the pipeline's `--propose-tier-a N` emits
  a promotion shortlist of the top-scored Tier B rows with all quality
  metrics (freshness, citations + influential citations, recognized
  venue, open-access, seed connectivity); the curator skips
  out-of-scope entries (generic LLM infrastructure) and writes or
  approves every "why": judgment stays human, mechanics get generated.
  Promotions leave Tier B (a paper lives in exactly one tier) and widen
  the next snowball walk.
- **Tier B**: harvested: citation snowballing from Tier A over the
  Semantic Scholar Graph API (D36). Every entry carries `s2PaperId`,
  external IDs, `score`, and `via` (which seeds discovered it); every
  row independently verifiable against the public API.
- **study**: papers a researcher ingested directly into a study
  (FR-LIT-1 path, unchanged).

### The pipeline (`scripts/corpus_harvest.py`)

1. Candidates = union of references + citations of every Tier A seed
   (nested fetch, paced to the public pool, cached per-seed, resumable).
2. **Quality gate** (the "quality of corpus is not undermined" rule):
   verifiable external ID (DOI or arXiv) mandatory; titled + dated;
   age-scaled citation floors (pre-2015: ≥200, classics only;
   pre-2018: ≥100; ≥3y old: ≥10; 2y old: ≥3); papers from the last ~2
   years pass on seed-connectivity alone (**fresh precedence**).
3. **Selection is uncapped** (rev 2): every gate-passing candidate that
   is *domain-woven* ships: woven = referenced/cited by ≥2 seeds, or
   fresh (≤2 years; recent papers haven't had time to accumulate
   edges). `--target N` remains as the legacy capped mode. The corpus
   grows as far as quality allows; 1,000 total is a floor the pipeline
   warns under, never a cut line.
4. **Ranking (scoring formula)**: `freshness×1.6 + log10(cites+1)×2 +
   log10(influentialCites+1)×1.2 + min(seedEdges,6)×1.5 + venueBonus
   (0.5 any venue + 1.0 recognized venue) + 0.4 openAccess`: fresh
   papers, papers whose citations actually *used* them, recognized
   venues/labs, and reproducibility-friendly open access all count;
   raw citation mass alone does not win. Recognized venues are a
   versioned regex (ICSE/FSE/CHI/TSE/EMSE/NeurIPS…: editorial
   judgment, changed only as a recorded decision, like the gate).
5. Output: `docs/papers/corpus-index.json` (machine layer) +
   `docs/papers/CORPUS.md` (generated human index, marked
   do-not-hand-edit). PDFs are not bulk-fetched (index-of-record
   posture, consistent with the gitignored-PDF rule; full text enters
   the FTS index on ingest/demand).
6. **Honesty invariants:** nothing synthesized; unresolvable seeds
   reported; deterministic given its cache; the gate/rank constants are
   versioned editorial judgment (changing them is a recorded decision).

### Future sources (the agentic-discovery extension point, D36)

alphaXiv / HF daily papers / OpenAlex / Connected Papers may join as
candidate *sources* behind the same adapter shape (emit candidates →
same gate → same rank). A trending signal is never a quality signal; no
source bypasses the gate. Each activation = its own D-row.

### Fit criteria

- F8.1 `corpus-index.json` + README seeds total ≥ 1,000 entries (the
  floor; uncapped mode ships every woven gate-passer above it); every
  Tier B entry resolves at the S2 API (spot-check protocol: random 20).
- F8.2 Rerunning against the same cache is byte-identical; rerunning
  fresh only moves scores/adds papers: never invents.
- F8.3 ≥ 60% of Tier B is ≤ 3 years old (fresh precedence, measured).
- F8.4 The importer lands Tier B as `Paper(tier=B)` rows + FTS entries;
  the constellation renders tiers distinguishably.
- F8.5 (rev 2) Every Tier B row carries its quality metrics
  (citations, influential citations, venue + recognized flag,
  open-access, publication types, via-trail) and the index records its
  `scoringVersion`; `--propose-tier-a` renders a shortlist from those
  metrics alone (no re-fetch).

## 2. FR-LIT-9: matching papers to the idea

1. **Trigger:** conversation context updates (new RQ slot, new measure,
   researcher asks "what's out there?") debounce into a match request;
   also invokable explicitly from the constellation's search.
2. **Ladder** (each rung optional, degrades to the one below):
   a. LLM rerank + one-line match reasons (cite-what-you-were-given);
   b. FTS relevance over title+abstract+extracted text;
   c. seed-connectivity neighborhoods (pure graph, no text).
3. **Presentation:** recommendation cards in-thread (design:
   `ui-motion-spec.md` §2), tier badge always visible, match reason
   always visible, one-click add → `PaperSetEntry(addedVia=match,
   matchReason)`: the reason is *kept*, it is elicitation evidence.
4. Added papers immediately: join the study RAG scope, strengthen
   FR-CONV-2 grounding retrieval, and appear in the constellation with
   the arrival animation.

Fit: F9.1 the scripted "over-trust juniors" demo conversation surfaces
`trust-in-ai-code-generation` + `insecure-code-with-ai-assistants`
among top-5 with reasons; F9.2 with no LLM key the same conversation
still surfaces both via FTS (reasons = matched terms); F9.3 an added
paper is retrievable in the very next assistant exchange.

## 3. FR-LIT-10: the living literature view

1. One canvas: the citation constellation (design contract in
   `ui-motion-spec.md` §4: idle drift, cite-pulses, arrival streaks,
   cluster halos, gap halos, lasso scope; deterministic per-study
   layout seed; reduced-motion = zero function loss).
2. **Scoped RAG:** selection sets the assistant's retrieval scope;
   answers about methodology/statistics/validation are grounded in the
   scoped papers + template registry, chip-cited (FR-LIT-4 rules,
   FR-ETH-4 boundary: aggregates only, never events).
3. **Guidance intents** (first-class prompts surfaced as buttons over a
   selection): "how did these validate their measures?", "what designs
   did they use?", "what statistics would replicate this?", "where are
   the gaps vs. my RQs?": each answer may emit design moves back into
   the conversation (the loop closes: literature → design).
4. Gap halos double as elicitation: clicking drafts a gap note turn
   ("no scoped paper measures X under Y") the researcher can turn into
   an RQ (FR-LIT-9 loop-back, `flows.md` §2).

Fit: F10.1 lasso 6 papers → ask a methods question → every claim chips
into the 6 (grep-the-output on citations); F10.2 the cite-pulse fires
for a chip-click and for a streamed citation; F10.3 reduced-motion run
completes the same walkthrough with identical information available;
F10.4 ≥500-node corpus renders at 60fps on the demo hardware profile.

## 4. Privacy & degradation summary

The corpus and constellation contain *published literature only*: no
participant data ever enters these surfaces; the RAG scope mechanism is
retrieval scoping, not access control (FR-ETH-4 remains the access
boundary). Offline: cached graph + FTS matching + structured designer;
the platform's literature features never hard-require any external
service (NFR-4/5/7).
