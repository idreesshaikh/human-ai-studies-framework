/* Conversation types shared with the server's wire contract. */

/** Citations attached to a design move. A move with no grounding is shown
 * as "unsourced". Quality is the continuous `confidence` (0..1)  -  there is no
 * provenance tier. */
export interface Grounding {
  ref: string; // corpus ref, e.g. "arxiv:2506.xxxxx", or template id
  confidence?: number; // 0..1 continuous quality signal  -  the sole quality rank
  title: string;
  year?: number;
  venue?: string;
  why: string; // "why this source"  -  shown on hover (GroundingChip)
  evidence?: import("./evidenceApi").EvidenceSnapshot;
}

/** One platform-proposed change to the protocol draft. The chat proposes
 * ``set-plan`` cards (server: study_plan); the other kinds come from the
 * checklist, the method comparison and studies recorded before them. */
export type MoveKind =
  | "add-rq"
  | "choose-template"
  | "set-parameter"
  | "set-field"
  | "declare-task"
  | "add-instrument"
  | "reconfigure-instrument"
  | "add-measure"
  | "merge-templates"
  | "prescribe-statistics"
  | "set-plan" // a change to one part of the study plan (server: study_plan)
  | "caution"; // a challenge to a choice  -  no draft change, just advice

/** "superseded": a newer proposal for the same part of the plan replaced it. */
export type MoveStatus = "proposed" | "accepted" | "rejected" | "superseded";

export interface DesignMove {
  moveId: string;
  kind: MoveKind;
  target: string; // protocol slot this move fills, e.g. "researchQuestions[]"
  proposal: string; // human-readable one-liner
  /** The change this move makes to the draft  -  a plain patch the compiler
   * applies. Caution and merge-templates moves carry none. */
  patch?: DraftPatch;
  grounding: Grounding[];
  status: MoveStatus;
  /** On a study-plan card, the values the assistant chose itself. `[]` means
   * every value came from the researcher; absent means the card carries no
   * marks (older or non-plan cards), so nothing can be said either way. */
  suggested?: PlanSuggestion[];
  /** For merge-templates moves: the template IDs being merged and why */
  mergeData?: {
    templateIds: string[];
    reason: string; // why these shapes should be combined
  };
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
  /* Platform-turn origin. Only llm turns propose moves; unavailable, scripted, and scope turns are persisted without model proposals. Absent for researcher turns. */
  source?: "llm" | "scripted" | "unavailable" | "scope";
  /** What the assistant asked, with answer options the researcher can send. */
  questions?: TurnQuestion[];
}

export interface TurnQuestion {
  ask: string;
  options: string[];
}

/** What the platform understands about the study so far (FR-CONV-10), and
 *  therefore whether it is willing to name a design shape yet. Surfaced
 *  rather than hidden: a researcher should be able to see *why* no design has
 *  been proposed, and what would change that. */
export interface Understanding {
  facets: Record<string, boolean>;
  known: string[];
  missing: string[];
  missingLabels: string[];
  /** Every facet's label, keyed by facet id  -  including the ones already
   *  known. `missingLabels` covers only what is absent, which cannot name a
   *  completed step. */
  facetLabels?: Record<string, string>;
  readyForDesign: boolean;
  facetsNeeded: number;
  /** The question the conversation will ask next, or "" when every facet is
   *  known. Decided by the server (elicitation.next_question) and shown so
   *  the researcher can see what is coming, not only what is missing. */
  nextQuestion?: string;
}

/** A paper matched to the researcher's idea. */
export interface Recommendation {
  ref: string;
  confidence?: number; // 0..1 continuous quality signal
  matchKind?: "direct" | "adjacent";
  matchedTerms?: string[];
  inStudy?: boolean; // already in the researcher's library
  title: string;
  authors?: string[];
  year: number;
  venue: string;
  identifier?: string;
  abstract?: string;
  matchReason: string; // one sentence, always visible, never truncated
}

/* The protocol draft (client-side model). The real document of record is
 * the YAML the compiler emits; this is the in-progress projection the slot
 * meter and draft rail read from. */

/** The generic section patch  -  the shape ``add-rq``/``add-measure``/
 * ``set-parameter`` moves carry. */
export interface SectionPatch {
  section: keyof ProtocolDraft;
  /** append to a list section, or set a scalar/keyed section. */
  op: "append" | "set";
  key?: string;
  value: string | unknown[] | Record<string, unknown>;
}

/** A ``choose-template`` move's patch  -  the *only* thing that can fill the
 * draft's mandatory `design` slot (server: compiler.py). */
export interface TemplatePatch {
  templateId: string;
  parameters?: Record<string, unknown>;
  /** Set on a researcher's manual protocol entry: it replaces earlier moves. */
  manual?: boolean;
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

/** A ``prescribe-statistics`` move's executable analysis recipe. */
export interface StatisticsPatch {
  recipeId: string;
  rq?: string;
}

/** A ``set-field`` move's patch (server: compiler.FILLABLE_SLOTS)  -  fills one
 * scalar protocol field directly (a sample size, a session length, the study
 * title...), restricted server-side to the protocol's declared fillable
 * slots. `path` is the dotted field, split: `["participants", "planned"]`. */
export interface FieldPatch {
  op: "set-field";
  path: string[];
  value: unknown;
}

/** The parts of a study plan a ``set-plan`` card can change. */
export type PlanPart = "questions" | "design" | "participants" | "task" | "measures" | "title";

/** A ``set-plan`` card's patch: the plan values it sets, and the decided
 * values they replace (server: study_plan._cards). */
export interface PlanPatch {
  part: PlanPart;
  plan: Record<string, unknown>;
  before: Record<string, unknown>;
  /** Display names of the measure ids the card sets. */
  names?: Record<string, string>;
}

export type DraftPatch =
  | SectionPatch
  | TemplatePatch
  | InstrumentPatch
  | StatisticsPatch
  | FieldPatch
  | PlanPatch;

export function isPlanPatch(p: DraftPatch): p is PlanPatch {
  return "part" in p && "plan" in p;
}

/** A value on a study-plan card that the assistant chose because the
 * researcher had not said it (server: study_plan._mark_suggestions). */
export interface PlanSuggestion {
  field: string;
  label: string;
  why: string;
}

export function isSectionPatch(p: DraftPatch): p is SectionPatch {
  return "op" in p && (p.op === "append" || p.op === "set");
}

export function isTemplatePatch(p: DraftPatch): p is TemplatePatch {
  return "templateId" in p;
}

export function isInstrumentPatch(p: DraftPatch): p is InstrumentPatch {
  return "op" in p && (p.op === "add-instrument" || p.op === "set-instrument" || p.op === "reconfigure");
}

export function isStatisticsPatch(p: DraftPatch): p is StatisticsPatch {
  return "recipeId" in p;
}

export function isFieldPatch(p: DraftPatch): p is FieldPatch {
  return "op" in p && p.op === "set-field";
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

/** The core sections the conversation guides through. Ethics remains a visible,
 * optional posture in the draft, not an approval gate. */
export const MANDATORY_SLOTS: (keyof ProtocolDraft)[] = [
  "researchQuestions",
  "design",
  "participants",
  "conditions",
  "measures",
  "instruments",
  "statisticalPlan",
];

export const OPTIONAL_SLOTS: (keyof ProtocolDraft)[] = ["ethics"];

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

/** One-sentence explanations of each mandatory slot, shown in the in-app
 * protocol guide (ProtocolGuide) for researchers unfamiliar with the terms. */
export const SLOT_DESCRIPTIONS: Record<keyof ProtocolDraft, string> = {
  researchQuestions: "The RQs this study is designed to answer.",
  design:
    "The published study design (e.g. within/between-subjects) chosen from the corpus or templates; the only slot a template move can fill.",
  participants:
    "Planned sample size, assignment (within/between-subjects), and counterbalancing.",
  conditions:
    "The experimental arms a session runs under (glossary: \"condition,\" not group or treatment).",
  measures: "What gets measured to answer each research question.",
  instruments:
    "The data-collecting components configured for the study (e.g. TERN, agent capture) and their settings.",
  statisticalPlan:
    "How each research question will be analysed, decided in advance rather than after the data comes in.",
  ethics: "The study's ethics posture and the safeguards in place for participants.",
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

// ---------------------------------------------------------------- power (P2-2)

/** One point on a power/sensitivity curve: power at a per-group n. */
export interface PowerPoint {
  nPerGroup: number;
  totalN: number;
  power: number;
}

/** One effect size's curve across the explored per-group n range. */
export interface PowerCurve {
  effectSize: number;
  points: PowerPoint[];
}

/** The first n at which a curve reaches the target power  -  or an honest
 * "not reached within the explored range". */
export interface PowerRequirement {
  effectSize: number;
  nPerGroup: number | null;
  totalN: number | null;
  powerAtTargetN: number | null;
  reachesTarget: boolean;
}

/** GET /studies/{id}/power: the planning payload, assumptions included. */
export interface PowerDoc {
  model: string;
  assumption?: string;
  plannedParticipants?: number | null;
  design?: string;
  alpha: number;
  powerTarget: number;
  maxTotalN: number;
  curves: PowerCurve[];
  requiredN: PowerRequirement[];
  note?: string;
}
