# Mega-Prompt 16 — The Curated-Dataset Leg

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `requirements/specs/fr-cur.md` (the
> requirement of record), `docs/design/state-machines.md` §3,
> `docs/design/data-model.md` (CuratedDataset/MiningJob),
> `docs/design/flows.md` §1 (the dataset-exists branch),
> `requirements/build-vs-adopt.md` (a GitHub-client decision may be
> needed — see freedoms), and `docs/roadmap/README.md` (walls + charter).

**Depends on:** MP-15 slice 3 (the template registry — `cursor-mining-v1`
is this phase's demand-side), MP-04 (middleware, ingestion, per-source
streams from MP-12), MP-02 (protocol schema — gains a curated-path
section). **Satisfies:** FR-CUR-1..3 (FR-CUR-4 stays deferred).
**Elicited:** owner, MP-01 rev 8 ("curated mining beside live capture").
**Status:** Open.

## The idea

Make the **"does the dataset already exist?" branch real**. Half the
empirical literature never runs a live session — it mines repos, PRs,
and archives. After this phase, a researcher whose answer is *yes*
declares a sampling frame in the protocol, runs a mining job, and gets
the same joined timeline, the same recipes, the same honest report and
paper draft as a live study — **zero recipe-layer changes** (FR-CUR
F1.1 is the phase's north star). The architectural bet being cashed:
the join-key event schema is the convergence contract.

Non-negotiable bounds, inherited verbatim:

- **Join keys, reinterpreted and documented** (FR-CUR-1): mined
  `participantId` = the declared anonymized actor unit (salted-hash
  pseudonyms); `condition` = the study's comparison arm; `sessionId` =
  the mined activity unit (PR, issue thread, commit-batch window);
  timestamps are the *source's* event times, never import time.
- **Idempotent re-mining** (F1.2): `seq` is the adapter's deterministic
  ordinal; re-running a job produces zero duplicate rows (the FR-ING-2
  replay mechanism, reused not reinvented).
- **Privacy extends to strangers** (F1.3): mined authors are
  pseudonymized by construction; no raw identities, commit messages, or
  code content unless the protocol's content policy explicitly scopes it
  (FR-AGENT-5 mechanism reused). Public data ethics are still ethics.
- **The frame comes first** (F2.2): the adapter refuses to run without a
  protocol-declared sampling frame — the mined equivalent of "the
  approved protocol is the executed protocol".
- **Honesty travels with the data** (FR-CUR-3): no validity-threats
  record → the analysis gate blocks. The record is injected verbatim
  into report + paper-draft threats sections.

## Slices

### Slice A — The normalizer contract + event vocabulary (FR-CUR-1)

1. **Event vocabulary, schema v5** (registered beside v3/v4 in the
   versioned vocabulary; consumers branch):
   `mined_commit`, `mined_pull_request`, `mined_review`,
   `mined_issue_event`, `mined_actor_snapshot` — all content-free by
   default: sizes, counts, timings, flags, salted hashes. Payload shapes
   documented next to the existing event docs.
2. **The adapter contract** — one Python protocol, adapters register in
   a dict (the per-source stream mechanism from MP-12 carries the
   `source` column):

   ```python
   class MiningAdapter(Protocol):
       source: str                                   # "github"
       def plan(self, frame: SamplingFrame) -> CoverageEstimate: ...
       def run(self, frame: SamplingFrame, cursor: Cursor | None
               ) -> Iterator[NormalizedEvent | CursorCheckpoint]: ...
   ```

   `run` yields events *and* periodic cursor checkpoints; the job runner
   persists each checkpoint, which is the whole resume story (F2.1) —
   no separate resume machinery.
3. **Pseudonymization**: per-dataset salt (server-side, never exported);
   actor → `participantId` mapping lives only as the hash.
4. **Protocol schema addition**: a `curated:` section (sampling frame:
   query, window, inclusion rules, exclusions, target n; declared actor
   unit; content policy). Additive schema change ⇒ `protocolVersion`
   bump; the validator branches (FR-PROT-2).
5. **Static metrics on mined code**: reuse the metrics leg against
   checked-out snapshots via the shadow-git machinery (D14) pointed at
   mined refs — explicitly *no second metrics pipeline*.

### Slice B — The GitHub adapter + job runner (FR-CUR-2)

1. **Sources**: repos, PRs (+ reviews, timelines), commits, issues via
   REST/GraphQL. **Agent-authorship heuristics are a versioned
   registry**, not inline cleverness:

   ```python
   HEURISTICS = [
     Heuristic(id="bot-suffix", version=1, cite="aidev-ai-coding-agents-github",
               known_failure_modes=["renamed bots"], fn=...),
     Heuristic(id="coauthor-trailer", version=1, ...),
     Heuristic(id="agent-signature", version=1,
               cite="mining-coding-agent-activity", ...),
   ]
   ```

   Every applied heuristic lands (id + version) in the dataset's
   validity-threats record.
2. **Job runner**: jobs run as background asyncio tasks inside the one
   FastAPI process (NFR-7 — no worker fleet); state + cursor + coverage
   persist in `MiningJob` per the state machine
   (`state-machines.md` §3): `declared → running ⇄ paused_rate_limited /
   interrupted → gated → complete | failed_gate`. Interrupted jobs offer
   resume; they never auto-restart.
3. **Operational posture** (NFR-4): token-scoped; primary *and*
   secondary rate limits honored with backoff; responses cached
   (content-addressed on request shape); degrades to cache offline.
4. **API surface**:

   ```
   POST   /projects/{p}/studies/{s}/mining-jobs        start (frame from protocol; refuses without one)
   GET    .../mining-jobs/{id}                          state, cursor, coverage, plain-language status
   POST   .../mining-jobs/{id}/resume                   from persisted cursor
   POST   .../mining-jobs/{id}/stop
   GET    .../curated-datasets/{id}                     dataset + threats record
   ```

5. **Conversation integration**: the dataset-exists branch is a design
   move — the platform proposes the sampling frame as a card (grounded
   in the template's source paper), and the compiled `curated:` section
   is a diff hunk like any other. The form path (FR-TPL-3) edits the
   same fields.

### Slice C — The validity-threats record + honest reporting (FR-CUR-3)

1. Record shape per `fr-cur.md` §4 (samplingFrame, heuristics with
   versions + known failure modes + citations, biases with direction and
   mitigation-or-accepted, coverage with per-reason drop counts).
   Authored as YAML; partially machine-filled (coverage, heuristic list
   are *generated*; biases are the researcher's honest work, prompted by
   named starter entries).
2. **Lifecycle gate**: a curated study cannot enter `analysis` without
   the record (F3.2) — enforced exactly like every other gate artifact.
3. **Report + paper injection**: threats section populated from the
   record with heuristic citations (F3.1), via the existing FR-ANA-4/6
   deterministic generation.
4. **UI**: mining-job screen (progress with coverage, the breathing
   rate-limit pause from `ui-motion-spec.md` §5 — calm, tooltip'd,
   plain-language); dataset browser and threats record in strict precise
   register (this is the platform's honesty made visible — zero
   animation, tabular numerals, hairline rules).

### Slice D — The demo dataset (the phase proof)

A committed, sanitized **fixture cassette** (recorded GitHub API
responses, pseudonymized at record time) so CI and the demo run with
zero tokens and zero network:

1. `cursor-mining-v1` instantiates (conversation or form) → sampling
   frame → mining job against the cassette → normalizer → joined
   timeline → gap report per source → recipes → per-RQ report → paper
   draft with populated threats section. **The full v1 chain, zero
   recipe-layer changes** (F1.1).
2. Cassette tests also simulate 403/429 (pause behavior) and mid-job
   interruption (resume without duplicates, F2.1).

## Degrees of freedom

- **REST vs. GraphQL mix** per source type; page sizes; cache layout —
  yours. A GitHub client *library* (vs. plain httpx) needs its D-row;
  plain httpx needs nothing.
- **Cassette format** — record/replay implementation is yours (fixture
  JSON, VCR-style, hand-rolled); the requirements are: committed,
  sanitized, deterministic, simulates rate-limit and interruption.
- **Coverage visualization** — how requested/retrieved/dropped renders
  (follow the `dataviz` skill); the numbers themselves are fixed by the
  record shape.
- **Heuristic implementation order** — ship the registry with the three
  named heuristics minimum; add more freely (each with id, version,
  cite, failure modes).
- **Actor-unit windowing** — how commit-batch windows are drawn when the
  protocol picks that unit; document the rule in the dataset record.

## Acceptance (maps to fit criteria)

- F1.1 demo dataset runs the full chain unchanged, zero recipe edits.
- F1.2 re-run ⇒ zero duplicates (test re-runs the cassette job twice).
- F1.3 grep-the-output on mined payloads: no raw identity/message/code
  outside a protocol-scoped content policy.
- F2.1 interrupt at ~50% ⇒ resume completes without duplicates.
- F2.2 jobless-frame refusal; F2.3 rate-limit pause is visible,
  plain-language, never a crash.
- F3.1 paper draft's threats section populated with heuristic
  citations; F3.2 missing record blocks the analysis gate.
- NFR-12: mining/dataset surfaces pass the token/theme/reduced-motion/
  axe gates like every surface.

## Verification steps

1. `uv run pytest && uv run ruff check .` — normalizer, adapter,
   runner, gate, injection tests all green, all offline (cassette).
2. The slice-D demo, recorded end to end (screen capture or scripted
   walkthrough): instantiate → mine → report → paper threats section.
3. `protocol validate` green on the demo study's compiled protocol
   (with the new `curated:` section, bumped version).
4. NFR-12 evidence archived for the new surfaces.

## Deviations log

Record departures here and in `requirements/traceability.md` §3.
