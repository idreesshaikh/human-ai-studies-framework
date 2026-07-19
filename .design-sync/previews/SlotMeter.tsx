import { SlotMeter } from "platform";
import type { ProtocolDraft } from "platform";

// Protocol completeness as a row of dots, one per required section. Dots light
// as sections fill; still-empty sections are named explicitly. Drafts ported
// from the over-trust flow (designStub moves compile into these slots).
const partial: ProtocolDraft = {
  researchQuestions: [
    "Do junior developers accept AI-generated code with less review than seniors?",
  ],
  design: [],
  participants: [],
  conditions: ["Experience level: junior vs. senior"],
  measures: [
    "Review latency (suggestion-visible-to-decision time)",
    "Code-correctness outcome (acceptance-test pass rate)",
  ],
  instruments: [],
  statisticalPlan: [],
  ethics: [],
};

const complete: ProtocolDraft = {
  researchQuestions: [
    "Do junior developers accept AI-generated code with less review than seniors?",
  ],
  design: ["Within-subjects, counterbalanced task order"],
  participants: ["12 developers (6 junior, 6 senior), recruited via meetups"],
  conditions: ["Experience level: junior vs. senior"],
  measures: [
    "Review latency (suggestion-visible-to-decision time)",
    "Code-correctness outcome (acceptance-test pass rate)",
  ],
  instruments: ["Cognitive Overlay (IDE telemetry)", "agentCapture"],
  statisticalPlan: [
    "Wilcoxon signed-rank (exact) + rank-biserial effect size; small-N = hypothesis-generating",
  ],
  ethics: ["Informed consent; content policy metadata-only; approved v1"],
};

export function Partial() {
  return (
    <div style={{ maxWidth: 360 }}>
      <SlotMeter draft={partial} />
    </div>
  );
}

export function Complete() {
  return (
    <div style={{ maxWidth: 360 }}>
      <SlotMeter draft={complete} />
    </div>
  );
}
