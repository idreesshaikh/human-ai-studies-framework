import { OfflineError, getAuthToken, request as req, apiBase } from "./api.ts";
import type { PowerDoc, Recommendation } from "./types";
import { DEMO_STUDY_ID } from "./demo.ts";

const API_BASE = apiBase().replace(/\/+$/, "");

export { OfflineError } from "./api.ts";

export interface Paper {
  paperRef: string;
  title: string;
  authors: string[];
  year: number | null;
  venue: string;
  abstract: string;
  doi: string;
  arxivId: string;
  url: string;
  citationCount: number | null;
  hasFullText: boolean;
  links: string[];
  addedAt: string;
  inProtocolLiterature: boolean;
}

export interface GraphNode {
  paperRef: string;
  title: string;
  authors?: string[];
  year: number | null;
  abstract?: string;
  citationCount: number | null;
  ingested: boolean;
}

export interface GraphEdge {
  src: string;
  dst: string;

  kind: "references" | "citations" | "recommendations" | "harvested-via";
}

export interface PaperGraph {
  studyId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface DryRunResult {
  recipeId: string;
  title: string;
  rqs: string[];
  answers: string[];

  summary: string;
}

export interface DryRunPlan {
  planned: number;
  ran: string[];
  blocked: { recipeId: string; rq: string; reason: string; }[];
  errors?: Record<string, string>;
  results: DryRunResult[];

  note?: string;
}

export interface DatasetRow {
  source: string;
  ts: string;
  sessionId: string;
  participantId: string;
  condition: string;
  taskId?: string;
  schemaVersion?: number;
  type: string;
  seq: number | null;
  flags: string[];
  payload: Record<string, unknown>;
}

export interface LiveSession {
  sessionId: string;
  participantId: string;
  condition: string;
  taskId: string;
  taskTitle: string;
  blockIndex: number | null;
  blocksTotal: number | null;
  eventsInWindow: number;
  lastEventType: string;
  lastReceivedAt: string;
  lastSeq: number;

  rate: number[];
  gapCount: number;
  missingEvents: number;
}

export interface LiveDoc {
  now: string;
  windowSeconds: number;
  bucketSeconds: number;
  sessions: LiveSession[];
}

export interface Prescription {
  designShape: string;
  test: string;
  effectSize: string;
  correction: string;
  sampleSizeGuidance: string;
  rationale: string;
}

export interface SessionStatus {
  sessionId: string;
  participantId: string;
  condition: string;
  taskId?: string;
  events: number;
  metricRows: number;
  sourceCounts?: Record<string, number>;
  flaggedEvents: number;
  flagKinds: string[];
  gapCount: number;
  missingEvents: number;
  complete: boolean;
  lastReceivedAt: string | null;
}

export interface ProducerStatus {
  source: string;
  state: "enabled" | "disabled" | "external-required" | "unsupported" | "unavailable";
  configured: boolean;
  reason: string;
  executor: string;
  capabilities: Record<string, { state: string; available: boolean; reason: string; }>;
  adapter?: string;
}

export interface StudyStatusDoc {
  studyId: string;
  generatedAt: string;
  conditions: string[];
  plannedParticipants: number;
  plannedSessionsPerParticipant: number;
  sessions: SessionStatus[];
  researchQuestions: { id: string; recipes: string[]; recipeRuns: string[]; }[];
  producers: Record<string, ProducerStatus>;
  requiredProducers: string[];
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function post<T>(path: string, body: unknown): Promise<T> {
  return req<T>(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

const enc = encodeURIComponent;
const sampleQuery = (study: string) => study === DEMO_STUDY_ID ? "?includeSynthetic=true" : "";

async function saveAs(path: string, filename: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      headers: await authHeaders(),
      credentials: "include",
    });
  } catch {
    throw new OfflineError();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      detail = `Download failed (${res.status}). Try again.`;
    }
    throw new Error(detail);
  }
  const url = URL.createObjectURL(await res.blob());
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

export const studyApi = {
  papers: (study: string) =>
    req<Paper[]>(`/studies/${enc(study)}/papers`),
  papersGraph: (study: string) =>
    req<PaperGraph>(`/studies/${enc(study)}/papers/graph`),
  ingestPaper: (study: string, id: { arxivId?: string; doi?: string; }) =>
    post<{ paperRef: string; title: string; edges: number; edgesPending?: boolean; }>(
      `/studies/${enc(study)}/papers`,
      id,
    ),
  deletePaper: (study: string, ref: string) =>
    req<{ deleted: string; }>(`/studies/${enc(study)}/papers/${enc(ref)}`, {
      method: "DELETE",
    }),

  matchPapers: (study: string, query: string, limit = 5) =>
    post<{ studyId: string; recommendations: Recommendation[]; }>(
      `/studies/${enc(study)}/papers/match`,
      { query, limit },
    ),

  addPaperFromMatch: (study: string, ref: string, matchReason = "") =>
    post<{
      studyId: string;
      paperRef: string;
      title: string;
      addedVia: string;
      edges: number;
      edgesPending: boolean;
    }>(`/studies/${enc(study)}/papers/from-match`, { ref, matchReason }),

  addPaperFromGraph: (study: string, ref: string) =>
    post<{
      studyId: string;
      paperRef: string;
      title: string;
      edges: number;
      edgesPending: boolean;
    }>(`/studies/${enc(study)}/papers/from-graph`, { ref }),
  setPaperLinks: (study: string, ref: string, targets: string[]) =>
    req<{ paperRef: string; links: string[]; }>(
      `/studies/${enc(study)}/papers/${enc(ref)}/links`,
      {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ targets }),
      },
    ),
  uploadPaperPdf: async (study: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/studies/${enc(study)}/papers/upload`, {
        method: "POST",
        body,
        headers: await authHeaders(),
        credentials: "include",
      });
    } catch {
      throw new OfflineError();
    }
    if (!res.ok) throw new Error(`upload failed: ${res.status}`);
    try {
      return (await res.json()) as { paperRef: string; };
    } catch {
      throw new OfflineError();
    }
  },

  downloadReplicationKit: async (study: string) => {
    await saveAs(
      `/studies/${enc(study)}/replication-kit`,
      `${study}-replication-kit.tar.gz`,
    );
  },

  downloadNotebook: async (study: string) => {
    await saveAs(`/studies/${enc(study)}/notebook`, `${study}-notebook.zip`);
  },

  downloadElicitationRecord: async (study: string) => {
    await saveAs(
      `/studies/${enc(study)}/conversation/export`,
      `${study}-elicitation-record.json`,
    );
  },
  dataset: (study: string) =>
    req<{ studyId: string; rows: DatasetRow[]; }>(
      `/studies/${enc(study)}/dataset${sampleQuery(study)}`,
    ),

  live: (study: string, windowSeconds = 300) =>
    req<LiveDoc>(
      `/studies/${enc(study)}/live?windowSeconds=${windowSeconds}`,
    ),

  prescriptions: (study?: string) => {
    const run = () =>
      req<{ prescriptions: Prescription[]; }>(
        `/analysis/prescriptions${study ? `?study_id=${enc(study)}` : ""}`,
      ).then((d) => d.prescriptions);
    return run();
  },

  power: (
    study: string,
    opts: {
      alpha?: number;
      maxN?: number;
      powerTarget?: number;
      effectSizes?: number[];
    } = {},
  ) => {
    const q = new URLSearchParams();
    q.set("alpha", String(opts.alpha ?? 0.05));
    q.set("maxN", String(opts.maxN ?? 120));
    q.set("powerTarget", String(opts.powerTarget ?? 0.8));
    q.set("effectSizes", (opts.effectSizes ?? [0.2, 0.5, 0.8]).join(","));
    return req<PowerDoc>(`/studies/${enc(study)}/power?${q.toString()}`);
  },

  simulate: (study: string, count = 10, profile = "mixed", seed?: number) =>
    post<{
      participants: number;
      profile: string;
      seed: number | null;
      run: string;
      sessions: number;
      events: number;
      metricRows: number;
      sessionIds: string[];
      studyId: string;
      plan: DryRunPlan;
    }>(`/studies/${enc(study)}/simulate`, {
      count,
      profile,
      ...(seed !== undefined ? { seed } : {}),
    }),
  status: (study: string) =>
    req<StudyStatusDoc>(
      `/studies/${enc(study)}/status${sampleQuery(study)}`,
    ),

  protocol: (study: string) =>
    req<{ document?: Record<string, unknown>; }>(
      `/studies/${enc(study)}/protocol`,
    ).then((r) => r.document ?? null),
  sessionEvents: (_studyId: string, sessionId: string) =>
    req<import("./timeline").EventRow[]>(`/sessions/${enc(sessionId)}/events`),
};
