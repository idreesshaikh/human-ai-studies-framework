/* The study-data client. Talks to the ingestion middleware for the study
 * operational + knowledge endpoints — papers, the citation graph, the grounded
 * assistant, session status, the dataset, and the lifecycle.
 *
 * Same-origin by default: in production the middleware serves this SPA (NFR-7),
 * so `''` resolves to :8000. Set VITE_API_BASE for a separate origin (needs
 * MIDDLEWARE_CORS_ORIGINS, FR-OPS-6). The bearer token comes from `api.ts`'s
 * shared `getAuthToken()` — the pasted-token fallback (`middleware.token` in
 * localStorage, matching MIDDLEWARE_TOKEN) or, in Clerk mode, the live Clerk
 * session JWT `AuthProvider` installs via `setTokenProvider`.
 *
 * Offline posture: the platform is explorable with no server (the hero demo,
 * `npm run dev` with nothing on :8000). Read endpoints fall back to a curated
 * seed so the constellation and charts still render beautifully; live actions
 * (ingest, assistant) raise `OfflineError`, which the UI shows as a calm
 * "needs the running middleware" notice. Nothing load-bearing is cloud-owned. */

import { ApiError, getAuthToken, notifyUnauthorized } from "./api.ts";
import { isDemoStudy } from "./demo.ts";
import type { Recommendation } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

export class OfflineError extends Error {
  constructor() {
    super(
      "This needs the running middleware (port 8000). Start it with " +
        "`docker compose up`, or explore the seeded demo below.",
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
  citationCount: number | null;
  ingested: boolean;
}

export interface GraphEdge {
  src: string;
  dst: string;
  kind: "references" | "citations" | "recommendations";
}

export interface PaperGraph {
  studyId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface AssistantAnswer {
  answer: string;
  citations: string[];
  toolCalls: { tool: string; input: Record<string, unknown> }[];
}

export interface AssistantConfig {
  configured: boolean;
  models: string[];
  defaultModel: string;
}

export interface DatasetRow {
  source: string;
  ts: string;
  sessionId: string;
  participantId: string;
  condition: string;
  type: string;
  seq: number | null;
  flags: string[];
  payload: Record<string, unknown>;
}

export interface Gate {
  artifact: string;
  satisfied: boolean;
  satisfiedBy: { fileId: number; uploadedAt: string; size: number } | null;
}

export interface LifecyclePhase {
  name: string;
  status: "complete" | "current" | "upcoming";
  gates: Gate[];
}

export interface LifecycleDoc {
  currentPhase: string;
  phases: LifecyclePhase[];
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
  events: number;
  metricRows: number;
  flaggedEvents: number;
  flagKinds: string[];
  gapCount: number;
  missingEvents: number;
  complete: boolean;
  lastReceivedAt: string | null;
}

// ------------------------------------------------------------------- transport

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      ...init,
      headers: { ...(await authHeaders()), ...(init.headers ?? {}) },
      credentials: "include",
    });
  } catch {
    // Network down / no server — the offline branch decides what to do.
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
    // proxy) means there's no real API behind this origin — same offline
    // posture as an unreachable server.
    throw new OfflineError();
  }
}

function post<T>(path: string, body: unknown): Promise<T> {
  return req<T>(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Run a read against the server, but fall back to `seed` when offline so the
 * surface still renders (the constellation and charts are worth showing even
 * with nothing on :8000). Non-offline errors propagate. */
// When the middleware is unreachable, reads fall back to built-in sample data
// so the UI stays explorable — but that must never be mistaken for a live
// study's real data. Anything that falls back fires this signal so surfaces
// (the Data tab) can say so honestly.
type SeededListener = () => void;
const seededListeners = new Set<SeededListener>();

export function onSeededData(listener: SeededListener): () => void {
  seededListeners.add(listener);
  return () => seededListeners.delete(listener);
}

function notifySeeded(): void {
  for (const l of seededListeners) l();
}

async function liveOrSeed<T>(run: () => Promise<T>, seed: T): Promise<T> {
  try {
    return await run();
  } catch (e) {
    if (e instanceof OfflineError) {
      notifySeeded();
      return seed;
    }
    throw e;
  }
}

/** Study-scoped reads: only the seeded demo study shows sample data when
 * offline. Every real study falls back to an honest *empty* value (it starts
 * from scratch), and — unlike the demo — does NOT raise the "seeded sample
 * data" banner, because empty is the truth, not a stand-in. */
async function liveOrSeedStudy<T>(
  study: string,
  run: () => Promise<T>,
  demoSeed: T,
  empty: T,
): Promise<T> {
  try {
    return await run();
  } catch (e) {
    if (e instanceof OfflineError) {
      if (isDemoStudy(study)) {
        notifySeeded();
        return demoSeed;
      }
      return empty;
    }
    throw e;
  }
}

export const EMPTY_LIFECYCLE: LifecycleDoc = {
  currentPhase: "design",
  phases: [
    { name: "design", status: "current", gates: [] },
    { name: "ethics", status: "upcoming", gates: [] },
    { name: "pilot", status: "upcoming", gates: [] },
    { name: "recruitment", status: "upcoming", gates: [] },
    { name: "data-collection", status: "upcoming", gates: [] },
    { name: "analysis", status: "upcoming", gates: [] },
    { name: "write-up", status: "upcoming", gates: [] },
  ],
};

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
    liveOrSeedStudy(
      study,
      () => req<Paper[]>(`/studies/${enc(study)}/papers`),
      SEED_PAPERS,
      [],
    ),
  papersGraph: (study: string) =>
    liveOrSeedStudy(
      study,
      () => req<PaperGraph>(`/studies/${enc(study)}/papers/graph`),
      seedGraph(study),
      { studyId: study, nodes: [], edges: [] },
    ),
  ingestPaper: (study: string, id: { arxivId?: string; doi?: string }) =>
    post<{ paperRef: string; title: string; edges: number }>(
      `/studies/${enc(study)}/papers`,
      id,
    ),
  deletePaper: (study: string, ref: string) =>
    req<{ deleted: string }>(`/studies/${enc(study)}/papers/${enc(ref)}`, {
      method: "DELETE",
    }),
  /** Corpus recommendations for a free-text query (FR-LIT-9) — drives the
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
    }>(`/studies/${enc(study)}/papers/from-match`, { ref, matchReason }),
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
   *  Streamed straight to a blob — the archive is binary and can be large,
   *  so it never goes through the JSON `req` path. */
  downloadReplicationKit: async (study: string) => {
    await saveAs(
      `/studies/${enc(study)}/replication-kit`,
      `${study}-replication-kit.tar.gz`,
    );
  },
  /** The elicitation record (FR-CONV-6) as a JSON file. */
  downloadElicitationRecord: async (study: string) => {
    await saveAs(
      `/studies/${enc(study)}/conversation/export`,
      `${study}-elicitation-record.json`,
    );
  },
  assistantConfig: (study: string) =>
    liveOrSeed(
      () => req<AssistantConfig>(`/studies/${enc(study)}/assistant/config`),
      { configured: false, models: [], defaultModel: "" },
    ),
  assistant: (
    study: string,
    question: string,
    history: { role: string; content: string }[],
    model?: string,
  ) =>
    post<AssistantAnswer>(`/studies/${enc(study)}/assistant`, {
      question,
      history,
      ...(model ? { model } : {}),
    }),
  dataset: (study: string) =>
    liveOrSeedStudy(
      study,
      () =>
        req<{ studyId: string; rows: DatasetRow[] }>(
          `/studies/${enc(study)}/dataset`,
        ),
      { studyId: study, rows: SEED_METRICS },
      { studyId: study, rows: [] },
    ),
  lifecycle: (study: string) =>
    liveOrSeedStudy(
      study,
      () => req<LifecycleDoc>(`/studies/${enc(study)}/lifecycle`),
      SEED_LIFECYCLE,
      EMPTY_LIFECYCLE,
    ),
  /** Attest that a gate's requirement is met, advancing the study a phase
   * (FR-DASH-2). Returns the recomputed lifecycle. */
  attestGate: (study: string, artifact: string, note = "") =>
    post<LifecycleDoc>(
      `/studies/${enc(study)}/lifecycle/gates/${enc(artifact)}/attest`,
      { note, attestedBy: "Researcher", confirmed: true },
    ),
  /** The deterministic prescription table (FR-TPL-6): design shape → exact
   * test, effect size, correction, sample-size guidance. Not study-scoped. */
  prescriptions: () =>
    liveOrSeed(
      () =>
        req<{ prescriptions: Prescription[] }>(`/analysis/prescriptions`).then(
          (d) => d.prescriptions,
        ),
      SEED_PRESCRIPTIONS,
    ),
  status: (study: string) =>
    liveOrSeedStudy(
      study,
      () =>
        req<{ sessions: SessionStatus[]; conditions: string[] }>(
          `/studies/${enc(study)}/status`,
        ),
      { sessions: SEED_SESSIONS, conditions: SEED_CONDITIONS },
      { sessions: [], conditions: [] },
    ),
  sessionEvents: (studyId: string, sessionId: string) =>
    liveOrSeedStudy(
      studyId,
      () => req<import("./timeline").EventRow[]>(`/sessions/${enc(sessionId)}/events`),
      SEED_SESSION_EVENTS,
      [],
    ),
};

// ---------------------------------------------------------------- offline seed
//
// A curated, corpus-consistent seed (the same landmark papers the design
// conversation cites) so the constellation, library, charts, and lifecycle are
// beautiful with no server — the platform's offline-explorable posture.

const SEED_PAPERS: Paper[] = [
  seedPaper("corpus:trust-in-ai-code-generation", "Investigating and Designing for Trust in AI-powered Code Generation", 2024, 141, ["RQ-1", "measure:review-latency"]),
  seedPaper("corpus:metr-early-2025-dev-productivity", "Measuring the Impact of Early-2025 AI on Developer Productivity", 2025, 63, ["design:within-subjects"]),
  seedPaper("corpus:guidelines-empirical-llm-se", "Guidelines for Empirical Studies of LLMs in Software Engineering", 2025, 88, ["design:within-subjects"]),
  seedPaper("corpus:insecure-code-with-ai-assistants", "Do Users Write More Insecure Code with AI Assistants?", 2023, 302, ["measure:correctness"]),
  seedPaper("corpus:realhumaneval", "RealHumanEval: Measuring the Human Utility of Coding Assistants", 2024, 47, []),
];

function seedPaper(
  ref: string,
  title: string,
  year: number,
  citationCount: number,
  links: string[],
): Paper {
  return {
    paperRef: ref,
    title,
    authors: [],
    year,
    venue: "",
    abstract:
      "Seeded corpus paper: the citation neighbourhood and full metadata " +
      "load from the running middleware.",
    doi: "",
    arxivId: "",
    url: "",
    citationCount,
    hasFullText: true,
    links,
    addedAt: "",
    inProtocolLiterature: links.length > 0,
  };
}

function seedGraph(study: string): PaperGraph {
  const nodes: GraphNode[] = SEED_PAPERS.map((p) => ({
    paperRef: p.paperRef,
    title: p.title,
    year: p.year,
    citationCount: p.citationCount,
    ingested: true,
  }));
  // A few un-ingested suggestions on the periphery (the grow-the-graph moment).
  const suggestions: [string, string, number][] = [
    ["arxiv:2308.10620", "Large Language Models for Software Engineering: A Survey", 210],
    ["arxiv:2302.06590", "Is Your Code Generated by ChatGPT Really Correct?", 620],
    ["doi:10.1145/3597503", "Grounded Copilot: How Programmers Interact with Code-Generating Models", 180],
  ];
  for (const [ref, title, cc] of suggestions) {
    nodes.push({ paperRef: ref, title, year: null, citationCount: cc, ingested: false });
  }
  const edges: GraphEdge[] = [
    { src: "corpus:trust-in-ai-code-generation", dst: "corpus:insecure-code-with-ai-assistants", kind: "references" },
    { src: "corpus:metr-early-2025-dev-productivity", dst: "corpus:guidelines-empirical-llm-se", kind: "references" },
    { src: "corpus:realhumaneval", dst: "corpus:trust-in-ai-code-generation", kind: "citations" },
    { src: "corpus:trust-in-ai-code-generation", dst: "arxiv:2308.10620", kind: "recommendations" },
    { src: "corpus:insecure-code-with-ai-assistants", dst: "arxiv:2302.06590", kind: "recommendations" },
    { src: "corpus:metr-early-2025-dev-productivity", dst: "doi:10.1145/3597503", kind: "recommendations" },
    { src: "corpus:guidelines-empirical-llm-se", dst: "corpus:realhumaneval", kind: "citations" },
  ];
  return { studyId: study, nodes, edges };
}

const SEED_CONDITIONS = ["ai-assisted", "unaided"];

// A small metric dataset (function-level) so the metric strip has a shape.
const SEED_METRICS: DatasetRow[] = seedMetricRows();

function seedMetricRows(): DatasetRow[] {
  const rows: DatasetRow[] = [];
  // Deterministic, plausible cognitive_complexity split: ai-assisted a touch
  // higher-variance (the kind of shape the study probes). No randomness.
  const cfg: [string, number[]][] = [
    ["ai-assisted", [4, 6, 7, 9, 11, 13, 8, 15, 6, 10]],
    ["unaided", [5, 6, 6, 7, 8, 8, 9, 7, 6, 10]],
  ];
  let seq = 0;
  for (const [condition, values] of cfg) {
    values.forEach((v, i) => {
      rows.push({
        source: "metrics",
        ts: "",
        sessionId: `S-${condition}`,
        participantId: `P${i + 1}`,
        condition,
        type: "function_metrics",
        seq: seq++,
        flags: [],
        payload: {
          function: `handler_${i}`,
          file: "app.py",
          cognitive_complexity: v,
          parameter_count: Math.min(7, 2 + (v % 5)),
          nesting_penalty: Math.round(v / 3),
        },
      });
    });
  }
  return rows;
}

const SEED_SESSION_EVENTS: import("./timeline").EventRow[] = [
  {
    v: 4, ts: "2026-07-16T14:30:00.000Z", mono: 0,
    sessionId: "S-ai-assisted", source: "cognitive-overlay",
    participantId: "P1", condition: "ai-assisted",
    seq: 0, type: "session_start", payload: {}, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:30:05.000Z", mono: 5_000,
    sessionId: "S-ai-assisted", source: "cognitive-overlay",
    participantId: "P1", condition: "ai-assisted",
    seq: 1, type: "edit_burst", payload: { charsAdded: 120, linesTouched: 5, origin: "human" }, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:30:45.000Z", mono: 45_000,
    sessionId: "S-ai-assisted", source: "agent-capture",
    participantId: "P1", condition: "ai-assisted",
    seq: 0, type: "agent_turn", payload: { role: "assistant", tool: "EditTool", chars: 450 }, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:31:10.000Z", mono: 70_000,
    sessionId: "S-ai-assisted", source: "cognitive-overlay",
    participantId: "P1", condition: "ai-assisted",
    seq: 2, type: "edit_burst", payload: { charsAdded: 320, linesTouched: 12, origin: "ai" }, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:32:00.000Z", mono: 120_000,
    sessionId: "S-ai-assisted", source: "agent-capture",
    participantId: "P1", condition: "ai-assisted",
    seq: 1, type: "tool_use", payload: { tool: "ReadTool", durationMs: 3_200 }, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:33:00.000Z", mono: 180_000,
    sessionId: "S-ai-assisted", source: "cognitive-overlay",
    participantId: "P1", condition: "ai-assisted",
    seq: 3, type: "fatigue_prompt_shown", payload: { trigger: "scheduled" }, flags: ["unauthenticated"],
  },
  {
    v: 4, ts: "2026-07-16T14:33:05.000Z", mono: 185_000,
    sessionId: "S-ai-assisted", source: "cognitive-overlay",
    participantId: "P1", condition: "ai-assisted",
    seq: 4, type: "fatigue_response", payload: { value: 4, points: 7 }, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:35:00.000Z", mono: 300_000,
    sessionId: "S-ai-assisted", source: "workspace-snapshot",
    participantId: "P1", condition: "ai-assisted",
    seq: 0, type: "snapshot", payload: { commit: "abc1234" }, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:38:00.000Z", mono: 480_000,
    sessionId: "S-ai-assisted", source: "task-harness",
    participantId: "P1", condition: "ai-assisted",
    seq: 0, type: "test_result", payload: { passed: 3, failed: 1 }, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:40:00.000Z", mono: 600_000,
    sessionId: "S-ai-assisted", source: "agent-capture",
    participantId: "P1", condition: "ai-assisted",
    seq: 2, type: "agent_turn", payload: { role: "user", chars: 80 }, flags: ["credential-mismatch"],
  },
];

const SEED_SESSIONS: SessionStatus[] = [
  { sessionId: "S-ai-assisted", participantId: "P1", condition: "ai-assisted", events: 214, metricRows: 10, flaggedEvents: 0, flagKinds: [], gapCount: 0, missingEvents: 0, complete: true, lastReceivedAt: "2026-07-16T15:02:00.000Z" },
  { sessionId: "S-unaided", participantId: "P1", condition: "unaided", events: 198, metricRows: 10, flaggedEvents: 1, flagKinds: ["unknown-condition"], gapCount: 1, missingEvents: 2, complete: false, lastReceivedAt: "2026-07-16T15:40:00.000Z" },
];

const SEED_LIFECYCLE: LifecycleDoc = {
  currentPhase: "data-collection",
  phases: [
    { name: "design", status: "complete", gates: [{ artifact: "protocol-validated.txt", satisfied: true, satisfiedBy: { fileId: 1, uploadedAt: "2026-07-12", size: 512 } }] },
    { name: "ethics", status: "complete", gates: [{ artifact: "ethics-approval.pdf", satisfied: true, satisfiedBy: { fileId: 2, uploadedAt: "2026-07-12", size: 88000 } }] },
    { name: "pilot", status: "complete", gates: [] },
    { name: "recruitment", status: "complete", gates: [] },
    { name: "data-collection", status: "current", gates: [] },
    { name: "analysis", status: "upcoming", gates: [{ artifact: "threats-record.json", satisfied: false, satisfiedBy: null }] },
    { name: "write-up", status: "upcoming", gates: [] },
  ],
};

// Offline fallback for the prescription table (the live values come from the
// analysis engine at /analysis/prescriptions). Kept short — the two shapes a
// small-N developer study most often lands on.
const SEED_PRESCRIPTIONS: Prescription[] = [
  {
    designShape: "paired",
    test: "Wilcoxon signed-rank (exact, two-sided)",
    effectSize: "Matched-pairs rank-biserial correlation (r)",
    correction: "none",
    sampleSizeGuidance: "Report per-cell n; small-N is hypothesis-generating.",
    rationale: "Within-subjects pairs each participant to themselves: the exact paired test needs no normality assumption.",
  },
  {
    designShape: "two-group",
    test: "Mann-Whitney U (exact, two-sided)",
    effectSize: "Cliff's delta",
    correction: "none",
    sampleSizeGuidance: "Report per-cell n; small-N is hypothesis-generating.",
    rationale: "Two independent groups with no distribution assumption; Cliff's delta reports the effect honestly at small N.",
  },
];
