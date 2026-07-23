/* The conversation domain model. These shapes match the server interfaces
 * so wiring the backend later is a transport swap, not a redesign. */

export type Tier = "A" | "B" | "study";

/** Citations attached to a design move. A move with no grounding is shown
 * as "unsourced". */
export interface Grounding {
  ref: string; // corpus ref, e.g. "arxiv:2506.xxxxx", or template id
  tier: Tier;
  confidence?: number; // 0..1 continuous quality signal — the primary rank, not the tier
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
  /** Which path produced a platform turn (FR-CONV-1.4) — "llm" when a
   * provider is configured and healthy, "scripted" on the degraded
   * no-key/fallback path. Absent for researcher turns. */
  source?: "llm" | "scripted";
}

/** A paper matched to the researcher's idea. */
export interface Recommendation {
  ref: string;
  tier: Tier;
  confidence?: number; // 0..1 continuous quality signal
  title: string;
  year: number;
  venue: string;
  matchReason: string; // one sentence, always visible, never truncated
}

/* The protocol draft (client-side model). The real document of record is
 * the YAML the compiler emits; this is the in-progress projection the slot
 * meter and draft rail read from. */

/** The generic section patch — the shape ``add-rq``/``add-measure``/
 * ``set-parameter`` moves carry. */
export interface SectionPatch {
  section: keyof ProtocolDraft;
  /** append to a list section, or set a scalar/keyed section. */
  op: "append" | "set";
  key?: string;
  value: string;
}

/** A ``choose-template`` move's patch — the *only* thing that can fill the
 * draft's mandatory `design` slot (server: design_llm.py). */
export interface TemplatePatch {
  templateId: string;
  parameters?: Record<string, unknown>;
}

/** An ``add-instrument``/``reconfigure-instrument`` move's patch. */
export interface InstrumentPatch {
  section: "instruments";
  op: "add-instrument" | "set-instrument" | "reconfigure";
  name: string;
  config?: Record<string, unknown>;
  path?: string[];
  value?: unknown;
}

export type DraftPatch = SectionPatch | TemplatePatch | InstrumentPatch;

export function isSectionPatch(p: DraftPatch): p is SectionPatch {
  return "op" in p && (p.op === "append" || p.op === "set");
}

export function isTemplatePatch(p: DraftPatch): p is TemplatePatch {
  return "templateId" in p;
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

/* ---------------------------------------------- evolution (FR-CONV-4/5)
 *
 * The study evolves through phase-aware amendments; the platform evolves from
 * feedback. These shapes mirror the server JSON (middleware app.py) so wiring
 * the transport later is a swap, not a redesign — exactly as the conversation
 * shapes above do. */

/** One post-ethics protocol change: a version bump plus the record the ethics
 * board relies on. `consentRelevant` is the deterministic rule's verdict (never
 * an LLM judgment); a relevant amendment pauses new sessions until re-approval. */
export interface Amendment {
  id: string;
  fromVersion: number;
  toVersion: number;
  summary: string;
  changes: string[]; // plain-language "what changed" lines
  rationale: string;
  grounding: string[]; // citation refs, or [] for unsourced
  consentRelevant: boolean;
  consentReasons: string[]; // why the rule fired, verbatim
  approvedBy: string;
  reapprovalArtifact: string | null; // set once the ethics re-approval lands
  at: string;
}

/** A study's amendment lifecycle: which revision it's on, whether ethics is
 * approved, and whether new sessions are paused awaiting re-approval. */
export interface AmendmentState {
  studyId: string;
  currentVersion: number;
  ethicsApprovedAt: string; // "" before ethics approval (ordinary compiles)
  pendingReapproval: string; // amendment id awaiting re-approval, or ""
  amendments: Amendment[];
}

/** Platform feedback marked in a conversation, filed as a finding. The locus
 * points back at the exact turn; resolving it needs project membership (the
 * boundary holds even for meta-data). */
export interface PlatformFinding {
  id: number; // the server's integer finding id (FR-META-1 pipeline)
  at: string;
  note: string;
  status: "open" | "resolved";
  locus: {
    studyId: string;
    turnId: string;
    seq: number;
    kind: string; // ux-defect | template-gap | unclassified | …
  };
}

/** The inert retrospective proposal drafted from feedback + shapes. It cites
 * the findings rows it used; a human approves it — nothing self-applies. */
export interface RetrospectiveProposal {
  status: "draft";
  title: string;
  generatedFrom: { feedbackFindings: number; shapeRows: number };
  citedFindingIds: number[];
  items: {
    title: string;
    kind: "ux-defect" | "template-improvement" | "new-template";
    evidence: Record<string, unknown>;
  }[];
}
