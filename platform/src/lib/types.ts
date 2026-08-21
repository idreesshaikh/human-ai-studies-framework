/* The conversation domain model. These shapes match the server interfaces
 * so wiring the backend later is a transport swap, not a redesign. */

/** Citations attached to a design move. A move with no grounding is shown
 * as "unsourced". Quality is the continuous `confidence` (0..1) — there is no
 * provenance tier. */
export interface Grounding {
  ref: string; // corpus ref, e.g. "arxiv:2506.xxxxx", or template id
  confidence?: number; // 0..1 continuous quality signal — the sole quality rank
  title: string;
  year?: number;
  venue?: string;
  why: string; // "why this source" — shown on hover (GroundingChip)
}

/** One platform-proposed change to the protocol draft. */
// Mirrors design_llm._ALLOWED_KINDS exactly — the server drops any kind
// outside that set before a move ever reaches the wire, so this union is
// complete by construction as long as the two stay in sync. It used to
// carry "set-threshold", a kind the server has never sent, and was missing
// three it does: "set-field" and "declare-task" (the direct protocol-slot
// fills the conversation gained this session) and "reconfigure-instrument"
// (instrument tuning, e.g. the stuck-detector threshold). A card for any of
// the missing three rendered with no kind label at all — KIND_LABEL[kind]
// is undefined for a key TypeScript never knew to require.
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
  | "caution"; // a challenge to a choice — no draft change, just advice

export type MoveStatus = "proposed" | "accepted" | "rejected";

export interface DesignMove {
  moveId: string;
  kind: MoveKind;
  target: string; // protocol slot this move fills, e.g. "researchQuestions[]"
  proposal: string; // human-readable one-liner
  /** The change this move makes to the draft — a plain patch the compiler
   * applies. Caution and merge-templates moves carry none. */
  patch?: DraftPatch;
  grounding: Grounding[];
  status: MoveStatus;
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
  /** Which path produced a platform turn.
   *
   * - `"llm"` — the design conversation. The only kind that proposes moves.
   * - `"unavailable"` — a holding turn: the model couldn't be reached, so
   *   this says so and proposes nothing. Never persisted, so it is gone on
   *   reload; the researcher's own turn stays.
   * - `"scripted"` — turns stored before the keyword fallback was removed.
   *   Kept readable, never produced.
   *
   * Absent for researcher turns. */
  source?: "llm" | "scripted" | "unavailable";
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
  /** Every facet's label, keyed by facet id — including the ones already
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
  inStudy?: boolean; // already in the researcher's library
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

/** A ``set-field`` move's patch (server: compiler.FILLABLE_SLOTS) — fills one
 * scalar protocol field directly (a sample size, a session length, the study
 * title...), restricted server-side to the protocol's declared fillable
 * slots. `path` is the dotted field, split: `["participants", "planned"]`. */
export interface FieldPatch {
  op: "set-field";
  path: string[];
  value: unknown;
}

export type DraftPatch = SectionPatch | TemplatePatch | InstrumentPatch | FieldPatch;

export function isSectionPatch(p: DraftPatch): p is SectionPatch {
  return "op" in p && (p.op === "append" || p.op === "set");
}

export function isTemplatePatch(p: DraftPatch): p is TemplatePatch {
  return "templateId" in p;
}

export function isInstrumentPatch(p: DraftPatch): p is InstrumentPatch {
  return "op" in p && (p.op === "add-instrument" || p.op === "set-instrument" || p.op === "reconfigure");
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

/** camelCase -> "Camel case": the plain-words fallback for any identifier
 * this map doesn't recognise by name. Never used for a known slot — those
 * always take their SLOT_LABELS wording — only for a path segment (like
 * "durationMinutes") that has no entry of its own. */
function sentenceCase(segment: string): string {
  const spaced = segment.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

/** Renders a move's `target` (a dotted protocol path such as
 * "researchQuestions[]" or "session.durationMinutes") in the words a
 * researcher reads, never as raw code.
 *
 * `target` is model-authored (design_llm's own JSON contract, not a
 * validated enum), and an earlier prompt version showed a literal
 * "protocol.path" example the model echoed as a real "protocol." prefix —
 * this strips that defensively so an older persisted move still reads
 * cleanly. Each dotted segment is looked up against SLOT_LABELS where it
 * matches one of the eight mandatory sections; anything else falls back to
 * sentence case rather than showing camelCase or a raw path. */
export function targetLabel(target: string): string {
  const cleaned = target
    .replace(/^protocol\./, "")
    .replace(/\[\]$/, "")
    .trim();
  if (!cleaned) return "the protocol";
  return cleaned
    .split(".")
    .map((part) => SLOT_LABELS[part as keyof ProtocolDraft] ?? sentenceCase(part))
    .join(" \u2022 ");
}

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

/** The first n at which a curve reaches the target power — or an honest
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
  alpha: number;
  powerTarget: number;
  maxTotalN: number;
  curves: PowerCurve[];
  requiredN: PowerRequirement[];
}

