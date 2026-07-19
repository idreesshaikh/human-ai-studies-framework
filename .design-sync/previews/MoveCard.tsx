import { MoveCard } from "platform";

// MoveCard is the signature interaction: a platform-proposed design move the
// researcher accepts (a/A) or rejects (r). Props ported from the deterministic
// design assistant (lib/designStub.ts) so the content is real, grounded copy.
const noop = () => {};

const grounded = {
  moveId: "move-1",
  kind: "add-measure" as const,
  target: "measures[]",
  proposal:
    "Measure whether developers review AI-generated code before accepting it — a code-verification outcome, not a felt one.",
  grounding: [
    {
      ref: "corpus:trust-in-ai-code-generation",
      tier: "A" as const,
      title: "Trust in AI Code Generation",
      year: 2024,
      venue: "corpus (Tier A seed)",
      why: "Documents over-reliance on AI-generated code — motivates a trust/verification measure.",
    },
  ],
  status: "proposed" as const,
};

const unsourced = {
  moveId: "move-2",
  kind: "set-parameter" as const,
  target: "participants",
  proposal: "Recruit 12 developers, within-subjects with counterbalancing.",
  grounding: [],
  status: "proposed" as const,
};

const caution = {
  moveId: "move-3",
  kind: "caution" as const,
  target: "measures[]",
  proposal:
    "Self-reported speed alone is unsafe: in the METR RCT developers felt 20% faster while measurably 19% slower.",
  grounding: [
    {
      ref: "corpus:metr-early-2025-dev-productivity",
      tier: "A" as const,
      title: "Measuring the Impact of Early-2025 AI on Developer Productivity",
      year: 2025,
      venue: "corpus (Tier A seed)",
      why: "The perception gap that makes self-report alone unsafe.",
    },
  ],
  status: "proposed" as const,
};

const accepted = { ...grounded, moveId: "move-4", status: "accepted" as const };

export function Grounded() {
  return <MoveCard move={grounded} onDecide={noop} />;
}

export function Unsourced() {
  return <MoveCard move={unsourced} onDecide={noop} />;
}

export function Caution() {
  return <MoveCard move={caution} onDecide={noop} />;
}

export function Accepted() {
  return <MoveCard move={accepted} onDecide={noop} />;
}
