# Design chat

The design chat on **Setup** turns a plain description of your study into
protocol decisions. You describe what you want to learn; it asks what must be
true for the answer to mean something, and proposes decisions as cards you
accept or reject. Accepted cards build the [protocol draft](protocol-draft.md).

<figure markdown="span">
  ![The Setup tab with the chat box and the protocol draft panel open on the right](../assets/screens/setup-light.webp#only-light)
  ![The Setup tab with the chat box and the protocol draft panel open on the right](../assets/screens/setup-dark.webp#only-dark)
  <figcaption>Setup, with the protocol draft open beside the chat. The chat stays off until a model is connected.</figcaption>
</figure>

The chat needs a model; see the settings in
[Run PHOENIX yourself](index.md#your-own-server). Without one, it says that no
language model is connected, and templates, direct entry and everything after
Setup still work. It supports studies of coding tasks, not exams, classrooms or
surveys.

## Ways to start

- **Describe your question** in the chat box: the behaviour, the people, the
  task, and the comparison you care about.
- **Start from details or an example**, then:
    - **Add known details** to fill in what you already know, then
      **Add to chat**;
    - **Try an example** to start from a sample question;
    - **Enter the protocol details directly** to skip the chat. See
      [Entering a design directly](protocol-draft.md#entering-a-design-directly).

## Cards

Each reply is a few sentences and up to five cards. When you give several facts
at once, the chat makes one card per fact, up to eight, and offers
**Accept all**. A card is one of three things:

- **A protocol change**, such as a within-subjects design, a measure, a
  condition, or a rule for how many participants to recruit.
- **An analysis recipe** that the analysis code can run, such as
  `paired-nonparametric`. A paragraph of advice is not an analysis plan.
- **A caution** about a risk in the design. **Note it** records that you saw it.

Accepted cards go into the draft; rejected cards leave nothing behind. **Undo**
reverses a decision. The chat keeps a short memory of recent messages and reads
the accepted decisions from the draft, so it does not propose them again.

## Where a card's evidence comes from

Each card shows its basis:

| Label | Meaning |
| --- | --- |
| **grounded** | Backed by papers in the corpus. Hover for the title, venue, confidence and the reason it applies |
| **Evidence and conditions** | Backed by an evidence map you imported, with its version |
| **No source: your call** | No paper in the corpus supports it. It may still be right, but it is your judgement, not evidence |

The chat never presents an unsourced card as backed by literature.

## Assistant style

The **Assistant style** control sets how the chat behaves from the next reply
on. It never changes decisions you already accepted.

- **Drafts the plan** (the default) turns what you say into cards.
- **Answers only** answers questions and flags risks, and never changes the
  draft.

## More tools

- The panel on the right switches between **Protocol draft** and
  **Literature**. Literature suggests papers; **Add to study** adds one to
  [Evidence](library.md).
- **Research tools** (**⋯**) opens **Method evidence**, where you can import an
  evidence map, compare methods and send a choice back to the chat for review.
  It also offers **Enter protocol manually**.

## What the chat will not do

- Invent a citation, or present an unsourced card as backed by literature.
- Change a decision you accepted without your say.
- Present synthetic or demo data as a result.
- Replace your ethics review, preregistration or final analysis.
