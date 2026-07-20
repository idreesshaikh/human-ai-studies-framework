import { useSyncExternalStore } from "react";
import type {
  Amendment,
  AmendmentState,
  PlatformFinding,
  RetrospectiveProposal,
} from "./types";

/* The evolution surfaces on a deterministic offline store.
 *
 * Mirrors the server exactly the way the conversation runs on `designStub.ts`:
 * the middleware endpoints (/ethics-approval, /conversation/approve amendment
 * routing, /reapproval, /platform/findings, /platform/retrospective) are built
 * and tested; this is the no-backend path so the amendment banner, the history
 * list, and the platform-findings lineage are explorable and gate-testable with
 * no server and no LLM key. The transport swap is a later slice — the shapes
 * here are the server's.
 *
 * The seed is a demo study mid-evolution: one resolved consent-relevant
 * amendment, one calm instrument tweak, and one consent-relevant amendment
 * currently awaiting re-approval — so the paused banner and both registers are
 * visible at once. */

const DEMO_STUDY = "sample-study-2026";

function seedAmendments(): Amendment[] {
  return [
    {
      id: "am-1",
      fromVersion: 1,
      toVersion: 2,
      summary: "adds instrument: agentCapture",
      changes: ["adds instrument: agentCapture"],
      rationale:
        "The pilot showed the agent's tool calls explain comprehension gaps " +
        "the IDE telemetry alone missed.",
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
        "Raise the stuck-detector threshold to two minutes — participants " +
        "were being nudged mid-thought.",
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
        "Capture the full agent conversation, not just metadata, to study " +
        "how phrasing shifts comprehension.",
      grounding: ["corpus:guidelines-empirical-llm-se"],
      consentRelevant: true,
      consentReasons: [
        "changes the content policy of instruments.agentCapture " +
          "(contentPolicy: 'metadata-only' → 'full-content')",
      ],
      approvedBy: "You",
      reapprovalArtifact: null,
      at: "2026-07-17T09:05:00.000Z",
    },
  ];
}

function seedFindings(): PlatformFinding[] {
  return [
    {
      id: 1,
      at: "2026-07-16T11:20:00.000Z",
      note: "The compile diff is hard to scan when many moves land at once.",
      status: "open",
      locus: {
        studyId: DEMO_STUDY,
        turnId: "t-8",
        seq: 8,
        kind: "ux-defect",
      },
    },
  ];
}

/** Derive the inert retrospective proposal from the findings — the same shape
 * the server's `evolution.draft_proposal` produces, so the offline surface and
 * the server agree. It cites the findings it used; a human approves it. */
export function deriveProposal(findings: PlatformFinding[]): RetrospectiveProposal {
  const byKind = new Map<string, PlatformFinding[]>();
  for (const f of findings) {
    const k = f.locus.kind || "unclassified";
    byKind.set(k, [...(byKind.get(k) ?? []), f]);
  }
  const items: RetrospectiveProposal["items"] = [];
  for (const kind of [...byKind.keys()].sort()) {
    const rows = byKind.get(kind)!;
    items.push({
      title: `Address feedback theme: ${kind}`,
      kind: "ux-defect",
      evidence: { findingIds: rows.map((r) => r.id).sort(), count: rows.length },
    });
  }
  return {
    status: "draft",
    title: "Platform retrospective (drafted)",
    generatedFrom: { feedbackFindings: findings.length, shapeRows: 0 },
    citedFindingIds: findings.map((f) => f.id).sort((a, b) => a - b),
    items,
  };
}

/* A tiny observable store, so a turn marked in the conversation shows up on the
 * platform-findings surface without prop-drilling across routes (the offline
 * analogue of the server's shared DB). */
class EvolutionStore {
  private amendmentState: AmendmentState;
  private findings: PlatformFinding[];
  private listeners = new Set<() => void>();
  private nextId: number;
  private snapshotCache: {
    amendmentState: AmendmentState;
    findings: PlatformFinding[];
    proposal: RetrospectiveProposal;
  };

  constructor() {
    const amendments = seedAmendments();
    const pending = amendments.find(
      (a) => a.consentRelevant && !a.reapprovalArtifact);
    this.amendmentState = {
      studyId: DEMO_STUDY,
      currentVersion: amendments[amendments.length - 1].toVersion,
      ethicsApprovedAt: "2026-07-12T09:00:00.000Z",
      pendingReapproval: pending?.id ?? "",
      amendments,
    };
    this.findings = seedFindings();
    this.nextId = 2;
    this.snapshotCache = this.build();
  }

  private build() {
    return {
      amendmentState: this.amendmentState,
      findings: this.findings,
      proposal: deriveProposal(this.findings),
    };
  }

  private emit() {
    this.snapshotCache = this.build();
    for (const l of this.listeners) l();
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = () => this.snapshotCache;

  /** Mark a conversation turn as platform feedback (FR-CONV-5.1). Confirmed by
   * the researcher, never auto-filed — this is the confirm step. */
  markFeedback(input: {
    studyId: string;
    turnId: string;
    seq: number;
    note: string;
    kind: string;
  }) {
    const finding: PlatformFinding = {
      id: this.nextId++,
      at: new Date().toISOString(),
      note: input.note || `Feedback marked on turn ${input.seq}`,
      status: "open",
      locus: {
        studyId: input.studyId,
        turnId: input.turnId,
        seq: input.seq,
        kind: input.kind || "unclassified",
      },
    };
    this.findings = [...this.findings, finding];
    this.emit();
    return finding;
  }

  /** Record the ethics re-approval that lifts a consent-relevant amendment's
   * session pause (FR-CONV-4.2, F4.1). */
  recordReapproval(artifact = "ethics-reapproval.pdf") {
    const id = this.amendmentState.pendingReapproval;
    if (!id) return;
    this.amendmentState = {
      ...this.amendmentState,
      pendingReapproval: "",
      amendments: this.amendmentState.amendments.map((a) =>
        a.id === id ? { ...a, reapprovalArtifact: artifact } : a),
    };
    this.emit();
  }
}

export const evolutionStore = new EvolutionStore();

/** Subscribe a component to the evolution store. */
export function useEvolution() {
  return useSyncExternalStore(
    evolutionStore.subscribe,
    evolutionStore.getSnapshot,
    evolutionStore.getSnapshot);
}
