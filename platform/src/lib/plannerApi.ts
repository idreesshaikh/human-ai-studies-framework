import { studyRequest } from "./studyApi";

export interface PlanInputs {
  design: string;
  test: string;
  distribution: string;
  effect: number;
  sd: number;
  alpha: number;
  target_power: number;
  dropout: number;
  covariate_correlation: number;
  period_effect: number;
  order_effect: number;
  counterbalanced: boolean;
  planned_n: number;
  max_n: number;
  simulations: number;
  seed: number;
  ordinal_levels: number;
  measure_id?: string | null;
}
export interface Requirement {
  nPerArm: number;
  totalN: number;
  recruitPerArm: number;
  recruitTotal: number;
  power: number;
  ci: [number, number] | null;
}
export interface PlanResult {
  inputs: PlanInputs;
  basis: "assumptions" | "pilot-data";
  method: string;
  effectUnits: string;
  required: Requirement | null;
  /** Why no sample size is reported when the target was reachable; null otherwise. */
  requiredWithheld?: { code: string; message: string } | null;
  curve: {
    totalN: number;
    nPerArm: number;
    power: number;
    ci: [number, number] | null;
  }[];
  sensitivity: { totalN: number; smallestDetectableEffect: number | null }[];
  warnings: string[];
  nullPower?: { power: number; ci: [number, number] } | null;
  planId?: number;
  createdAt?: string;
  stale?: boolean;
  measureId?: string | null;
  protocol?: { protocolHash: string; protocolVersion: number };
  pilot?: {
    participants: number;
    sd: number;
    sdCI: [number, number];
    actionable: boolean;
  } | null;
  before?: PlanResult;
  pilotSensitivity?: { sd: number; required: Requirement | null }[];
}
export interface TypedMeasure {
  id: string;
  construct: string;
  instrument: string;
  fields: string[];
  analysisRecipe: string;
  analysisScale?: "raw" | "log";
}
export interface PlannerProtocol {
  protocolVersion: number;
  participants: { design: string; planned: number; counterbalanced: boolean };
  conditions: string[];
  measures?: (string | TypedMeasure)[];
  analysisPlan: { rq: string; recipes: string[] }[];
  controlConditions?: string[];
  rerunOf?: string;
}
export interface SessionDecision {
  pilot: boolean;
  decision: "include" | "exclude" | "undecided";
  reason: string;
  decidedBy: string;
  updatedAt: string;
}
export interface AuditResult {
  sessions: {
    sessionId: string;
    participantId: string;
    condition: string;
    status: "no-evidence" | "evidence-of-ai-use" | "cannot-assess";
    counts: Record<string, number>;
    reasons: string[];
    captureComplete: boolean;
    decision: SessionDecision | null;
  }[];
  blindSpots: string[];
  accuracy: string;
}
export interface Lineage {
  original: unknown;
  rerun: unknown;
  pooled: false;
  fields: {
    field: string;
    original: unknown;
    rerun: unknown;
    changed: boolean;
  }[];
}
const path = (id: string) => `/studies/${encodeURIComponent(id)}`;
function post<T>(url: string, body: unknown) {
  return studyRequest<T>(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}
export const plannerApi = {
  load: (id: string) =>
    studyRequest<{
      plan: PlanResult | null;
      protocol: PlannerProtocol;
      decisions: Record<string, SessionDecision>;
    }>(`${path(id)}/plan`),
  calculate: (id: string, inputs: PlanInputs) =>
    post<PlanResult>(`${path(id)}/plan`, inputs),
  pilot: (id: string, inputs: PlanInputs) =>
    post<PlanResult>(`${path(id)}/pilot-variance`, inputs),
  audit: (id: string) =>
    studyRequest<AuditResult>(`${path(id)}/control-arm-audit`),
  annotate: (
    id: string,
    session: string,
    body: { pilot?: boolean; decision?: string; reason: string },
  ) =>
    post<SessionDecision>(
      `${path(id)}/sessions/${encodeURIComponent(session)}/annotation`,
      body,
    ),
  lineage: (id: string) => studyRequest<Lineage>(`${path(id)}/lineage`),
};
