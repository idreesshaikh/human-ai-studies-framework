# Design conversation

The design conversation is the platform’s methodologist at the edge of the
desk. You describe what you want to learn; PHOENIX asks what must be true for
the answer to be interpretable, then proposes one decision at a time.

<figure markdown="span">
  ![A current Phoenix design conversation](../assets/screens/phoenix-demo-conversation-current.png){ width="900" }
  <figcaption>Every move is reviewable, reversible, and connected to the protocol draft.</figcaption>
</figure>

## A move, not a magic answer

1. **Describe the question.** Start with the phenomenon, population, task, and
   comparison you care about.
2. **Inspect the proposal.** A move might choose a within-subjects design,
   define a measure, add a condition, or set a participant-count rule.
3. **Check the evidence.** Each citation chip points back to the literature
   corpus with a confidence score. If no source supports the move, the UI says
   **unsourced**.
4. **Accept or reject.** Accepted moves compile into the protocol draft;
   rejected moves leave no hidden configuration behind.

The point is not to outsource judgement. The point is to make judgement
explicit, evidenced, and easy to audit later.

## Grounding is a type, not a tone

Every proposal is exactly one of:

- **Cited** — backed by papers in the corpus, with the supporting literature
  visible in the move card.
- **Unsourced** — a useful possibility that has no supporting paper in the
  available corpus and must not be mistaken for evidence.

There is no third state. Clicking a citation opens the paper in the study’s
Library, where the researcher can inspect its place in the constellation.

## Steering the assistant

The **Steer** control adjusts how assertively the assistant drives the next turn.
High steer proposes more aggressively; low steer asks more and presumes less.
It changes the next response, not the protocol already accepted.

## What the assistant will not do

- Fabricate a citation or imply that an unsourced move is literature-backed.
- Silently rewrite an accepted protocol decision.
- Present demo or synthetic data as a result.
- Replace the researcher’s ethics review, preregistration, or final analysis.

The [protocol draft](protocol-draft.md) is the document of record; the
conversation is the trace of how it became that way.
