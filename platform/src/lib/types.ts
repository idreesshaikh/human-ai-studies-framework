/* The conversation domain model. These shapes match the server interfaces
 * so wiring the backend later is a transport swap, not a redesign. */

export type Tier = "A" | "B" | "study";

/** Citations attached to a design move. A move with no grounding is shown
 * as "unsourced". */
export interface Grounding {
  ref: string; // corpus ref, e.g. "arxiv:2506.xxxxx", or template id
  tier: Tier;
  title: string;
  year?: number;
  venue?: string;
  why: string; // "why this source" — shown on hover (GroundingChip)
}

/** One platform-proposed change to the protocol draft. */
export type MoveKind =
  | "add-rq"
  | "choose-template"
  | "set-parameter"
  | "add-instrument"
  | "add-measure"
  | "set-threshold"
  | "caution"; // a challenge to a choice — no draft change, just advice

export type MoveStatus = "proposed" | "accepted" | "rejected";

export interface DesignMove {
  moveId: string;
  kind: MoveKind;
  target: string; // protocol slot this move fills, e.g. "researchQuestions[]"
  proposal: string; // human-readable one-liner
  /** The change this move makes to the draft — a plain patch the compiler
   * applies. Caution moves carry none. */
  patch?: DraftPatch;
  grounding: Grounding[];
  status: MoveStatus;
}

/** A conversation turn. Platform turns may carry design moves and paper
 * recommendations. */
export interface Turn {
  turnId: string;
  role: "researcher" | "platform";
  author: string; // who contributed the turn
  text: string;
  moves: DesignMove[];
  recommendations: Recommendation[];
}

/** A paper matched to the researcher's idea. */
export interface Recommendation {
  ref: string;
  tier: Tier;
  title: string;
  year: number;
  venue: string;
  matchReason: string; // one sentence, always visible, never truncated
}

/* The protocol draft (client-side model). The real document of record is
 * the YAML the compiler emits; this is the in-progress projection the slot
 * meter and draft rail read from. */

export interface DraftPatch {
  section: keyof ProtocolDraft;
  /** append to a list section, or set a scalar/keyed section. */
  op: "append" | "set";
  key?: string;
  value: string;
}

export interface ProtocolDraft {
  researchQuestions: string[];
  design: string[];
  participants: string[];
  conditions: string[];
  measures: string[];
  instruments: string[];
  statisticalPlan: string[];
  ethics: string[];
}

/** The sections a protocol must fill — drives the slot meter and the
 * "here's what's still unresolved" prompts. */
export const MANDATORY_SLOTS: (keyof ProtocolDraft)[] = [
  "researchQuestions",
  "design",
  "participants",
  "conditions",
  "measures",
  "instruments",
  "statisticalPlan",
  "ethics",
];

export const SLOT_LABELS: Record<keyof ProtocolDraft, string> = {
  researchQuestions: "Research questions",
  design: "Design",
  participants: "Participants",
  conditions: "Conditions",
  measures: "Measures",
  instruments: "Instruments",
  statisticalPlan: "Statistical plan",
  ethics: "Ethics posture",
};

export function emptyDraft(): ProtocolDraft {
  return {
    researchQuestions: [],
    design: [],
    participants: [],
    conditions: [],
    measures: [],
    instruments: [],
    statisticalPlan: [],
    ethics: [],
  };
}
