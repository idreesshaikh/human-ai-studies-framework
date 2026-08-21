/* The study-data client. Talks to the ingestion middleware for the study
 * operational + knowledge endpoints — papers, the citation graph, the grounded
 * assistant, session status, and the dataset.
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
import type {
  PowerCurve,
  PowerDoc,
  PowerPoint,
  PowerRequirement,
  Recommendation,
} from "./types";

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
  /** Events received per bucket, oldest first — the sparkline. */
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
  /** The ethics package (FR-AGENT-5, FR-ETH-4): design, tasks, what is
   *  captured, and the exact consent text, generated from the protocol
   *  alone. A 409 (no compiled protocol yet) surfaces as the same
   *  `ApiError` every other study read does — the caller's existing catch
   *  handles it, so nothing bespoke is needed here. */
  downloadEthicsPackage: async (study: string) => {
    await saveAs(
      `/studies/${enc(study)}/ethics-package`,
      `${study}-ethics-package.md`,
    );
  },
  /** The starter notebook + data dictionary, zipped: the curated handoff.
   *  A loaded, documented dataframe with every planned recipe imported —
   *  never run — so a researcher's own analysis starts from a known point
   *  rather than a bare dataset export. */
  downloadNotebook: async (study: string) => {
    await saveAs(`/studies/${enc(study)}/notebook`, `${study}-notebook.zip`);
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
  prescriptions: (study?: string) =>
    liveOrSeed(
      () =>
        req<{ prescriptions: Prescription[] }>(
          `/analysis/prescriptions${study ? `?study_id=${enc(study)}` : ""}`,
        ).then((d) => d.prescriptions),
      SEED_PRESCRIPTIONS,
    ),
  /** The power/sensitivity curve (P2-2): exact two-sample t-test power
   * (non-central t, equal per-group n, two-sided) across per-group n, plus
   * the first n reaching the target power, per effect size. Planning math
   * over the study's planned comparison — the payload carries its own model
   * and assumptions, so the panel renders them without hardcoding. Offline:
   * the demo study gets a normal-approximation stand-in of the same formula
   * (the seeded-data banner says so); real studies get an honest empty doc. */
  power: (
    study: string,
    opts: {
      alpha?: number;
      maxN?: number;
      powerTarget?: number;
      effectSizes?: number[];
    } = {},
  ) =>
    liveOrSeedStudy(
      study,
      () => {
        const q = new URLSearchParams();
        q.set("alpha", String(opts.alpha ?? 0.05));
        q.set("maxN", String(opts.maxN ?? 120));
        q.set("powerTarget", String(opts.powerTarget ?? 0.8));
        q.set("effectSizes", (opts.effectSizes ?? [0.2, 0.5, 0.8]).join(","));
        return req<PowerDoc>(`/studies/${enc(study)}/power?${q.toString()}`);
      },
      seedPowerDoc(opts),
      emptyPowerDoc(),
    ),
  /** Synthetic dry run (FR-DRY-1): N simulated participants through the
   * real ingest path — tokens minted, session blocks recorded, events and
   * metrics stored exactly as a live capture would. The report states what
   * landed. A live action: never seeded, offline raises `OfflineError`. */
  simulate: (study: string, count = 10, profile = "mixed", seed?: number) =>
    post<{
      participants: number;
      profile: string;
      seed: number | null;
      run: string;
      sessions: number;
      events: number;
      metricRows: number;
      tokensMinted: number;
      studyId: string;
    }>(`/studies/${enc(study)}/simulate`, {
      count,
      profile,
      ...(seed !== undefined ? { seed } : {}),
    }),
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
  /** The study's compiled protocol, read-only.
   *
   *  The conversation gets its protocol back from `/conversation/compile`,
   *  which needs a contribute-level capability — so a viewer (and every
   *  visitor to the read-only demo) got a 403 there and saw an empty
   *  "no design shape yet" rail over a fully compiled protocol. This is the
   *  view-capability twin of that call: no compilation, no write, just the
   *  document of record. */
  protocol: (study: string) =>
    req<{ document?: Record<string, unknown> }>(
      `/studies/${enc(study)}/protocol`,
    ).then((r) => r.document ?? null),
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
// conversation cites) so the constellation, library, and charts are
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
    sessionId: "S-ai-assisted", source: "tern",
    participantId: "P1", condition: "ai-assisted",
    seq: 0, type: "session_start", payload: {}, flags: [],
  },
  {
    v: 4, ts: "2026-07-16T14:30:05.000Z", mono: 5_000,
    sessionId: "S-ai-assisted", source: "tern",
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
    sessionId: "S-ai-assisted", source: "tern",
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
    sessionId: "S-ai-assisted", source: "tern",
    participantId: "P1", condition: "ai-assisted",
    seq: 3, type: "fatigue_prompt_shown", payload: { trigger: "scheduled" }, flags: ["unauthenticated"],
  },
  {
    v: 4, ts: "2026-07-16T14:33:05.000Z", mono: 185_000,
    sessionId: "S-ai-assisted", source: "tern",
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

// Offline stand-in for the power curve (P2-2). The live payload is exact
// non-central-t math from the middleware; the stand-in uses the normal
// approximation of the same two-sample t-test power formula, computed
// deterministically at module load. It exists so the demo study still
// renders with nothing on :8000 — the existing seeded-data banner says so.
function normCdf(x: number): number {
  return 0.5 * (1 + erf(x / Math.SQRT2));
}

// Abramowitz & Stegun 7.1.26 — good to ~1.5e-7, plenty for a stand-in.
function erf(x: number): number {
  const t = 1 / (1 + 0.3275911 * Math.abs(x));
  const y =
    1 -
    (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) *
      t *
      Math.exp(-x * x);
  return x >= 0 ? y : -y;
}

const Z_ALPHA: Record<number, number> = { 0.01: 2.5758293035, 0.05: 1.9599639845, 0.1: 1.644853627 };

function seedPowerDoc(opts: {
  alpha?: number;
  maxN?: number;
  powerTarget?: number;
  effectSizes?: number[];
}): PowerDoc {
  const alpha = opts.alpha ?? 0.05;
  const powerTarget = opts.powerTarget ?? 0.8;
  const maxTotalN = opts.maxN ?? 120;
  const sizes = opts.effectSizes ?? [0.2, 0.5, 0.8];
  const zCrit = Z_ALPHA[alpha] ?? 1.9599639845;
  const maxPerGroup = Math.floor(maxTotalN / 2);
  const curves: PowerCurve[] = [];
  const requiredN: PowerRequirement[] = [];
  for (const d of sizes) {
    const points: PowerPoint[] = [];
    for (let n = 2; n <= maxPerGroup; n += 1) {
      const power = Math.min(
        1,
        Math.max(
          0,
          1 - normCdf(zCrit - d * Math.sqrt(n / 2)) + normCdf(-zCrit - d * Math.sqrt(n / 2)),
        ),
      );
      points.push({ nPerGroup: n, totalN: 2 * n, power: Math.round(power * 1e6) / 1e6 });
    }
    const reached = points.find((p) => p.power >= powerTarget);
    requiredN.push({
      effectSize: d,
      nPerGroup: reached?.nPerGroup ?? null,
      totalN: reached?.totalN ?? null,
      powerAtTargetN: reached?.power ?? null,
      reachesTarget: reached !== undefined,
    });
    curves.push({ effectSize: d, points });
  }
  return {
    model: "two-sample t-test, independent means, equal per-group n, two-sided",
    alpha,
    powerTarget,
    maxTotalN,
    curves,
    requiredN,
  };
}

function emptyPowerDoc(): PowerDoc {
  return {
    model: "two-sample t-test, independent means, equal per-group n, two-sided",
    alpha: 0.05,
    powerTarget: 0.8,
    maxTotalN: 120,
    curves: [],
    requiredN: [],
  };
}
