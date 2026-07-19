import { AmendmentBanner } from "platform";
import type { AmendmentState, Amendment } from "platform";

// The amendment banner: a calm consent surface. States the study's revision
// plainly, and when a consent-relevant amendment awaits ethics re-approval it
// says new sessions are paused. Data ported from a demo study
// mid-evolution (evolutionStub).
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
];

const approved: AmendmentState = {
  studyId: "sample-study-2026",
  currentVersion: 2,
  ethicsApprovedAt: "2026-07-12T09:00:00.000Z",
  pendingReapproval: "",
  amendments,
};

const paused: AmendmentState = {
  studyId: "sample-study-2026",
  currentVersion: 4,
  ethicsApprovedAt: "2026-07-12T09:00:00.000Z",
  pendingReapproval: "am-3",
  amendments,
};

export function Approved() {
  return (
    <div style={{ maxWidth: 720 }}>
      <AmendmentBanner state={approved} />
    </div>
  );
}

export function Paused() {
  return (
    <div style={{ maxWidth: 720 }}>
      <AmendmentBanner state={paused} onRecordReapproval={() => {}} />
    </div>
  );
}
