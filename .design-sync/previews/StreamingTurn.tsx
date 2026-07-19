import { StreamingTurn } from "platform";
import type { Turn } from "platform";

// A single conversation turn: the prose, then any design moves and paper
// recommendations it carries. Platform turns sit left; researcher turns right.
// Content ported from the over-trust script (designStub).
const noop = () => {};
const noAdd = () => {};

const platformTurn: Turn = {
  turnId: "turn-2",
  role: "platform",
  author: "Platform",
  text: "Good starting point. “Over-trust” is a claim about how developers review AI code before accepting it — measurable, not just felt. Here are moves that turn it into a study, each grounded. Two papers in the corpus match closely.",
  moves: [
    {
      moveId: "move-1",
      kind: "add-measure",
      target: "measures[]",
      proposal:
        "Measure: review latency — time an AI suggestion is visible before accept/reject.",
      patch: {
        section: "measures",
        op: "append",
        value: "Review latency (suggestion-visible-to-decision time)",
      },
      grounding: [
        {
          ref: "corpus:trust-in-ai-code-generation",
          tier: "A",
          title: "Trust in AI Code Generation",
          year: 2024,
          venue: "corpus (Tier A seed)",
          why: "Documents over-reliance on AI-generated code — motivates a trust/verification measure.",
        },
      ],
      status: "proposed",
    },
  ],
  recommendations: [
    {
      ref: "corpus:trust-in-ai-code-generation",
      tier: "A",
      title: "Trust in AI Code Generation",
      year: 2024,
      venue: "corpus (Tier A seed)",
      matchReason:
        "Directly studies over-reliance on AI-generated code — your exact construct.",
    },
  ],
};

const researcherTurn: Turn = {
  turnId: "r-1",
  role: "researcher",
  author: "You",
  text: "I think junior developers over-trust AI-generated code.",
  moves: [],
  recommendations: [],
};

export function PlatformTurn() {
  return (
    <div style={{ maxWidth: 560 }}>
      <StreamingTurn
        turn={platformTurn}
        addedRefs={new Set<string>()}
        onDecide={noop}
        onAddPaper={noAdd}
      />
    </div>
  );
}

export function ResearcherTurn() {
  return (
    <div style={{ maxWidth: 560 }}>
      <StreamingTurn
        turn={researcherTurn}
        addedRefs={new Set<string>()}
        onDecide={noop}
        onAddPaper={noAdd}
        feedback={{ suggested: false, marked: false, onMark: () => {} }}
      />
    </div>
  );
}
