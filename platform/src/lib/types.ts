

export interface Grounding {
  ref: string;
  confidence?: number;
  title: string;
  year?: number;
  venue?: string;
  why: string;
}

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
  | "caution";

export type MoveStatus = "proposed" | "accepted" | "rejected";

export interface DesignMove {
  moveId: string;
  kind: MoveKind;
  target: string;
  proposal: string;

  patch?: DraftPatch;
  grounding: Grounding[];
  status: MoveStatus;

  mergeData?: {
    templateIds: string[];
    reason: string;
  };
}

export interface Turn {
  turnId: string;
  role: "researcher" | "platform";
  author: string;
  text: string;
  moves: DesignMove[];
  recommendations: Recommendation[];

  source?: "llm" | "scripted" | "unavailable" | "scope";
}

export interface Understanding {
  facets: Record<string, boolean>;
  known: string[];
  missing: string[];
  missingLabels: string[];

  facetLabels?: Record<string, string>;
  readyForDesign: boolean;
  facetsNeeded: number;

  nextQuestion?: string;
}

export interface Recommendation {
  ref: string;
  confidence?: number;
  matchKind?: "direct" | "adjacent";
  matchedTerms?: string[];
  inStudy?: boolean;
  title: string;
  authors?: string[];
  year: number;
  venue: string;
  identifier?: string;
  abstract?: string;
  matchReason: string;
}

export interface SectionPatch {
  section: keyof ProtocolDraft;

  op: "append" | "set";
  key?: string;
  value: string;
}

export interface TemplatePatch {
  templateId: string;
  parameters?: Record<string, unknown>;
}

export interface InstrumentPatch {
  section: "instruments";
  op: "add-instrument" | "set-instrument" | "reconfigure";
  name: string;
  config?: Record<string, unknown>;
  path?: string[];
  value?: unknown;
}

export interface StatisticsPatch {
  recipeId: string;
  rq?: string;
}

export interface FieldPatch {
  op: "set-field";
  path: string[];
  value: unknown;
}

export type DraftPatch =
  | SectionPatch
  | TemplatePatch
  | InstrumentPatch
  | StatisticsPatch
  | FieldPatch;

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

function sentenceCase(segment: string): string {
  const spaced = segment.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

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

export interface PowerPoint {
  nPerGroup: number;
  totalN: number;
  power: number;
}

export interface PowerCurve {
  effectSize: number;
  points: PowerPoint[];
}

export interface PowerRequirement {
  effectSize: number;
  nPerGroup: number | null;
  totalN: number | null;
  powerAtTargetN: number | null;
  reachesTarget: boolean;
}

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
