import { useSyncExternalStore } from "react";
import type { Amendment, AmendmentState } from "./types";

/* The evolution surface runs on a deterministic offline store.
 *
 * Mirrors the server exactly the way the conversation runs on `designStub.ts`:
 * the middleware endpoints (/ethics-approval, /conversation/approve amendment
 * routing, /reapproval) are built and tested; this is the no-backend path so
 * the amendment banner and the history list are explorable and gate-testable
 * with no server and no LLM key. The transport swap is a later slice — the
 * shapes here are the server's.
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
        "Raise the stuck-detector threshold to two minutes: participants " +
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

/* A tiny observable store, so the amendment banner and history list update
 * without prop-drilling across routes (the offline analogue of the server's
 * shared DB). */
class EvolutionStore {
  private amendmentState: AmendmentState;
  private listeners = new Set<() => void>();
  private snapshotCache: {
    amendmentState: AmendmentState;
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
    this.snapshotCache = this.build();
  }

  private build() {
    return {
      amendmentState: this.amendmentState,
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
