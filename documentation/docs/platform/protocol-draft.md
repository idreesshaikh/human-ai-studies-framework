# Protocol draft

The protocol draft is the study as it will run. It builds up from the cards you
accept in the [design chat](design-conversation.md), or from the details you
enter directly, and stays open beside the chat on **Setup**.

## What the draft shows

The panel lists eight sections: research questions, design, participants,
conditions, measures, instruments, statistical plan, and ethics. Ethics is
optional, so the progress count covers the other seven. **What are these
sections?** explains each one, and **Edit details** opens the form described
below. The study name and the administrative fields the schema requires are in
the study header and the raw YAML, not in the count.

At any moment the draft answers three questions:

1. Which decisions are in it?
2. Which decision is missing next?
3. Is it valid enough to apply?

## Review and apply

**Review draft** opens the full compiled protocol before anything changes. It
marks which decisions are backed by papers and which are your call, shows the
YAML, and highlights what changed since the protocol you last applied.

<figure markdown="span">
  ![The Review draft dialog listing the decisions to apply, with Keep editing and Apply protocol buttons](../assets/screens/review-draft-light.webp#only-light)
  ![The Review draft dialog listing the decisions to apply, with Keep editing and Apply protocol buttons](../assets/screens/review-draft-dark.webp#only-dark)
  <figcaption>Review draft, before Apply protocol. Applying records who approved which compilation.</figcaption>
</figure>

Choose **Keep editing** to go back, or **Apply protocol** to make this version
the study's protocol. PHOENIX records the approval, and the next step,
**Plan recruitment**, appears.

Only the applied protocol reaches participants. It sets:

- the conditions and the order each participant meets them in;
- the measures and the instruments that capture them;
- the consent statement TERN shows when a participant connects;
- TERN's capture settings;
- the analysis plan and the checks it must pass.

## How compiling works

- **No model involved.** The protocol compiler turns accepted decisions into a
  versioned YAML document the same way every time.
- **Checked.** Missing conditions, measures or participant-count rules are named
  as errors, never filled in with defaults.
- **Two compilers, one authority.** Your browser shows the result of each card
  at once. The server then compiles again, and its result decides: if it finds
  an error, **Apply protocol** stays blocked.

Older saved conversations are recovered where possible. The former `taskTimer`
name maps to TERN's capture instrument with a visible warning, and recognisable
old statistical-plan sentences map to a runnable recipe. Anything else stays a
warning or an error.

## Entering a design directly

If you already have a design, skip the chat. **Enter the protocol details
directly** on a new study, or **Edit details** on the draft, opens a form with
the study name, up to six research questions, the design, two conditions, the
participants, the task, the session length, and the outcomes. It starts from the
current draft.

Saving records your entry as accepted decisions that replace the earlier ones,
and keeps the analysis recipes of research questions you did not change. The
same compiler checks it, and **Apply protocol** approves it. The chat stays
available, and cards accepted afterwards refine your entry.

## Consent and responsibility

PHOENIX does not grant ethics approval. It makes the capture decision explicit:
the participant sees the consent statement written from the protocol, and TERN
applies the protocol's capture settings. You remain responsible for review by
your institution, and for deciding when a change to the protocol needs a new
review. TERN applies a newly applied protocol at each participant's next
session without asking for consent again.

## Templates

**Templates**, in the sidebar, ranks study designs by how often published
studies in the corpus use them. Each template includes the statistical plan it
needs.
