import { DraftRail } from "platform";
import type { ProtocolDraft } from "platform";

// The draft rail: the protocol compiled so far from accepted moves, rendered
// YAML-ish with the slot meter on top. A realistic partially-filled protocol
// from the over-trust flow — some slots resolved, some still unresolved.
const draft: ProtocolDraft = {
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

export function PartialProtocol() {
  return (
    <div style={{ height: 560, width: 400 }}>
      <DraftRail draft={draft} />
    </div>
  );
}
