/**
 * Typed client for the ingestion middleware REST API (FR-ING-1).
 *
 * Same-origin always: the Vite dev server proxies these paths to :8000, and
 * in production the middleware serves the SPA itself (NFR-7). An optional
 * bearer token (localStorage `middleware.token`) matches MIDDLEWARE_TOKEN.
 */

export interface Health {
  status: string
  studyId: string | null
  protocolLoaded: boolean
}

export interface ResearchQuestion {
  id: string
  text: string
  recipes: string[]
}

export interface ProtocolSummary {
  studyId: string
  protocolVersion: number
  title: string
  researchers: string[]
  ethicsRef: string
  conditions: string[]
  participants: { planned: number; design?: string; counterbalanced?: boolean }
  session: { durationMinutes?: number; taskDescription?: string }
  researchQuestions: ResearchQuestion[]
  phases: { name: string; gates: string[] }[]
}

export interface Gate {
  artifact: string
  satisfied: boolean
  satisfiedBy: { fileId: number; uploadedAt: string; size: number } | null
}

export interface LifecyclePhase {
  name: string
  status: 'complete' | 'current' | 'upcoming'
  gates: Gate[]
}

export interface LifecycleDoc {
  currentPhase: string
  phases: LifecyclePhase[]
}

/** Row of GET /studies/{id}/sessions - per-leg counts only. */
export interface SessionSummary {
  sessionId: string
  participantId: string
  condition: string
  events: number
  metricRows: number
  firstTs: string | null
  lastTs: string | null
}

export interface SessionStatus {
  sessionId: string
  participantId: string
  condition: string
  events: number
  metricRows: number
  flaggedEvents: number
  flagKinds: string[]
  gapCount: number
  missingEvents: number
  complete: boolean
  lastReceivedAt: string | null
}

export interface RqCoverage {
  id: string
  recipes: string[]
  recipeRuns: string[]
}

export interface StatusDoc {
  studyId: string
  generatedAt: string
  lifecycle: LifecycleDoc
  conditions: string[]
  plannedParticipants: number
  plannedSessionsPerParticipant: number
  sessions: SessionStatus[]
  researchQuestions: RqCoverage[]
}

export interface LiveSession {
  sessionId: string
  participantId: string
  condition: string
  eventsInWindow: number
  lastEventType: string
  lastReceivedAt: string
  lastSeq: number
  rate: number[]
  gapCount: number
  missingEvents: number
}

export interface LiveDoc {
  now: string
  windowSeconds: number
  bucketSeconds: number
  sessions: LiveSession[]
}

export interface StudyEvent {
  v: number
  ts: string
  mono: number
  sessionId: string
  participantId: string
  condition: string
  seq: number
  type: string
  payload: Record<string, unknown>
  flags: string[]
}

export interface GapReport {
  sessionId: string
  firstSeq: number
  lastSeq: number
  received: number
  expected: number
  gaps: { afterSeq: number; beforeSeq: number; missing: number }[]
  complete: boolean
}

export interface ManualTask {
  id: number
  title: string
  status: 'open' | 'done'
  note: string
  createdAt: string
}

export interface DatasetRow {
  source: string
  ts: string
  sessionId: string
  participantId: string
  condition: string
  type: string
  seq: number | null
  flags: string[]
  payload: Record<string, unknown>
}

/** One operational finding (FR-META-1). */
export interface Finding {
  id: number
  at: string
  source: string
  kind: string
  requirementId: string
  message: string
  context: Record<string, unknown>
  status: string
}

export interface Paper {
  paperRef: string
  title: string
  authors: string[]
  year: number | null
  venue: string
  abstract: string
  doi: string
  arxivId: string
  url: string
  citationCount: number | null
  hasFullText: boolean
  links: string[]
  addedAt: string
  inProtocolLiterature: boolean
}

export interface GraphNode {
  paperRef: string
  title: string
  year: number | null
  citationCount: number | null
  ingested: boolean
}

export interface GraphEdge {
  src: string
  dst: string
  kind: 'references' | 'citations' | 'recommendations'
}

export interface PaperGraph {
  studyId: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface AssistantAnswer {
  answer: string
  citations: string[]
  toolCalls: { tool: string; input: Record<string, unknown> }[]
}

/** One SRS requirement row, parsed live from requirements/srs.md (FR-DASH-9). */
export interface RequirementInfo {
  id: string
  priority: string
  text: string
  status: string
}

/** One glossary row from requirements/glossary.md (FR-DASH-9). */
export interface GlossaryEntry {
  term: string
  definition: string
}

/** Sign-in surface the middleware wants (GET /auth/config). */
export interface AuthConfig {
  mode: 'none' | 'token' | 'clerk'
  clerkPublishableKey?: string
}

/**
 * Same-origin by default (dev proxy / middleware-served SPA). Set
 * VITE_API_BASE to a middleware URL when the dashboard is hosted on a
 * separate origin - the middleware must then allow that origin via
 * MIDDLEWARE_CORS_ORIGINS (FR-OPS-6).
 */
const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/+$/, '')

/**
 * Clerk mode injects a live token getter here (session JWTs are short-lived
 * and refreshed by clerk-js, so they are fetched per request); token mode
 * keeps the stored bearer token. Null getter = fall back to localStorage.
 */
type TokenProvider = () => Promise<string | null>
let tokenProvider: TokenProvider | null = null
export function setTokenProvider(provider: TokenProvider | null): void {
  tokenProvider = provider
}

async function headers(): Promise<Record<string, string>> {
  if (tokenProvider) {
    const token = await tokenProvider()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }
  const token = localStorage.getItem('middleware.token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Registered by the app shell: called on any 401 so the sign-in surface
 * can take over instead of views failing one by one.
 */
let unauthorizedListener: (() => void) | null = null
export function onUnauthorized(listener: (() => void) | null): void {
  unauthorizedListener = listener
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...init,
    headers: { ...(await headers()), ...(init.headers ?? {}) },
  })
  if (res.status === 401) unauthorizedListener?.()
  if (!res.ok) {
    throw new Error(`${init.method ?? 'GET'} ${path} -> ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

function send<T>(method: string, path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const api = {
  health: () => get<Health>('/health'),
  authConfig: () => get<AuthConfig>('/auth/config'),
  protocol: (study: string) =>
    get<ProtocolSummary>(`/studies/${encodeURIComponent(study)}/protocol`),
  lifecycle: (study: string) =>
    get<LifecycleDoc>(`/studies/${encodeURIComponent(study)}/lifecycle`),
  status: (study: string) =>
    get<StatusDoc>(`/studies/${encodeURIComponent(study)}/status`),
  live: (study: string) =>
    get<LiveDoc>(`/studies/${encodeURIComponent(study)}/live`),
  sessions: (study: string) =>
    get<SessionSummary[]>(`/studies/${encodeURIComponent(study)}/sessions`),
  events: (sessionId: string, limit = 10000) =>
    get<StudyEvent[]>(
      `/sessions/${encodeURIComponent(sessionId)}/events?limit=${limit}`,
    ),
  gaps: (sessionId: string) =>
    get<GapReport>(`/sessions/${encodeURIComponent(sessionId)}/gaps`),
  dataset: (study: string) =>
    get<{ studyId: string; rows: DatasetRow[] }>(
      `/studies/${encodeURIComponent(study)}/dataset`,
    ),
  requirements: () => get<RequirementInfo[]>('/requirements'),
  glossary: () => get<GlossaryEntry[]>('/glossary'),
  findings: () => get<Finding[]>('/findings'),
  scanFindings: (study: string) =>
    send<{ written: number }>(
      'POST',
      `/studies/${encodeURIComponent(study)}/findings/scan`,
      {},
    ),
  tasks: () => get<ManualTask[]>('/tasks'),
  addTask: (title: string, note = '') =>
    send<{ id: number }>('POST', '/tasks', { title, note }),
  setTaskStatus: (id: number, status: 'open' | 'done') =>
    send<{ id: number; status: string }>('PATCH', `/tasks/${id}`, { status }),
  uploadFile: async (file: File): Promise<{ id: number; duplicate: boolean }> => {
    const body = new FormData()
    body.append('file', file)
    const res = await fetch(API_BASE + '/ingest/files', {
      method: 'POST',
      body,
      headers: await headers(),
    })
    if (!res.ok) throw new Error(`upload failed: ${res.status}`)
    return res.json()
  },

  // --- knowledge layer (MP-10) ---
  papers: (study: string) =>
    get<Paper[]>(`/studies/${encodeURIComponent(study)}/papers`),
  papersGraph: (study: string) =>
    get<PaperGraph>(`/studies/${encodeURIComponent(study)}/papers/graph`),
  ingestPaper: (study: string, id: { arxivId?: string; doi?: string }) =>
    send<{ paperRef: string; title: string; edges: number }>(
      'POST',
      `/studies/${encodeURIComponent(study)}/papers`,
      id,
    ),
  deletePaper: (study: string, ref: string) =>
    request<{ deleted: string }>(
      `/studies/${encodeURIComponent(study)}/papers/${encodeURIComponent(ref)}`,
      { method: 'DELETE' },
    ),
  setPaperLinks: (study: string, ref: string, targets: string[]) =>
    send<{ paperRef: string; links: string[] }>(
      'PUT',
      `/studies/${encodeURIComponent(study)}/papers/${encodeURIComponent(ref)}/links`,
      { targets },
    ),
  uploadPaperPdf: async (study: string, file: File): Promise<{ paperRef: string }> => {
    const body = new FormData()
    body.append('file', file)
    const res = await fetch(
      `${API_BASE}/studies/${encodeURIComponent(study)}/papers/upload`,
      { method: 'POST', body, headers: await headers() },
    )
    if (!res.ok) throw new Error(`upload failed: ${res.status}`)
    return res.json()
  },
  assistantConfig: (study: string) =>
    get<{ configured: boolean; models: string[]; defaultModel: string }>(
      `/studies/${encodeURIComponent(study)}/assistant/config`,
    ),
  assistant: (
    study: string,
    question: string,
    history: { role: string; content: string }[],
    model?: string,
  ) =>
    send<AssistantAnswer>('POST', `/studies/${encodeURIComponent(study)}/assistant`, {
      question,
      history,
      ...(model ? { model } : {}),
    }),
}
