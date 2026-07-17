# Mega-Prompt 11 - Paper Draft Export + Self-Improvement Retrospective

> Self-contained: execute this file in a fresh working session at the repo
> root. Read first: `docs/archive/roadmap/00-VISION.md`, `requirements/srs.md` (FR-ANA-6,
> FR-META-*), the recipe contract (`analysis/core.py`), and the protocol
> schema. For the retrospective's Claude usage, **check the
> current official API docs first** and respect D10's bounds.

**Depends on:** 07 (report exists); 02 (frozen protocol). **Satisfies:**
FR-ANA-6, FR-META-1, FR-META-2. **Sprint day 7 (with MP-08 dry run).**
**Status:** Not started

## Part A - Paper draft export (FR-ANA-6)

The write-up phase becomes a build artifact: `analysis paper
<protocol.yaml> --study <id>` emits `paper/draft.md` + `paper/draft.tex`
(article class, natbib) with:

1. **Title/abstract stub** - templated from protocol metadata; abstract is
   a fill-in skeleton with the study's actual n, conditions, and headline
   effect sizes pre-inserted as `\todo{verify}`-marked sentences.
2. **Introduction/RQs** - the protocol's research questions verbatim, each
   tagged with its ID.
3. **Related work** - seeded from FR-LIT-3 links: one paragraph stub per
   linked paper, grouped by what it justifies, with proper cite keys; a
   generated `references.bib` from ingested paper metadata.
4. **Methodology** - *synthesized from the frozen protocol, not hand-
   written*: participants plan, conditions, counterbalancing, session
   structure, instruments with their exact configs (probe intervals,
   thresholds), metrics with definitions and citations, ethics/consent
   procedure. If the methods section can't be generated, the protocol was
   incomplete - log it as an RQ-F1 specification defect (FR-META-1).
5. **Results** - per RQ: the recipe's methods text, tables (booktabs),
   figures (the recipe's SVG/PNG files, `\includegraphics`), exact tests +
   effect sizes + per-cell n (NFR-8 verbatim from the report).
6. **Threats to validity** - templated skeleton pre-filled with known
   framework limitations (origin-heuristic blind spots from
   `extension/docs/adaptation-notes.md`, small-n framing, single-IDE scope).
7. Every generated claim carries an HTML/LaTeX comment with its trace tag
   (`%% trace: RQ-P4 / ai-review-behavior / FR-INST-8`).

Deterministic given protocol + report (NFR-6): no LLM in the pipeline for
Parts 1–7 - this is templating, and reproducibility is the point.
pytest: golden-file test over the demo study (modulo timestamps).

## Part B - Operational findings log (FR-META-1)

The framework records its own defects as structured findings:

- Middleware table `findings(id, ts, source, kind, requirementId, detail,
  status)`; auto-writers already exist in spirit - wire them: protocol
  validation failures (MP-02), seq gaps + unknown-participant flags
  (MP-04), recipe requires-failures (MP-07), gate blocks (MP-02), plus
  `POST /findings` for the facilitator's manual friction notes during
  MP-08.
- Dashboard: findings feed appears as task-board cards (MP-06 already
  derives cards from integrity warnings - extend to all finding kinds).

## Part C - Retrospective (FR-META-2): the framework improves itself

`analysis retrospective --study <id>` after a study:

1. Collects: the findings log, setup-time entries, requires-check history,
   and the facilitator's `findings.md` from MP-08.
2. Claude (current API docs; D10 bounds - aggregates and findings
   only, no participant rows) drafts a **changelist proposal**:
   `retrospective/<date>-proposal.md` with sections *SRS amendments*
   (per requirement ID: keep/amend/add, with evidence citations into the
   findings log), *protocol-schema changes*, *instrument config changes*,
   and *explicitly rejected ideas* (with why).
3. **Human gate:** the proposal is inert until the researcher reviews it
   and applies accepted items as ordinary edits to `requirements/srs.md` +
   `requirements/traceability.md` (change-managed like any requirement
   change - new IDs, supersessions, log entry). The framework never edits
   its own requirements unattended; "self-evolving" means *self-proposing*.
4. Offline-degradable: without an API key, emit the collected evidence
   bundle and a template so the researcher writes the proposal manually.

## Acceptance criteria

- Over the seeded demo study: `analysis paper` produces a compilable
  `draft.tex` (run `pdflatex` to prove it) whose methods section contains
  the demo protocol's real probe intervals and metric definitions, and
  whose results section embeds real recipe figures per RQ.
- Golden-file test green; regenerating produces an identical draft.
- Injecting a fake seq gap + a failed requires-check yields two findings
  rows, two task-board cards, and both cited as evidence in the
  retrospective proposal.
- The retrospective proposal contains zero participant-row data (grep the
  prompt-construction layer's output in tests, same pattern as FR-ETH-4).

## Verification

- pytest green; full demo run of paper + retrospective; open the PDF.
  Update `docs/archive/roadmap/00-VISION.md` tracker + `requirements/traceability.md`
  (FR-ANA-6, FR-META-1/2 → ✅).
