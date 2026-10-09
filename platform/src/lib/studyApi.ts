/* Study data and literature requests. Reads and mutations use the server. Credentials come from api.ts. */

import { ApiError, getAuthToken, notifyUnauthorized } from "./api.ts";
import { dataBundleFilename, dataBundlePath } from "./dataBundle.ts";
import type { PowerDoc, Recommendation } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

export class OfflineError extends Error {
  constructor() {
    super(
      "This needs the running middleware (port 8000). Start it with " +
        "`docker compose up`.",
    );
    this.name = "OfflineError";
  }
}

// ------------------------------------------------------------------- shapes

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
  /** ``harvested-via`` is the corpus provenance kind. The constellation maps
   * it to the researcher-facing recommendations series at its presentation
   * boundary, but the API type should still describe the wire response. */
  kind: "references" | "citations" | "recommendations" | "harvested-via";
}

export interface PaperGraph {
  studyId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** One recipe the dry run actually executed, with the statistic it produced. */
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
  pilot?: boolean;
  inclusionDecision?: string;
}

/** One session the middleware has heard from inside the live window. */
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
  /** Events received per bucket, oldest first  -  the sparkline. */
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
  state:
    | "enabled"
    | "disabled"
    | "external-required"
    | "unsupported"
    | "unavailable";
  configured: boolean;
  reason: string;
  executor: string;
  capabilities: Record<
    string,
    { state: string; available: boolean; reason: string }
  >;
  adapter?: string;
}

export interface StudyStatusDoc {
  studyId: string;
  generatedAt: string;
  conditions: string[];
  plannedParticipants: number;
  plannedSessionsPerParticipant: number;
  sessions: SessionStatus[];
  researchQuestions: { id: string; recipes: string[]; recipeRuns: string[] }[];
  producers: Record<string, ProducerStatus>;
  requiredProducers: string[];
}

// ------------------------------------------------------------------- transport

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function studyRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      ...init,
      headers: { ...(await authHeaders()), ...(init.headers ?? {}) },
      credentials: "include",
    });
  } catch {
    // Network down / no server  -  the offline branch decides what to do.
    throw new OfflineError();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON body */
    }
    if (res.status === 401) notifyUnauthorized();
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    // A 200 that isn't real JSON (dev-server SPA fallback, misconfigured
    // proxy) means there's no real API behind this origin  -  same offline
    // posture as an unreachable server.
    throw new OfflineError();
  }
}

const req = studyRequest;

function post<T>(path: string, body: unknown): Promise<T> {
  return req<T>(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function onSeededData(_listener: (study?: string) => void): () => void {
  void _listener;
  return () => {};
}

const enc = encodeURIComponent;

/** Fetch a file and hand it to the browser's download flow. The server's
 *  own error detail is surfaced (a study with no protocol yet explains
 *  itself), and the object URL is always revoked. */
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
      /* non-JSON error body */
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
    (() => req<Paper[]>(`/studies/${enc(study)}/papers`))(),
  papersGraph: (study: string) =>
    (() => req<PaperGraph>(`/studies/${enc(study)}/papers/graph`))(),
  ingestPaper: (study: string, id: { arxivId?: string; doi?: string }) =>
    post<{
      paperRef: string;
      title: string;
      edges: number;
      edgesPending?: boolean;
    }>(`/studies/${enc(study)}/papers`, id),
  deletePaper: (study: string, ref: string) =>
    req<{ deleted: string }>(`/studies/${enc(study)}/papers/${enc(ref)}`, {
      method: "DELETE",
    }),
  /** Corpus recommendations for a free-text query (FR-LIT-9)  -  drives the
   * conversation's live recommender box. */
  matchPapers: (study: string, query: string, limit = 5) =>
    post<{ studyId: string; recommendations: Recommendation[] }>(
      `/studies/${enc(study)}/papers/match`,
      { query, limit },
    ),
  /** One-click accept of a recommendation into the study's Library, keeping
   * the match reason as elicitation evidence (FR-LIT-9.3). */
  addPaperFromMatch: (study: string, ref: string, matchReason = "") =>
    post<{
      studyId: string;
      paperRef: string;
      title: string;
      addedVia: string;
      edges: number;
      edgesPending: boolean;
    }>(`/studies/${enc(study)}/papers/from-match`, { ref, matchReason }),
  /** Add a graph suggestion from its already-harvested metadata. This avoids
   * repeating a Semantic Scholar lookup when the provider is rate-limiting. */
  addPaperFromGraph: (study: string, ref: string) =>
    post<{
      studyId: string;
      paperRef: string;
      title: string;
      edges: number;
      edgesPending: boolean;
    }>(`/studies/${enc(study)}/papers/from-graph`, { ref }),
  setPaperLinks: (study: string, ref: string, targets: string[]) =>
    req<{ paperRef: string; links: string[] }>(
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
      return (await res.json()) as { paperRef: string };
    } catch {
      throw new OfflineError();
    }
  },
  /** The byte-reproducible replication kit (FR-PROT-7), saved to disk.
   *  Streamed straight to a blob  -  the archive is binary and can be large,
   *  so it never goes through the JSON `req` path. */
  downloadReplicationKit: async (study: string) => {
    await saveAs(
      `/studies/${enc(study)}/replication-kit`,
      `${study}-replication-kit.tar.gz`,
    );
  },
  /** The starter notebook + data dictionary, zipped: the analysis handoff.
   *  A loaded, documented dataframe with every planned recipe imported  -
   *  never run  -  so a researcher's own analysis starts from a known point
   *  rather than a bare dataset export. */
  downloadNotebook: async (study: string) => {
    await saveAs(`/studies/${enc(study)}/notebook`, `${study}-notebook.zip`);
  },
  /** The collected data as a zip of tidy CSVs + the joined timeline + data
   *  dictionary, for the researcher's own postprocessing. Dry-run rows are
   *  left out unless `includeSynthetic` is set. */
  downloadDesignCard: async (study: string) =>
    saveAs(
      `/studies/${enc(study)}/design-card?format=markdown`,
      `${study}-design-card.md`,
    ),
  downloadDataBundle: async (study: string, includeSynthetic = false) => {
    await saveAs(
      dataBundlePath(study, includeSynthetic),
      dataBundleFilename(study),
    );
  },
  /** The elicitation record (FR-CONV-6) as a JSON file. */
  downloadElicitationRecord: async (study: string) => {
    await saveAs(
      `/studies/${enc(study)}/conversation/export`,
      `${study}-elicitation-record.json`,
    );
  },
  dataset: (study: string, includeSynthetic = false) =>
    (() =>
      req<{ studyId: string; rows: DatasetRow[] }>(
        `/studies/${enc(study)}/dataset${includeSynthetic ? "?includeSynthetic=true" : ""}`,
      ))(),
  /** Sessions the middleware has heard from recently (FR-DASH-3).
   *
   * Deliberately *not* seeded when the server is unreachable: an empty live
   * monitor is the honest answer to "is anyone running right now?", whereas
   * invented sessions would be the one place a fake reads as a real
   * participant at work. */
  live: (study: string, windowSeconds = 300) =>
    req<LiveDoc>(
      `/studies/${enc(study)}/live?windowSeconds=${windowSeconds}`,
    ).catch(() => ({
      now: new Date().toISOString(),
      windowSeconds,
      bucketSeconds: 10,
      sessions: [],
    })),

  /** The deterministic prescription table (FR-TPL-6): design shape → exact
   * test, effect size, correction, sample-size guidance. Pass a `study`
   * to scope it to that study's own compiled analysis plan; omit it for
   * the full browsable catalogue of every shape PHOENIX can prescribe. */
  prescriptions: (study?: string) => {
    const run = () =>
      req<{ prescriptions: Prescription[] }>(
        `/analysis/prescriptions${study ? `?study_id=${enc(study)}` : ""}`,
      ).then((d) => d.prescriptions);
    return run();
  },
  /** Unsaved compatibility power curve, calculated by the live planner. */
  power: (
    study: string,
    opts: {
      alpha?: number;
      maxN?: number;
      powerTarget?: number;
      effectSizes?: number[];
    } = {},
  ) =>
    (() => {
      const q = new URLSearchParams();
      q.set("alpha", String(opts.alpha ?? 0.05));
      q.set("maxN", String(opts.maxN ?? 120));
      q.set("powerTarget", String(opts.powerTarget ?? 0.8));
      q.set("effectSizes", (opts.effectSizes ?? [0.2, 0.5, 0.8]).join(","));
      return req<PowerDoc>(`/studies/${enc(study)}/power?${q.toString()}`);
    })(),
  status: (study: string, includeSynthetic = false) =>
    (() =>
      req<StudyStatusDoc>(
        `/studies/${enc(study)}/status${includeSynthetic ? "?includeSynthetic=true" : ""}`,
      ))(),
  /** Recorded protocol for readers, without compilation or a database write. */
  protocol: (study: string) =>
    (() =>
      req<{ document?: Record<string, unknown> }>(
        `/studies/${enc(study)}/protocol`,
      ).then((r) => r.document ?? null))(),

  sessionEvents: (_studyId: string, sessionId: string) =>
    (() =>
      req<import("./timeline").EventRow[]>(
        `/sessions/${enc(sessionId)}/events`,
      ))(),
};
