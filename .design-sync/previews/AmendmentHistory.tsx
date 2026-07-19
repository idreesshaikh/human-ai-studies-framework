import { AmendmentHistory } from "platform";
import type { Amendment } from "platform";

// The amendment history: a quiet vertical list of post-ethics changes —
// version chips, plain-language summaries, and the consent register. Data
// ported verbatim from a demo study mid-evolution
// (evolutionStub): one resolved consent-relevant amendment, one calm config
// tweak, one consent-relevant amendment awaiting re-approval.
const amendments: Amendment[] = [
  {
    id: "am-1",
    fromVersion: 1,
    toVersion: 2,
    summary: "adds instrument: agentCapture",
    changes: ["adds instrument: agentCapture"],
    rationale:
      "The pilot showed the agent's tool calls explain comprehension gaps the IDE telemetry alone missed.",
    grounding: ["corpus:guidelines-empirical-llm-se"],
    consentRelevant: true,
    consentReasons: ["adds a new data stream: instruments.agentCapture"],
    approvedBy: "You",
    reapprovalArtifact: "ethics-approval-v2.pdf",
    at: "2026-07-14T10:12:00.000Z",
  },
  {
    id: "am-2",
    fromVersion: 2,
    toVersion: 3,
    summary: "reconfigures instrument: cognitiveOverlay",
    changes: ["reconfigures instrument: cognitiveOverlay"],
    rationale:
      "Raise the stuck-detector threshold to two minutes — participants were being nudged mid-thought.",
    grounding: [],
    consentRelevant: false,
    consentReasons: [],
    approvedBy: "You",
    reapprovalArtifact: null,
    at: "2026-07-15T14:30:00.000Z",
  },
  {
    id: "am-3",
    fromVersion: 3,
    toVersion: 4,
    summary: "changes the content policy of instruments.agentCapture",
    changes: ["reconfigures instrument: agentCapture"],
    rationale:
      "Capture the full agent conversation, not just metadata, to study how phrasing shifts comprehension.",
    grounding: ["corpus:guidelines-empirical-llm-se"],
    consentRelevant: true,
    consentReasons: [
      "changes the content policy of instruments.agentCapture (contentPolicy: 'metadata-only' → 'full-content')",
    ],
    approvedBy: "You",
    reapprovalArtifact: null,
    at: "2026-07-17T09:05:00.000Z",
  },
];

export function History() {
  return (
    <div style={{ maxWidth: 640 }}>
      <AmendmentHistory amendments={amendments} />
    </div>
  );
}
