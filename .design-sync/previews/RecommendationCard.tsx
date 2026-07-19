import { RecommendationCard } from "platform";

// A paper matched to the researcher's idea. Match reason is one sentence,
// always shown in full. Adding it joins the paper to the study set. Content
// ported from the over-trust recommendation script (designStub).
const noop = () => {};

const trust = {
  ref: "corpus:trust-in-ai-code-generation",
  tier: "A" as const,
  title: "Trust in AI Code Generation",
  year: 2024,
  venue: "corpus (Tier A seed)",
  matchReason:
    "Directly studies over-reliance on AI-generated code — your exact construct.",
};

const insecure = {
  ref: "corpus:insecure-code-with-ai-assistants",
  tier: "A" as const,
  title: "Do Users Write More Insecure Code with AI Assistants?",
  year: 2023,
  venue: "corpus (Tier A seed)",
  matchReason:
    "Shows accepted AI code carries defects users miss — grounds the correctness outcome.",
};

export function NotAdded() {
  return (
    <div style={{ maxWidth: 320 }}>
      <RecommendationCard rec={trust} added={false} onAdd={noop} />
    </div>
  );
}

export function Added() {
  return (
    <div style={{ maxWidth: 320 }}>
      <RecommendationCard rec={insecure} added={true} onAdd={noop} />
    </div>
  );
}
