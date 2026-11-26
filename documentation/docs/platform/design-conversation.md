# Design conversation

The design conversation is a chat on the **Setup** tab where an assistant helps
you decide the study. It talks first: it answers your questions, lays out options
with their trade-offs, and asks about the decisions only you can make. It proposes
changes once you have settled those or handed them to it. Its proposals arrive as
cards that you review, and nothing reaches the protocol until you apply it.

The conversation needs a connected model; see
[Connect a model](../reference/model-providers.md). Without one the assistant
says that no language model is connected, and
[templates](templates.md), [direct entry](manual-entry.md) and every later tab
still work.

## How a conversation goes

1. **Say what you want to learn**, or ask a question about designing the study.
2. **Read the reply.** The assistant explains the options and what each one costs
   you, and asks one question at a time about a choice that is yours to make,
   such as who you can recruit or how long a session can run. The question appears
   as a card in the thread. When it has natural answers, they appear as buttons:
   choose one to send it, or type your own. A question that is still unanswered is
   asked again; the assistant never decides it for you.
3. **Review the cards** it proposes once you have settled those choices, or say
   "draft it" to let the assistant fill in the rest.
4. **Keep talking** until the draft covers the study, then
   [review and apply it](protocol-draft.md).

## Proposal cards

Each card changes one part of the study plan:

- design and conditions
- participants
- task and session length
- outcome measures
- research questions
- title

A card lists the proposed value of each field it changes and, under **Now**, the
accepted value it would replace, so you can see exactly what accepting it changes.
You **Accept** or **Reject** each card, or press ++a++, ++r++ or ++u++ (undo) on a
focused card, and these rules apply:

- **Accepted parts stay accepted.** The assistant does not propose them again
  unless you ask to change them.
- **A newer proposal replaces an older pending one** for the same part, so a part
  never has two competing cards.
- **Up to two decisions appear under the latest reply.** As you accept or
  reject them, the next decisions appear. When both visible cards reflect
  details you supplied, **Accept both** records those two together.
- **Values the assistant chose itself are marked** on the card under **Chosen by
  the assistant**, with its reason, so you can see which choices were not yours
  before you accept them. Each of those cards waits for its own decision.

Open **Assistant style** beside the message box and choose **Answers only**
when you want advice without cards.
The assistant then answers and flags risks and never changes the draft.

## Literature on the cards

Literature retrieved for a turn appears in the **Literature** view of the panel
beside the chat. When the local library has little on your topic, the turn also
searches Semantic Scholar for at most 2.5 seconds and adds what it finds to the
library. If Semantic Scholar is slow or unavailable, the turn goes ahead with the
local results. The search sends up to eight keywords taken from your messages,
not the messages themselves. Set `MIDDLEWARE_LIVE_SEARCH=0` to turn it off; see
[Configuration](../reference/configuration.md#server-settings).

A card cites a paper only when that paper was retrieved for the same turn, so
every citation can be found in the panel. A card with no citation has no paper
behind it; judge it on its reasoning. Add a paper to your study from the panel, or
from the [Literature tab](library.md).

## Nothing is applied until you apply it

Accepted cards update the **Protocol draft** panel, which is a compiled draft and
not yet the study's protocol. Choose **Review draft** to read the compiled
protocol and its changes, then **Apply protocol**. See
[Review and apply the protocol](protocol-draft.md).

The assistant does not replace your ethics review, preregistration or final
analysis, and it never presents synthetic data as a result.

## Next steps

- [Review and apply the protocol](protocol-draft.md)
- [Literature](library.md) to collect the papers behind your decisions
