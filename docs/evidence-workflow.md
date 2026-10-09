# Evidence-linked methods

In **Setup → Method evidence**, import a JSON document conforming to the
[evidence contract](evidence-mapping.md). Versions are immutable and scoped to
the study. Reimporting the active version is idempotent; changed content needs
a new `mapVersion`.

Enter the question, population, task, construct, and available producers and
instruments. Compare methods, expand a source, inspect its exact passage and
location, and confirm its applicability context. A curator's review is not the
researcher's context confirmation; both are retained separately.

Candidates distinguish compatible, conditional, incompatible and insufficient
evidence. Query overlap only orders discovery: reported method use, popularity
and extraction confidence cannot supply methodological support. Unknown facts,
conflicting reviewed guidance, different contexts, missing producers,
unsupported recipes and missing recipe inputs remain visible. Context labels
must match exactly; this conservative baseline does not infer transferability.

Changing constraints invalidates the visible comparison and source confirmations.
Failed or late requests cannot display stale eligible choices. Existing accepted
decisions remain intact; reassess them explicitly when constraints change.

## From evidence to protocol

“Review this choice in chat” creates a proposal, not an approval. Accept, reject
or undo it using the existing controls. A design change needs an exact draft
research-question match and explicit mapped analysis recipes. Accepting that
choice changes its design and targeted analysis together; unrelated questions
and other accepted details remain intact. Undo replays the prior choices.

The normal compiler, stale-compilation checks and researcher approval still
govern applying the protocol. The evidence snapshot retains the map digest and
version, sources, passages, review status, context, assumptions, constraints and
required measurement inputs. Decision labels/timestamps and approval records
are exported with it. A declared producer is not proof that its runner is set
up, consented, or producing data: check Plan and rehearse actual capture.

The elicitation JSON includes `evidenceMaps`. The data bundle includes
`files/evidence-maps.json` and `files/design-decisions.json`. Replication kits for
mapped studies include `design-evidence.json`. Protocol schema compatibility is
preserved: provenance travels as sidecar artifacts, not extra protocol fields.

## Rehearse without inventing research results

Import `protocol/examples/evidence-workflow-demo.json` into a separate synthetic
study. It clearly labels its invented studies, passages and simulated reviewers.
Use its labels: `Novice Python developers`, `Fix a Python bug`, `completion-time`;
declare `task-harness` as producer and instrument. The required `task_outcome`
events are **not** interchangeable with session timer telemetry. Arrange and
verify the external task harness before attempting data collection.

```bash
npm --prefix platform run check
```

The rehearsal creates synthetic studies only on a loopback target. It checks
chat, invalid imports, source inspection, constraint changes, failure recovery,
keyboard approval, desktop/mobile accessibility and exported evidence.
It cleans up only its newly created project, even on failure. Set
`REHEARSAL_KEEP=1` to retain that synthetic presentation fixture explicitly.

This delivers a software slice of #92–94, not completion of #89. The independently
reviewed 20–30-study map, third design-family execution, expert benchmark,
classifier experiments, comparative evaluation, and human usability pilot
remain open. Importing a document preserves its declared review status; it does
not authenticate the reviewer or establish the truth of its claims.
