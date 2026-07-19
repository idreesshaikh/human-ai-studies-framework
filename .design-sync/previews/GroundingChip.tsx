import { GroundingChip } from "platform";

// Citation chips: tier badge + paper title. Hover/focus reveals year, venue,
// and the "why this source" line. Content ported from the corpus (designStub).
const trust = {
  ref: "corpus:trust-in-ai-code-generation",
  tier: "A" as const,
  title: "Trust in AI Code Generation",
  year: 2024,
  venue: "corpus (Tier A seed)",
  why: "Documents over-reliance on AI-generated code — directly motivates a trust/verification measure.",
};

const guidelines = {
  ref: "corpus:guidelines-empirical-llm-se",
  tier: "B" as const,
  title: "Guidelines for Empirical Studies of LLMs in SE",
  year: 2024,
  venue: "corpus (Tier B harvest)",
  why: "The methodological floor: within-subjects + counterbalancing for small-N developer studies.",
};

const studyTemplate = {
  ref: "template:within-subjects-counterbalanced",
  tier: "study" as const,
  title: "Within-subjects, counterbalanced task order",
  year: 2026,
  venue: "in this study",
  why: "The design template this study adopted — prescribes the paired non-parametric plan.",
};

export function Chips() {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
      <GroundingChip g={trust} />
      <GroundingChip g={guidelines} />
      <GroundingChip g={studyTemplate} />
    </div>
  );
}
