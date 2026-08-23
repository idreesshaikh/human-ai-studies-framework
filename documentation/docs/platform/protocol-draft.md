# Protocol draft

The protocol draft is where a conversation becomes a study. It compiles from
the design moves you accepted and stays visible while the next decision is
being made.

<figure markdown="span">
  ![The current protocol rail](../assets/screens/phoenix-demo-conversation-current.png){ width="900" }
<figcaption>The draft rail shows coverage, missing sections, and the exact choices that will drive the run.</figcaption>
</figure>

## What the rail shows

The rail keeps the method legible while the conversation stays focused. Its
eight researcher-controlled sections are research questions, design,
participants, conditions, measures, instruments, statistical plan, and ethics.
Study identity and schema-required administrative fields remain available in
the study header and the raw YAML; they do not inflate the visible progress
meter.

The rail always answers three questions:

1. What decisions are already in the draft?
2. What is the next missing decision?
3. Is the compiled protocol valid enough to apply?

Only the active decision is expanded in the conversation. Earlier decisions,
warnings, and raw YAML are disclosures so they remain inspectable without
becoming a wall of repeated text.

## The document of record

The conversation explains the reasoning; the compiled protocol defines the
study. Only the protocol drives:

- the conditions and counterbalanced task order;
- the measures and instrument legs;
- the consent statement shown before pairing;
- TERN’s approved capture configuration;
- the analysis plan and its validation rules.

That is how the framework keeps the thesis coherent: the artifact designed by
the researcher is the artifact the participant runs.

## What compilation means

- **Deterministic.** Accepted choices compile through the protocol schema into a
  versioned document. No LLM is involved in compilation.
- **Diffed.** Changes are visible against the previous version before approval.
- **Validated.** Missing conditions, measures, or participant-count rules are
  named instead of being silently defaulted.
- **Human-approved.** A draft is not a study run until the researcher approves
  the change.

The browser projection and server compiler are intentionally separate. The
client compiler gives instant feedback while a card is accepted; the server
compile is authoritative and blocks **Apply to protocol** when validation fails.
Both compilers must understand the same move shapes. In particular,
`prescribe-statistics` stores an executable recipe identifier, not a paragraph
of statistical advice.

Older saved conversations are recovered where possible. The former
`taskTimer` name maps to the registered TERN capture instrument with a visible
warning. Recognizable legacy statistical-plan sentences map to a runnable
recipe. Unknown values remain warnings or errors and are never presented as a
valid protocol.

## Consent and responsibility

PHOENIX does not grant ethics approval. It makes the capture decision explicit:
the participant sees the protocol-derived consent statement, and TERN applies
the approved configuration for that run. The researcher remains responsible for
institutional review and for deciding when an amendment requires a new review.

## Proven shapes and novel protocols

The [Library](library.md) ranks proven design shapes by corpus usage. Each shape
binds the statistical plan it requires. Merging shapes produces a new protocol
grounded in the papers attached to the chosen moves.
