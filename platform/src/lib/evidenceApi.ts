import { studyRequest } from "./studyApi";

export interface EvidenceContext {
  query: string;
  population: string;
  task: string;
  construct: string;
  producers: string[];
  instruments: string[];
  confirmedRelationIds: string[];
}

export interface EvidenceSource {
  id: string;
  kind: string;
  claim: string;
  review: { status: string; reviewers: string[] };
  applicability: { context: string; status: string };
  passage: { location: string; text: string };
  publication: { title: string; source: string; version: string | null };
}

export interface EvidenceCandidate {
  id: string;
  designFamily: string | null;
  status: "compatible" | "conditional" | "incompatible" | "insufficient-evidence";
  reasons: string[];
  missingFacts: string[];
  constraints: string[];
  sources: EvidenceSource[];
  study: {
    population: string | null;
    tasks: string[] | null;
    constructs: string[];
    limitations: string[] | null;
    analysisAssumptions: string[] | null;
    measures: { id: string; instrument: string | null; datasetFields: string[] | null; analysisRecipe: string | null }[];
    captureRequirements: { measureId: string; producer: string | null; eventTypes: string[] | null; availability: string }[];
  };
}

export interface EvidenceSnapshot {
  mapId: string;
  mapVersion: string;
  mapDescription: string;
  mapDigest: string;
  context: EvidenceContext;
  candidate: EvidenceCandidate;
}

export interface EvidenceMap {
  digest: string | null;
  document: { mapId: string; mapVersion: string; description: string } | null;
}

const path = (id: string) => `/studies/${encodeURIComponent(id)}/evidence-map`;
const json = (method: string, body: unknown) => ({ method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
export const evidenceApi = {
  load: (id: string) => studyRequest<EvidenceMap>(path(id)),
  import: (id: string, document: unknown) => studyRequest<EvidenceMap>(path(id), json("PUT", document)),
  compare: (id: string, context: EvidenceContext) => studyRequest<{ digest: string; candidates: EvidenceCandidate[] }>(`${path(id)}/candidates`, json("POST", context)),
  propose: (id: string, context: EvidenceContext, candidateId: string, mapDigest: string, requestId: string) =>
    studyRequest<{ moveId: string }>(`${path(id)}/propose`, json("POST", { ...context, candidateId, mapDigest, requestId })),
};
